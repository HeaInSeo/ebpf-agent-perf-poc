#!/usr/bin/env python3
"""Exercises 2/3: inspect live BCC programs and tail callees with bpftool."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent

def run(*cmd, check=True):
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=False, timeout=25)
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd))}: {result.stdout}")
    return result

def programs():
    return json.loads(run("bpftool", "-j", "prog", "show").stdout)

def maps():
    return json.loads(run("bpftool", "-j", "map", "show").stdout)

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")

def inspect_live(mode, out):
    tag = "ex02" if mode == "map" else "ex03"
    ready = out / f"{tag}-ready.json"
    counts_file = out / f"{tag}-counts.json"
    for path in (ready, counts_file):
        path.unlink(missing_ok=True)
    before = {p["id"] for p in programs()}
    logfile = (out / f"{tag}-worker.log").open("w")
    cmd = ["/usr/bin/python3", "-u", str(HERE / "bcc_worker.py"),
           "--mode", mode, "--ready", str(ready), "--counts", str(counts_file)]
    worker = subprocess.Popen(cmd, stdout=logfile, stderr=subprocess.STDOUT)
    detected = []
    try:
        deadline = time.monotonic() + 80
        while not ready.exists():
            if worker.poll() is not None:
                raise RuntimeError(f"{tag} BCC worker exited: {worker.returncode}")
            if time.monotonic() > deadline:
                raise TimeoutError(f"{tag} BCC attach timed out")
            time.sleep(0.2)
        meta = json.loads(ready.read_text())
        expected = set(meta["expected"])
        after = [p for p in programs() if p["id"] not in before]
        detected = [p for p in after if p.get("name") in expected]
        by_name = {p["name"]: p for p in detected}
        if set(by_name) != expected:
            raise AssertionError(f"{tag} expected={expected}, loaded={list(by_name)}")
        expected_type = "kprobe" if mode == "map" else "raw_tracepoint"
        for item in detected:
            if item["type"] != expected_type:
                raise AssertionError(f"unexpected type {item}")
        all_maps = {m["id"]: m for m in maps()}
        all_map_ids = set()
        jit_info = {}
        for name in sorted(expected):
            prog = by_name[name]
            prog_id = prog["id"]
            all_map_ids.update(prog.get("map_ids", []))
            (out / f"{tag}-{name}-prog.txt").write_text(
                run("bpftool", "prog", "show", "id", str(prog_id)).stdout)
            xlated = run("bpftool", "prog", "dump", "xlated", "id",
                         str(prog_id)).stdout
            if not xlated.strip():
                raise AssertionError(f"{name}: no xlated bytecode")
            (out / f"{tag}-{name}-xlated.txt").write_text(xlated)
            jited = run("bpftool", "prog", "dump", "jited", "id",
                        str(prog_id), check=False)
            jit_ok = bool(jited.stdout.strip()) and jited.returncode == 0
            (out / f"{tag}-{name}-jited.txt").write_text(jited.stdout)
            jit_info[name] = {"kernel_jited": prog.get("jited", False),
                              "dump_available": jit_ok}
            if prog.get("jited", False) and not jit_ok:
                raise AssertionError(f"{name}: JIT is marked present but dump failed")
            print(f"{tag} LIVE {name}: id={prog_id} type={prog['type']}"
                  f" xlated={prog.get('bytes_xlated')}B"
                  f" jited={prog.get('bytes_jited', 0)}B"
                  f" dump={jit_ok}", flush=True)
        used_maps = [all_maps[id] for id in sorted(all_map_ids) if id in all_maps]
        write_json(out / f"{tag}-map-metadata.json", used_maps)
        map_names = {m.get("name") for m in used_maps}
        required_map = "counter_table" if mode == "map" else "jump"
        if required_map not in map_names:
            raise AssertionError(f"{tag} missing map {required_map}: {map_names}")
        if mode == "map":
            for _ in range(12):
                run("/usr/bin/true")
        else:
            time.sleep(1)
        worker.terminate()
        worker.wait(timeout=12)
        if worker.returncode != 0:
            raise AssertionError(f"{tag}: worker exited {worker.returncode}")
        if not counts_file.exists():
            raise AssertionError(f"{tag}: no map counter snapshot")
        counts = json.loads(counts_file.read_text())
        if mode == "map":
            if sum(counts.values()) < 12:
                raise AssertionError(f"{tag}: execve events < 12: {counts}")
        elif any(counts.get(k, 0) < 1 for k in ("uname", "getpid", "gettid")):
            raise AssertionError(f"{tag}: tail call counters not incremented: {counts}")
        leaked = {p["id"] for p in programs()} & {p["id"] for p in detected}
        for _ in range(10):
            if not leaked:
                break
            time.sleep(0.2)
            leaked = {p["id"] for p in programs()} & {p["id"] for p in detected}
        if leaked:
            raise AssertionError(f"{tag}: program IDs not released: {sorted(leaked)}")
        result = {"status": "PASS", "mode": mode, "worker_pid": meta["pid"],
                  "programs": [{"id": by_name[n]["id"], "name": n,
                                "type": by_name[n]["type"]}
                               for n in sorted(expected)],
                  "jit": jit_info, "counts": counts,
                  "cleanup": "all inspected program IDs released"}
        write_json(out / f"{tag}.json", result)
        print(f"{tag} PASS: {len(expected)} live programs, counts={counts},"
              " released on worker exit", flush=True)
    finally:
        if worker.poll() is None:
            worker.terminate()
            try:
                worker.wait(timeout=8)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()
        logfile.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("requires root in controlled GitHub Actions job")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    errors = []
    for mode in ("map", "tail"):
        try:
            inspect_live(mode, out)
        except Exception as exc:
            print(f"EXERCISE {mode} FAIL: {exc}", file=sys.stderr, flush=True)
            errors.append(f"{mode}: {exc}")
            write_json(out / ("ex02-error.json" if mode == "map"
                              else "ex03-error.json"), {"error": str(exc)})
    if errors:
        sys.exit(1)

if __name__ == "__main__":
    main()
