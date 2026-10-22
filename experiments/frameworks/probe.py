#!/usr/bin/env python3
"""F001: exact counts, PID isolation and BPF object lifetime, not performance."""
import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import select
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"


def object_ids(command):
    # Linux x86_64 SYS_bpf=321; bpf_attr start_id/next_id/open_flags.
    class Attr(ctypes.Structure):
        _fields_ = [("start", ctypes.c_uint32), ("next", ctypes.c_uint32), ("flags", ctypes.c_uint32)]
    libc = ctypes.CDLL(None, use_errno=True)
    found = set()
    attr = Attr()
    while True:
        rc = libc.syscall(ctypes.c_long(321), ctypes.c_int(command), ctypes.byref(attr), ctypes.sizeof(attr))
        if rc < 0:
            error = ctypes.get_errno()
            if error == errno.ENOENT:
                return found
            raise OSError(error, os.strerror(error))
        found.add(attr.next)
        attr.start = attr.next


def inventory():
    return {"programs": object_ids(11), "maps": object_ids(12)}


def serial(inv):
    return {key: sorted(value) for key, value in inv.items()}


def line(process, timeout=30):
    if not select.select([process.stdout], [], [], timeout)[0]:
        raise TimeoutError("process readiness/result timed out")
    value = process.stdout.readline()
    if not value:
        raise RuntimeError(f"process exited before readiness/result: rc={process.poll()}")
    return value


def command(framework, pid):
    if framework == "bpftrace":
        ready = f"/usr/bin/python3 {ROOT / 'bpftrace_ready.py'}"
        return ["bpftrace", "-q", "-B", "line", "-c", ready, str(ROOT / "counter.bt"), str(pid)]
    if framework == "bcc":
        return ["/usr/bin/python3", "-u", str(ROOT / "bcc_collector.py"), str(pid)]
    obj = BUILD / ("aya-counter" if framework == "aya" else "counter.bpf.o")
    return [str(BUILD / framework), str(pid), str(obj)]


def parse_counter(framework, stdout):
    if framework == "bpftrace":
        matches = re.findall(r"(?m)^@events:\s*(\d+)\s*$", stdout)
        if len(matches) > 1:
            raise ValueError("ambiguous bpftrace counter snapshots")
        return int(matches[0]) if matches else 0
    values = [json.loads(x) for x in stdout.splitlines() if x.startswith('{"observed"')]
    if len(values) != 1 or type(values[0]["observed"]) is not int or values[0]["observed"] < 0:
        raise ValueError("missing/invalid/ambiguous counter output")
    return values[0]["observed"]


def stop(process):
    if process is None:
        return
    if process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def trial(framework, directory, batches, negative_calls):
    directory.mkdir()
    selected = other = collector = None
    before = inventory()
    during = None
    result = {"batches": batches, "expected": sum(batches), "negative_control_calls": negative_calls}
    error = None
    stdout = ""
    stderr_path = directory / "collector.stderr"
    with stderr_path.open("w") as stderr:
        try:
            selected = subprocess.Popen([str(BUILD / "target")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            other = subprocess.Popen([str(BUILD / "target")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            if line(selected).strip() != "READY" or line(other).strip() != "READY":
                raise RuntimeError("invalid target readiness")
            result.update(selected_pid=selected.pid, negative_pid=other.pid)
            collector = subprocess.Popen(command(framework, selected.pid), stdout=subprocess.PIPE, stderr=stderr, text=True)
            end = time.monotonic() + 40
            while "READY" not in stdout.splitlines():
                if time.monotonic() > end:
                    raise TimeoutError("collector did not attach")
                stdout += line(collector, max(0.1, end - time.monotonic()))
            during = inventory()
            introduced = {key: during[key] - before[key] for key in before}
            if not introduced["programs"] or not introduced["maps"]:
                raise RuntimeError("no new live BPF program/map after readiness")
            other.stdin.write(f"{negative_calls}\n"); other.stdin.flush()
            if line(other).strip() != f"DONE {negative_calls}":
                raise RuntimeError("negative target failed")
            for n in batches:
                selected.stdin.write(f"{n}\n"); selected.stdin.flush()
                if line(selected).strip() != f"DONE {n}":
                    raise RuntimeError("selected target failed")
            collector.send_signal(signal.SIGINT)
            tail, _ = collector.communicate(timeout=12)
            stdout += tail
            result["collector_exit"] = collector.returncode
            if collector.returncode != 0:
                raise RuntimeError(f"collector exit {collector.returncode}")
            observed = parse_counter(framework, stdout)
            result["observed"] = observed
            if observed != sum(batches):
                raise RuntimeError(f"counter mismatch: expected={sum(batches)} observed={observed}")
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        finally:
            stop(collector)
            if collector and collector.stdout and not collector.stdout.closed:
                stdout += collector.stdout.read()
            for process in (selected, other):
                if process is not None:
                    process.stdin.close()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=3)
    (directory / "collector.stdout").write_text(stdout)
    after = inventory()
    if during is not None:
        introduced = {key: during[key] - before[key] for key in before}
        until = time.monotonic() + 3
        while any(introduced[key] & after[key] for key in before) and time.monotonic() < until:
            time.sleep(0.05)
            after = inventory()
        leftovers = {key: introduced[key] & after[key] for key in before}
        result.update(introduced=serial(introduced), remaining=serial(leftovers))
        if any(leftovers.values()):
            error = (error + "; " if error else "") + "BPF objects remained after collector exit"
    result.update(before=serial(before), after=serial(after), error=error, verdict="FAIL" if error else "PASS")
    (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--framework", required=True, choices=["bpftrace", "libbpf", "cilium", "aya", "bcc"])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if platform.machine() != "x86_64" or os.geteuid() != 0:
        parser.error("requires explicitly controlled Linux x86_64 root runner")
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "result.json").exists():
        parser.error("refusing to overwrite an existing result")
    metadata = {"framework": args.framework, "kernel": platform.uname()._asdict(), "utc_epoch": time.time(),
                "source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "github": {k: os.getenv(k) for k in ["GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "ImageOS", "ImageVersion"]},
                "hook": "tracepoint/raw_syscalls/sys_enter", "syscall_id": 39, "signal_loss": "in-kernel map aggregation; no streamed event transport"}
    (args.output / "environment.json").write_text(json.dumps(metadata, indent=2) + "\n")
    results = []
    try:
        for repeat in range(3):
            for label, batches in [("zero", []), ("single", [500]), ("batches", [1, 499, 5000])]:
                result = trial(args.framework, args.output / f"r{repeat}-{label}", batches, 137)
                results.append(result)
                print(f"{args.framework} r{repeat} {label}: {result['verdict']} observed={result.get('observed')} expected={sum(batches)}", flush=True)
                if result["verdict"] != "PASS":
                    raise RuntimeError(result["error"])
        verdict, error = "PASS", None
    except Exception as exc:
        verdict, error = "FAIL", str(exc)
    summary = {**metadata, "verdict": verdict, "error": error, "passed_trials": sum(x["verdict"] == "PASS" for x in results),
               "expected_trials": 9, "trials": results,
               "boundary": "Only this pinned toolchain, hook, map counter and recorded runner; no all-hook, performance or agent-improvement claim."}
    (args.output / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    sums = []
    for path in sorted(args.output.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(args.output)}")
    (args.output / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n")
    print(json.dumps({"framework": args.framework, "verdict": verdict, "passed_trials": summary["passed_trials"], "error": error}))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
