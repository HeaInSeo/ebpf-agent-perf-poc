#!/usr/bin/env python3
"""Manual R001 acquisition. Raw observations are append-only and fail closed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import select
import signal
import subprocess
import time

CASES = {"small": (131072, 2048), "large": (16777216, 32)}
HOLDOUT = {"small-holdout": (196608, 2304), "large-holdout": (12582912, 48)}
MODES = ("native", "go", "go-ebpf")
TIMEFMT = '{"elapsed_s":%e,"user_s":%U,"system_s":%S,"maxrss_kib":%M,"exit":%x}'

def save(path, value):
    with path.open("x") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1048576), b""):
            h.update(b)
    return h.hexdigest()

def line(proc, timeout=45):
    if not select.select([proc.stdout], [], [], timeout)[0]:
        raise RuntimeError("handshake timeout")
    value = proc.stdout.readline()
    if not value:
        raise RuntimeError("process ended before handshake")
    return value

def bpf_program(pid, read_fd, write_fd):
    return f'''BEGIN {{ printf("READY\\n"); }}
tracepoint:raw_syscalls:sys_enter
/pid == {pid} && ((args->id == 0 && args->args[0] == {read_fd}) || (args->id == 1 && args->args[0] == {write_fd}))/
{{ @calls[args->id] = count(); @kind[tid] = args->id + 1; @started[tid] = nsecs; }}
tracepoint:raw_syscalls:sys_exit /pid == {pid} && @kind[tid]/
{{ $k = @kind[tid]-1; @latency_ns[$k] = sum(nsecs-@started[tid]);
   if (args->ret > 0) {{ @bytes[$k] = sum(args->ret); }}
   if (args->ret < 0) {{ @errors[$k] = count(); }}
   delete(@kind[tid]); delete(@started[tid]); }}
tracepoint:sched:sched_process_exit /pid == {pid} && tid == {pid}/ {{ exit(); }}
END {{ clear(@kind); clear(@started); }}'''

def parse_maps(raw):
    result = {name: {"0": 0, "1": 0} for name in ("calls", "bytes", "errors", "latency_ns")}
    for name, key, value in re.findall(r"(?m)^@(calls|bytes|errors|latency_ns)\[(0|1)\]:\s*(\d+)\s*$", raw):
        result[name][key] = int(value)
    return result

def trial(binary, input_file, size, copies, chunk, mode, folder):
    folder.mkdir()
    target_stderr = (folder / "target.stderr").open("w")
    collector_stderr = None
    target = collector = None
    started = time.monotonic()
    try:
        command = ["/usr/bin/time", "-f", TIMEFMT, "-o", str(folder / "target-resource.json"),
                   str(binary), "-input", str(input_file), "-output", str(folder / "output.bin"),
                   "-chunk", str(chunk), "-iterations", str(copies)]
        if mode != "native":
            command += ["-profile", str(folder / "go")]
        target = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=target_stderr, universal_newlines=True, bufsize=1,
                                  env={**os.environ, "GOMAXPROCS": "2"}, start_new_session=True)
        ready_line = line(target)
        ready = json.loads(ready_line)
        assert ready["ready"] is True
        attach_s = None
        collector_head = ""
        if mode == "go-ebpf":
            program = bpf_program(ready["pid"], ready["read_fd"], ready["write_fd"])
            (folder / "collector.bt").write_text(program)
            collector_stderr = (folder / "collector.stderr").open("w")
            attach_start = time.monotonic()
            collector = subprocess.Popen(["sudo", "-n", "/usr/bin/time", "-f", TIMEFMT,
                "-o", str(folder / "collector-resource.json"), "bpftrace", "-q", "-e", program],
                stdout=subprocess.PIPE, stderr=collector_stderr, universal_newlines=True, bufsize=1,
                start_new_session=True)
            collector_head = line(collector)
            if collector_head.strip() != "READY":
                raise RuntimeError("collector not READY: " + collector_head)
            attach_s = time.monotonic() - attach_start
        target.stdin.write("GO\n")
        target.stdin.flush()
        result_line = line(target, 90)
        result = json.loads(result_line)
        assert result["success"] and result["bytes"] == copies * size
        rest, _ = target.communicate("EXIT\n", timeout=30)
        if target.returncode or rest.strip():
            raise RuntimeError("target failed or unexpected stdout")
        (folder / "target.stdout").write_text(ready_line + result_line + rest)
        maps = None
        if collector:
            tail, _ = collector.communicate(timeout=30)
            raw = collector_head + tail
            (folder / "collector.stdout").write_text(raw)
            if collector.returncode:
                raise RuntimeError("collector failed")
            maps = parse_maps(raw)
            expected = {"calls": {"0": copies * ((size + chunk - 1) // chunk + 1),
                                  "1": copies * ((size + chunk - 1) // chunk)},
                        "bytes": {"0": copies * size, "1": copies * size},
                        "errors": {"0": 0, "1": 0}}
            for name, values in expected.items():
                if maps[name] != values:
                    raise RuntimeError("counter/byte mismatch " + json.dumps({"expected":expected,"observed":maps}))
        end_to_end = time.monotonic() - started
        target_stderr.close()
        if collector_stderr:
            collector_stderr.close()
        for name in ("target.stderr", "collector.stderr"):
            p = folder / name
            if p.exists() and p.read_text().strip():
                raise RuntimeError("unexpected stderr " + p.read_text()[-2000:])
        expected_hash = digest(input_file) if copies else hashlib.sha256(b"").hexdigest()
        if digest(folder / "output.bin") != expected_hash:
            raise RuntimeError("output checksum mismatch")
        (folder / "output.bin").unlink()
        row = {"mode":mode,"chunk":chunk,"size":size,"copies":copies,"correct":True,
               "result":result,"maps":maps,"collector_attach_s":attach_s,
               "end_to_end_s":end_to_end,"sha256":expected_hash,
               "target_resource":json.loads((folder / "target-resource.json").read_text()),
               "collector_resource":json.loads((folder / "collector-resource.json").read_text()) if collector else None}
        save(folder / "result.json", row)
        return row
    finally:
        for proc in (target, collector):
            if proc and proc.poll() is None:
                subprocess.run(["sudo", "-n", "kill", "-KILL", "--", "-"+str(proc.pid)], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                proc.wait(timeout=10)
        target_stderr.close()
        if collector_stderr:
            collector_stderr.close()

def dataset(path, size):
    block = random.Random(20261022).randbytes(65536)
    with path.open("xb") as f:
        left = size
        while left:
            part = block[:min(left, len(block))]
            f.write(part)
            left -= len(part)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=("acquire", "holdout"), required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--binary", type=Path, required=True)
    args = p.parse_args()
    root = args.root.resolve()
    root.mkdir(exist_ok=True, parents=True)
    phase = root / args.phase
    phase.mkdir()
    binary = args.binary.resolve()
    env = {"run_id":os.getenv("GITHUB_RUN_ID"),"run_attempt":os.getenv("GITHUB_RUN_ATTEMPT"),
           "sha":os.getenv("GITHUB_SHA"),"image":os.getenv("ImageVersion"),
           "kernel":platform.release(),"machine":platform.machine(),"cpu_count":os.cpu_count(),
           "seed":20261022,"repeats":12,"binary_sha256":digest(binary),
           "cpuinfo":Path("/proc/cpuinfo").read_text(),"started_epoch":time.time()}
    save(phase / "environment.json", env)
    if args.phase == "holdout" and not (root / "sealed-go-choice.json").exists():
        raise RuntimeError("Go choice not sealed")
    if args.phase == "acquire":
        for name, size, copies in (("zero",4097,0),("positive",4097,2)):
            input_file = phase / (name+".input")
            dataset(input_file,size)
            trial(binary,input_file,size,copies,32768,"go-ebpf",phase/name)
            input_file.unlink()
    cases = CASES if args.phase == "acquire" else HOLDOUT
    with (phase / "raw.jsonl").open("x") as record:
        for case, (size, copies) in cases.items():
            input_file = phase / (case+".input")
            dataset(input_file,size)
            for chunk in (32768,65536):
                trial(binary,input_file,size,copies,chunk,"native",phase/(case+"-warm-"+str(chunk)))
            for rnd in range(12):
                conditions = [(chunk,mode) for chunk in (32768,65536)
                              for mode in (MODES if args.phase == "acquire" else ("native",))]
                random.Random(20261022+rnd*97+size).shuffle(conditions)
                for chunk,mode in conditions:
                    name = f"{case}-{rnd:02d}-{chunk}-{mode}"
                    row = trial(binary,input_file,size,copies,chunk,mode,phase/name)
                    row.update({"case":case,"round":rnd,"folder":name})
                    record.write(json.dumps(row,sort_keys=True)+"\n"); record.flush()
                    print(f"{name}: {row['result']['duration_ns']/1e6:.3f}ms full={row['end_to_end_s']:.3f}s",flush=True)
            input_file.unlink()

if __name__ == "__main__":
    main()
