#!/usr/bin/env python3
"""Compare raw and typed syscall hooks on every allowed CPU, sequentially."""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys

from run import Blocked, is_target_event, validate_result


HERE = Path(__file__).resolve().parent
TRACE_CPU = re.compile(r"^\s*.*?-(\d+)\s+\[(\d+)\]\s+")
RAW_ROUNDS = 2
MAX_CPUS = 8


def assess_trial(mode, cpu, returncode, result, env, source_sha, timed_out=False):
    """An empty typed control is an observation, never a raw success."""
    if mode not in ("raw", "typed"):
        raise ValueError("알 수 없는 대조 경로임")
    if timed_out:
        raise ValueError("시도별 45초 제한을 초과함")
    if env.get("source_sha") != source_sha:
        raise ValueError("시도별 실행 코드 SHA가 기준과 다름")
    if result.get("target_cpu") != cpu or result.get("target_affinity") != [cpu]:
        raise ValueError("대상 CPU 고정 결과가 요청과 다름")
    if result.get("attached") is not True:
        raise ValueError("eBPF 연결 완료를 확인하지 못함")
    if result.get("target_exit") != 0 or result.get("loader_exit") != 0 or result.get("detached") is not True:
        raise ValueError("대상·로더 정상 종료와 연결 해제를 확인하지 못함")
    pid, cookie = result.get("target_pid"), result.get("cookie")
    if not isinstance(pid, int) or pid <= 0 or not isinstance(cookie, int) or cookie <= 0:
        raise ValueError("대상 PID 또는 실행 식별값이 유효하지 않음")
    events = result.get("events")
    if not isinstance(events, list) or result.get("received_events") != len(events) or result.get("expected_events") != 1:
        raise ValueError("커널 메시지 수 기록이 일치하지 않음")

    if mode == "typed" and not events:
        # Do not excuse a configuration, collection, or restoration error merely
        # because its result also happens to contain zero events.
        try:
            validate_result([], 0, 0, True)
        except RuntimeError as exc:
            expected_reason = str(exc)
        if returncode != 1 or result.get("status") != "FAIL" or result.get("reason") != expected_reason:
            raise ValueError("typed 대조의 정상 실행 후 메시지 미수신 조건을 충족하지 못함")
        return "NO_EVENT"

    if returncode != 0 or result.get("status") != "PASS":
        raise ValueError("메시지 수신 성공과 실행기 정상 종료를 확인하지 못함")
    validate_result(events, result["target_exit"], result["loader_exit"], result["detached"])
    if not is_target_event(events[0], pid, cookie):
        raise ValueError("커널 원문의 PID·cookie가 대상과 다름")
    match = TRACE_CPU.match(events[0])
    if not match or int(match[1]) != pid or int(match[2]) != cpu:
        raise ValueError("커널 원문에 기록된 PID·CPU가 대상과 다름")
    return "PASS"


def run_trial(mode, cpu, round_number, args, source_bytes, source_sha):
    relative = Path(mode) / f"cpu-{cpu}" / f"round-{round_number}"
    output = args.output / relative
    # A previous trial must not be mistaken for a new subprocess result.
    output.mkdir(parents=True, exist_ok=False)
    (output / "source-sha.txt").write_bytes(source_bytes)
    object_path = args.object if mode == "raw" else args.legacy_object
    command = [
        sys.executable, "-u", str(HERE / "run.py"),
        "--output", str(output.resolve()), "--object", str(object_path.resolve()),
        "--loader", str(args.loader.resolve()), "--cpu", str(cpu), "--timeout", "8",
    ]
    label = f"[{mode} CPU {cpu} round {round_number}]"
    print(f"{label} 실행 시작", flush=True)
    timed_out = False
    with (output / "driver.stdout.log").open("wb") as stdout, (output / "driver.stderr.log").open("wb") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                   env=os.environ.copy(), start_new_session=True)
        try:
            returncode = process.wait(timeout=45)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
            # The run.py parent may exit before its children; address the whole
            # new process group to prevent an orphaned gated target or loader.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            returncode = process.wait(timeout=3)

    for name in ("driver.stdout.log", "driver.stderr.log"):
        for line in (output / name).read_text(errors="replace").splitlines():
            print(f"{label} {line}", flush=True)

    record = {
        "mode": mode, "cpu": cpu, "round": round_number,
        "source_sha": None, "expected_source_sha": source_sha,
        "path": relative.as_posix(), "command": command,
        "subprocess_exit": returncode, "timed_out": timed_out,
        "validation": "FAIL", "validation_reason": "결과 기록을 확인하지 못함",
    }
    try:
        result = json.loads((output / "result.json").read_text())
        env = json.loads((output / "environment.json").read_text())
        record.update({key: result.get(key) for key in (
            "status", "reason", "target_pid", "cookie", "target_cpu", "target_affinity",
            "received_events", "expected_events", "events", "target_exit", "loader_exit", "attached", "detached",
        )})
        record["source_sha"] = env.get("source_sha")
        record["kernel"] = env.get("kernel")
        record["observed_cpus"] = [int(match[2]) for line in result.get("events", [])
                                   if (match := TRACE_CPU.match(line))]
        record["validation"] = assess_trial(mode, cpu, returncode, result, env, source_sha, timed_out)
        record["validation_reason"] = (
            "지정한 CPU의 실제 커널 메시지 1건과 정상 종료·연결 해제를 확인함"
            if record["validation"] == "PASS" else
            "typed 대조에서 정상 연결·실행·정리 후 커널 메시지 0건을 관찰함"
        )
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        record["validation_reason"] = f"{type(exc).__name__}: {exc}"
    print(f"{label} {record['validation']}: {record['validation_reason']}", flush=True)
    return record


def summary(report):
    lines = [
        f"## CPU별 eBPF 재현 확인 — {report['status']}", "", report["reason"], "",
        f"- 허용된 CPU: `{report['allowed_cpus']}`",
        f"- 실행 코드: `{report['source_sha']}`",
        f"- raw 검증: **{report['raw_passed']} / {report['raw_expected']} 통과**",
        f"- typed 대조: **{report['typed_valid']} / {report['typed_expected']} 기록 검증 완료**", "",
        "| 경로 | CPU | 회차 | 메시지 수 | 출력 CPU | 판정 |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for trial in report["trials"]:
        observed = ", ".join(map(str, trial.get("observed_cpus", []))) or "—"
        verdict = "0건 관측 (대조)" if trial["validation"] == "NO_EVENT" else trial["validation"]
        lines.append(f"| {trial['mode']} | {trial['cpu']} | {trial['round']} | {trial.get('received_events', '—')} | {observed} | {verdict} |")
    lines += [
        "",
        "raw 경로는 CPU마다 2회 실행하며, 매번 지정한 CPU의 실제 커널 메시지 1건과 정상 종료·연결 해제가 모두 필요함.",
        "",
        "typed 경로는 기존 syscall tracepoint의 대조 실험임. 정상 연결·대상 실행·정리 후 메시지만 0건인 경우를 미수신 관측으로 보존함. 다른 오류는 전체 검증 실패로 처리함.",
        "",
        "시도별 원본 메시지, 실행 환경, PID·cookie, stdout·stderr는 `cpu-checks/{raw,typed}/cpu-번호/round-회차/`에 보관함.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/hello-world/cpu-checks"))
    parser.add_argument("--object", type=Path, default=HERE / "build/hello.bpf.o")
    parser.add_argument("--legacy-object", type=Path, default=HERE / "build/hello-typed.bpf.o")
    parser.add_argument("--loader", type=Path, default=HERE / "build/hello")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "FAIL", "reason": "CPU별 검증이 완료되지 않음",
        "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "kernel": platform.release(), "allowed_cpus": [], "source_sha": "unavailable",
        "raw_rounds_per_cpu": RAW_ROUNDS, "typed_rounds_per_cpu": 1,
        "raw_expected": 0, "raw_passed": 0, "typed_expected": 0, "typed_valid": 0,
        "trials": [],
    }
    try:
        if not hasattr(os, "sched_getaffinity"):
            raise Blocked("Linux CPU affinity 기능이 필요함")
        cpus = sorted(os.sched_getaffinity(0))
        report["allowed_cpus"] = cpus
        report["raw_expected"] = len(cpus) * RAW_ROUNDS
        report["typed_expected"] = len(cpus)
        if not cpus or len(cpus) > MAX_CPUS:
            raise Blocked(f"전체 CPU 검증 범위는 1~{MAX_CPUS}개임. 현재 허용된 CPU 수={len(cpus)}; 일부 CPU만 검사하지 않음")
        if os.geteuid() != 0:
            raise Blocked("격리된 Linux 실험 환경에서 sudo 권한이 필요함")
        source_file = args.output.parent / "source-sha.txt"
        if not source_file.is_file():
            raise Blocked("상위 결과 폴더에 source-sha.txt가 필요함")
        source_bytes = source_file.read_bytes()
        source_sha = source_bytes.decode("utf-8").strip()
        if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
            raise Blocked("기준 실행 코드 SHA가 유효하지 않음")
        if os.environ.get("GITHUB_SHA") and os.environ["GITHUB_SHA"] != source_sha:
            raise RuntimeError("기준 실행 코드 SHA와 Actions의 GITHUB_SHA가 다름")
        report["source_sha"] = source_sha
        (args.output / "source-sha.txt").write_bytes(source_bytes)
        for path in (args.object, args.legacy_object, args.loader):
            if not path.is_file():
                raise Blocked(f"필요한 빌드 결과가 없음: {path}")
        for cpu in cpus:
            for mode, rounds in (("raw", RAW_ROUNDS), ("typed", 1)):
                for round_number in range(1, rounds + 1):
                    trial = run_trial(mode, cpu, round_number, args, source_bytes, source_sha)
                    report["trials"].append(trial)
                    if mode == "raw" and trial["validation"] == "PASS":
                        report["raw_passed"] += 1
                    if mode == "typed" and trial["validation"] in ("PASS", "NO_EVENT"):
                        report["typed_valid"] += 1
        if report["raw_passed"] == report["raw_expected"] and report["typed_valid"] == report["typed_expected"]:
            report["status"] = "PASS"
            report["reason"] = "허용된 모든 CPU에서 raw 경로의 실제 커널 메시지 수신을 반복 확인하고 typed 대조 결과를 보존함."
        else:
            report["reason"] = "raw 반복 검증 또는 typed 대조의 실행·증거 조건을 충족하지 못함. 시도별 기록 확인이 필요함."
    except Blocked as exc:
        report["status"] = "BLOCKED"
        report["reason"] = str(exc)
    except Exception as exc:
        report["reason"] = f"{type(exc).__name__}: {exc}"
    report["completed_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    (args.output / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    (args.output / "summary.md").write_text(summary(report))
    print(f"[CPU 검증] {report['status']}: {report['reason']}", flush=True)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
