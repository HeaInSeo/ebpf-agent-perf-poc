#!/usr/bin/env python3
"""A bounded execve experiment; only actual trace_pipe records can pass it."""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import platform
import re
import secrets
import select
import signal
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
EVENT = re.compile(r"(?:^|:\s*)Hello World! pid=(\d+) cookie=(\d+)\s*$")
TARGET = """import os, sys
print('TARGET_READY', flush=True)
if sys.stdin.buffer.read(1) != b'1':
    sys.exit(2)
os.execv('/usr/bin/true', ['hello-world-target'])
"""


class Blocked(RuntimeError):
    """The chosen execution environment lacks a prerequisite."""


def log(message):
    print(message, flush=True)


def is_target_event(line, pid, cookie):
    """Do not accept setup messages, other PIDs, or a previous run's cookie."""
    match = EVENT.search(line)
    return bool(match and int(match[1]) == pid and int(match[2]) == cookie)


def validate_result(events, target_exit, loader_exit, detached):
    if len(events) != 1:
        raise RuntimeError(f"대상 커널 메시지가 정확히 1건이어야 함: 실제 {len(events)}건")
    if target_exit != 0:
        raise RuntimeError(f"테스트 프로그램이 정상 종료하지 않음: {target_exit}")
    if loader_exit != 0 or not detached:
        raise RuntimeError(f"eBPF 로더의 정상 정리를 확인하지 못함: exit={loader_exit}")


def configure_target_cpu(pid, cpu):
    """Pin the gated target before attach/execve and verify the applied affinity."""
    allowed = os.sched_getaffinity(0)
    if cpu is not None:
        if cpu not in allowed:
            raise Blocked(f"요청한 CPU {cpu}가 허용된 CPU 목록에 없음: {sorted(allowed)}")
        os.sched_setaffinity(pid, {cpu})
    affinity = sorted(os.sched_getaffinity(pid))
    if cpu is not None and affinity != [cpu]:
        raise RuntimeError(f"대상 CPU 고정 확인 실패: 요청={cpu}, 실제={affinity}")
    return affinity


def wait_ready(process, expected, destination, timeout=8):
    """Read a flushed readiness line without an unbounded readline()."""
    deadline = time.monotonic() + timeout
    pending = b""
    while time.monotonic() < deadline:
        ready, _, _ = select.select([process.stdout], [], [], 0.1)
        if not ready:
            if process.poll() is not None:
                raise RuntimeError(f"연결 준비 전에 프로세스가 종료됨: exit={process.returncode}")
            continue
        chunk = os.read(process.stdout.fileno(), 65536)
        if not chunk:
            raise RuntimeError("준비 완료 메시지 없이 출력이 종료됨")
        destination.write(chunk)
        destination.flush()
        pending += chunk
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            if line.decode("utf-8", errors="replace") == expected:
                return
    raise RuntimeError("제한 시간 안에 준비 완료 메시지를 받지 못함")


def collect_events(fd, pid, cookie, destination, timeout, diagnostics=None):
    if diagnostics is None:
        diagnostics = {}
    diagnostics.update(bytes_read=0, complete_lines=0, candidate_lines=[])
    deadline = time.monotonic() + timeout
    drain_deadline = None
    events = []
    pending = b""
    while time.monotonic() < (drain_deadline or deadline):
        remaining = (drain_deadline or deadline) - time.monotonic()
        try:
            chunk = os.read(fd, 65536)
        except BlockingIOError:
            # Nonblocking read is authoritative; poll is only a bounded wait.
            select.select([fd], [], [], min(0.1, max(0, remaining)))
            continue
        if not chunk:
            raise RuntimeError("커널 추적 스트림이 예기치 않게 종료됨")
        pending += chunk
        diagnostics["bytes_read"] += len(chunk)
        while b"\n" in pending:
            raw, pending = pending.split(b"\n", 1)
            line = raw.decode("utf-8", errors="replace")
            diagnostics["complete_lines"] += 1
            if "Hello World!" in line and f"cookie={cookie}" in line and len(diagnostics["candidate_lines"]) < 8:
                diagnostics["candidate_lines"].append(line)
            if is_target_event(line, pid, cookie):
                events.append(line)
                destination.write(line + "\n")
                destination.flush()
                log("[커널 원문] " + line)
                # The target has exited. Drain briefly to reject duplicate records.
                if drain_deadline is None:
                    drain_deadline = min(deadline, time.monotonic() + 0.25)
        if len(pending) > 1024 * 1024:
            raise RuntimeError("추적 스트림에서 비정상적으로 긴 레코드를 수신함")
    diagnostics["partial_bytes"] = len(pending)
    return events


def trace_state(tracing):
    state = {}
    for name in ("tracing_on", "current_tracer", "buffer_percent", "trace_options",
                 "events/bpf_trace/bpf_trace_printk/enable"):
        path = tracing / name
        state[name] = path.read_text().strip() if path.is_file() else "unavailable"
    return state


def ensure_trace_ready(tracing, changed):
    # New kernels enable bpf_trace_printk asynchronously during BPF loading.
    # READY means attached; confirm the output channel separately before execve.
    for name in ("tracing_on", "events/bpf_trace/bpf_trace_printk/enable"):
        path = tracing / name
        if not path.is_file():
            raise Blocked(f"커널 출력 채널 설정이 없음: {name}")
        previous = path.read_text().strip()
        if previous not in ("0", "1"):
            raise Blocked(f"커널 출력 채널 상태를 확인할 수 없음: {name}={previous}")
        if previous != "1":
            changed.append((path, previous))
            path.write_text("1\n")
        if path.read_text().strip() != "1":
            raise RuntimeError(f"커널 출력 채널 활성화 실패: {name}")


def stop_process(process, stdout_file, normal_loader=False):
    if process is None:
        return None, False
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
    forced = False
    try:
        output, _ = process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        forced = True
        process.kill()
        output, _ = process.communicate(timeout=3)
    if output:
        stdout_file.write(output)
        stdout_file.flush()
    detached = bool(normal_loader and not forced and b"DETACHED" in (output or b"").splitlines())
    return process.returncode, detached


def command_version(args):
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=5, check=False)
        if completed.returncode != 0:
            return "unavailable"
        return completed.stdout.strip().splitlines()[0]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return "unavailable"


def environment(output):
    repository = os.environ.get("GITHUB_REPOSITORY", "HeaInSeo/ebpf-agent-perf-poc")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    # Checkout ownership belongs to runner, so read the SHA recorded before sudo.
    source_file = output / "source-sha.txt"
    source_sha = source_file.read_text().strip() if source_file.is_file() else ""
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        source_sha = "unavailable"
    return {
        "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "uid": os.geteuid(),
        "cpu_count": os.cpu_count(),
        "allowed_cpus": sorted(os.sched_getaffinity(0)),
        "runner_image": os.environ.get("ImageOS", "unknown"),
        "runner_image_version": os.environ.get("ImageVersion", "unknown"),
        "source_sha": source_sha,
        "github_sha": os.environ.get("GITHUB_SHA", ""),
        "run_id": run_id,
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "run_url": f"https://github.com/{repository}/actions/runs/{run_id}" if run_id else "",
        "clang": command_version(["clang", "--version"]),
        "gcc": command_version(["gcc", "--version"]),
        "libbpf": command_version(["pkg-config", "--modversion", "libbpf"]),
        "python": platform.python_version(),
    }


def summary(result, env):
    events = result["events"]
    lines = [
        f"# eBPF Hello World — {result['status']}",
        "",
        result["reason"],
        "",
        "## 커널에서 받은 메시지",
        "",
    ]
    if events:
        lines += ["```text", *events, "```", ""]
    else:
        lines += ["이번 실행에서 검증 가능한 커널 메시지를 받지 못함.", ""]
    lines += [
        "## 확인 결과",
        "",
        "| 항목 | 결과 |",
        "| --- | --- |",
        f"| eBPF 연결 완료 | {'✅' if result['attached'] else '❌'} |",
        f"| 대상 메시지 수 | {len(events)} / 기대 1건 |",
        f"| 테스트 프로그램 종료 코드 | {result['target_exit']} |",
        f"| 로더 종료 코드 | {result['loader_exit']} |",
        f"| eBPF 연결 정리 확인 | {'✅' if result['detached'] else '❌'} |",
        f"| 대상 PID | `{result['target_pid']}` |",
        f"| 지정한 대상 CPU | {result['target_cpu'] if result['target_cpu'] is not None else '미지정'} |",
        f"| 대상 CPU affinity | `{result['target_affinity']}` |",
        f"| 실행 식별값 | `{result['cookie']}` |",
        f"| 커널 | `{env['kernel']}` |",
        f"| 실행한 코드 | `{env['source_sha']}` |",
        "",
        "메시지 전달 경로: `execve` 이벤트 → eBPF의 `bpf_printk()` → `trace_pipe` 수집 → 이 화면.",
        "",
        "메시지는 커널 추적 스트림에서 읽은 원문임. PID와 이번 실행의 식별값이 모두 일치해야 집계함.",
        "",
        "이 실험은 기능 확인용임. 성능 측정이나 기존 PoC 가설에 대한 판정은 포함하지 않음.",
        "",
        "자세한 과정은 **Hello World 실행 및 커널 메시지 확인** 로그, 원본 파일은 아래 Artifact에서 확인할 수 있음.",
        "",
    ]
    if env["run_url"]:
        lines += [f"[이 실행 열기]({env['run_url']})", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/hello-world"))
    parser.add_argument("--object", type=Path, default=HERE / "build/hello.bpf.o")
    parser.add_argument("--loader", type=Path, default=HERE / "build/hello")
    parser.add_argument("--timeout", type=float, default=8)
    parser.add_argument("--cpu", type=int, help="Pin the test target to one allowed CPU before execve")
    args = parser.parse_args()
    if not 0 < args.timeout <= 20:
        parser.error("--timeout must be greater than 0 and at most 20 seconds")
    args.output.mkdir(parents=True, exist_ok=True)
    env = environment(args.output)
    (args.output / "environment.json").write_text(json.dumps(env, ensure_ascii=False, indent=2) + "\n")
    result = {
        "status": "FAIL", "reason": "실행이 완료되지 않음", "attached": False,
        "target_pid": None, "cookie": secrets.randbits(63) or 1,
        "target_cpu": args.cpu, "target_affinity": [],
        "expected_events": 1, "events": [], "target_exit": None,
        "loader_exit": None, "detached": False,
    }
    target = loader = None
    trace_fd = None
    tracing = Path("/sys/kernel/tracing")
    trace_changes = []
    trace_diagnostics = {}
    read_diagnostics = {}
    failure = None
    with (args.output / "loader.stdout.log").open("wb") as loader_out, \
         (args.output / "loader.stderr.log").open("wb") as loader_err, \
         (args.output / "target.stdout.log").open("wb") as target_out, \
         (args.output / "target.stderr.log").open("wb") as target_err, \
         (args.output / "kernel-events.log").open("w") as events_out:
        try:
            if env["source_sha"] == "unavailable":
                raise Blocked("sudo 전에 git rev-parse HEAD 결과를 출력 폴더의 source-sha.txt에 기록해야 함")
            if env["github_sha"] and env["github_sha"] != env["source_sha"]:
                raise RuntimeError("체크아웃한 소스 SHA와 Actions의 GITHUB_SHA가 다름")
            if os.geteuid() != 0:
                raise Blocked("격리된 Linux 실험 환경에서 sudo 권한이 필요함")
            if not (tracing / "events/raw_syscalls/sys_enter/id").is_file():
                raise Blocked("tracefs 또는 raw_syscalls/sys_enter tracepoint가 없음")
            if args.cpu is not None and args.cpu not in env["allowed_cpus"]:
                raise Blocked(f"요청한 CPU {args.cpu}가 허용된 CPU 목록에 없음: {env['allowed_cpus']}")
            if not args.object.is_file() or not args.loader.is_file():
                raise Blocked("빌드 결과가 없음. 먼저 make -C experiments/hello-world를 실행해야 함")
            trace_fd = os.open(tracing / "trace_pipe", os.O_RDONLY | os.O_NONBLOCK)
            trace_diagnostics["before_attach"] = trace_state(tracing)
            log("[준비] 테스트 이벤트를 기다릴 커널 메시지 수집기를 열었음")
            target = subprocess.Popen(
                [sys.executable, "-u", "-c", TARGET], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=target_err, bufsize=0,
            )
            result["target_pid"] = target.pid
            wait_ready(target, "TARGET_READY", target_out)
            result["target_affinity"] = configure_target_cpu(target.pid, args.cpu)
            log(f"[준비] 테스트 프로세스 PID={target.pid}; 아직 execve 이벤트를 발생시키지 않음")
            log(f"[CPU 확인] 요청={args.cpu}, 대상 affinity={result['target_affinity']}")
            loader = subprocess.Popen(
                [str(args.loader.resolve()), str(args.object.resolve()), str(target.pid), str(result["cookie"])],
                stdout=subprocess.PIPE, stderr=loader_err, bufsize=0,
            )
            wait_ready(loader, f"READY pid={target.pid} cookie={result['cookie']}", loader_out)
            result["attached"] = True
            log("[연결] eBPF를 커널에 적재하고 execve 이벤트에 연결함")
            trace_diagnostics["before_output_ready"] = trace_state(tracing)
            ensure_trace_ready(tracing, trace_changes)
            trace_diagnostics["output_ready"] = trace_state(tracing)
            log("[출력 준비] tracing_on=1, bpf_trace_printk 이벤트 활성화를 확인함")
            target.stdin.write(b"1")
            target.stdin.close()
            target.stdin = None
            result["target_exit"] = target.wait(timeout=5)
            log("[실험] 테스트 프로세스가 /usr/bin/true를 실행함")
            result["events"] = collect_events(trace_fd, target.pid, result["cookie"], events_out,
                                               args.timeout, read_diagnostics)
        except Blocked as exc:
            result["status"] = "BLOCKED"
            failure = str(exc)
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"
        finally:
            for name, process, destination in (("loader", loader, loader_out), ("target", target, target_out)):
                try:
                    code, detached = stop_process(process, destination, normal_loader=(name == "loader"))
                    result[name + "_exit"] = code
                    if name == "loader":
                        result["detached"] = detached
                except Exception as exc:
                    failure = f"{failure + '; ' if failure else ''}{name} 정리 오류: {exc}"
            if trace_fd is not None:
                os.close(trace_fd)
            for path, previous in reversed(trace_changes):
                try:
                    path.write_text(previous + "\n")
                except OSError as exc:
                    failure = f"{failure + '; ' if failure else ''}추적 설정 복원 오류: {exc}"
    (args.output / "trace-settings.json").write_text(json.dumps(trace_diagnostics, ensure_ascii=False, indent=2) + "\n")
    (args.output / "reader.json").write_text(json.dumps(read_diagnostics, ensure_ascii=False, indent=2) + "\n")
    if failure is None:
        try:
            validate_result(result["events"], result["target_exit"], result["loader_exit"], result["detached"])
            result["status"] = "PASS"
            result["reason"] = "테스트 프로세스의 execve에서 나온 Hello World를 1건 받고 정상 종료함."
        except RuntimeError as exc:
            failure = str(exc)
    if failure is not None:
        result["reason"] = failure
    result["received_events"] = len(result["events"])
    (args.output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (args.output / "summary.md").write_text(summary(result, env))
    log(f"[정리] loader_exit={result['loader_exit']}, DETACHED={result['detached']}")
    log(f"[판정] {result['status']}: {result['reason']}")
    if result["status"] != "PASS":
        errors = (args.output / "loader.stderr.log").read_text(errors="replace")
        if errors:
            log("[로더 오류]\n" + errors)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
