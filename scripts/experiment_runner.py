#!/usr/bin/env python3
"""Record immutable DAG I/O experiments without changing the upstream library."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import subprocess
import sys
import time

VARIANTS = ("readall", "buffered", "optimized")
CASES = {
 "train-small": (12, 65536, 4, "fanout"),
 "train-large": (8, 2097152, 4, "fanout"),
 "holdout-wide": (24, 1048576, 8, "fanout"),
 "holdout-deep": (8, 8388608, 2, "chain"),
}
# x86_64 Linux syscall IDs; raw_syscalls was independently matched to strace in E003.
# E004 proved typed sys_enter_write undercounted; do not use it for attribution.
BPF = """tracepoint:raw_syscalls:sys_enter /pid == cpid && args->id == 0/ { @read = count(); }
tracepoint:raw_syscalls:sys_enter /pid == cpid && args->id == 1/ { @write = count(); }
tracepoint:raw_syscalls:sys_enter /pid == cpid && args->id == 257/ { @openat = count(); }
tracepoint:raw_syscalls:sys_enter /pid == cpid && args->id == 326/ { @copy_file_range = count(); }
tracepoint:raw_syscalls:sys_enter /pid == cpid && args->id == 3/ { @close = count(); }"""

def shell_version(*command):
 try:
  p = subprocess.run(command,capture_output=True,text=True,check=False)
  return {"command":list(command),"exit":p.returncode,"stdout":p.stdout.strip(),"stderr":p.stderr.strip()}
 except FileNotFoundError:
  return {"command":list(command),"error":"tool not installed"}

def build_dataset(path,n,size,seed):
 path.mkdir(parents=True,exist_ok=False)
 hashes={}
 for i in range(n):
  rnd=random.Random(seed+i)
  # Deterministic repeated chunks, same size and entropy characteristics for variants.
  chunk=rnd.randbytes(16384)
  name=f"item-{i:04d}.bin"
  h=hashlib.sha256()
  with (path/name).open("wb") as out:
   left=size
   while left:
    data=chunk[:min(left,len(chunk))]
    out.write(data);h.update(data)
    left-=len(data)
  hashes[name]=h.hexdigest()
 return hashes
def verify_output(path,expected):
 observed={}
 for name,digest in expected.items():
  h=hashlib.sha256()
  with (path/name).open("rb") as f:
   for block in iter(lambda:f.read(256*1024),b""):
    h.update(block)
  observed[name]=h.hexdigest()
 if observed!=expected or sorted(os.listdir(path))!=sorted(expected):
  raise ValueError("OUTPUT_MISMATCH: output checksums or file names differ")
 return True

def parse_stdout(log):
 for line in log.splitlines():
  if line.startswith('{"') and '"duration_ns"' in line:
   result=json.loads(line)
   if result.get("success") is True:return result
 raise ValueError("RUNNER_RESULT_MISSING_OR_FAILED: "+log[-1000:])

def kernel_counts(log):
 counters={k:0 for k in ("read","write","openat","copy_file_range","close")}
 for key in counters:
  found=re.search(r"(?m)^@"+re.escape(key)+r":\s*(\d+)\s*$",log)
  if found:counters[key]=int(found.group(1))
 return counters

def run_one(binpath,input_dir,output_dir,case,variant,mode,profiles,seq):
 nodes,size,workers,shape=CASES[case]
 command=[str(binpath),"-variant",variant,"-shape",shape,"-input-dir",
          str(input_dir),"-output-dir",str(output_dir),
          "-nodes",str(nodes),"-workers",str(workers)]
 if mode=="goprof":
  command.extend(["-cpuprofile",str(profiles/f"{case}-{variant}-{seq}.cpu.pprof"),
                  "-trace",str(profiles/f"{case}-{variant}-{seq}.runtime.trace")])
 if mode=="ebpf":
  # bpftrace -c takes a single command string and launches child after attach.
  command=["sudo","bpftrace","-q","-c"," ".join(command),"-e",BPF]
 start=time.monotonic()
 process=subprocess.run(command,text=True,capture_output=True,timeout=65,
                        env={**os.environ,"GOMAXPROCS":"4"},check=False)
 wall=time.monotonic()-start
 if process.returncode!=0:
  raise RuntimeError(f"RUN_FAILED mode={mode} exit={process.returncode} stdout={process.stdout[-800:]} stderr={process.stderr[-800:]}")
 r=parse_stdout(process.stdout)
 return {"result":r,"syscalls":kernel_counts(process.stdout) if mode=="ebpf" else None,
         "full_process_s":wall,"stderr":process.stderr[-1500:],
         "bpftrace_stdout":process.stdout if mode=="ebpf" else ""}
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--phase",choices=("train","holdout"),required=True)
 p.add_argument("--output",type=Path,required=True)
 p.add_argument("--binary",type=Path,default=Path("bin/iobench"))
 p.add_argument("--repeats",type=int,default=10)
 p.add_argument("--ebpf-repeats",type=int,default=5)
 p.add_argument("--smoke",action="store_true")
 p.add_argument("--skip-ebpf",action="store_true",help="development-only smoke mode")
 args=p.parse_args()
 if args.repeats<1 or args.ebpf_repeats<1: p.error("repeats must be positive")
 root=args.output.resolve()
 root.mkdir(parents=True,exist_ok=True)
 binary=args.binary.resolve()
 if not binary.is_file():p.error(f"missing binary {binary}")
 cases=[c for c in CASES if c.startswith(args.phase)]
 if args.smoke:cases=cases[:1]
 workroot=root/"work"
 workroot.mkdir(exist_ok=True)
 profile_dir=root/"profiles"
 profile_dir.mkdir(exist_ok=True)
 records=root/(args.phase+".jsonl")
 if records.exists():p.error(f"refusing to overwrite raw record {records}")
 environment={
  "phase":args.phase, "epoch_utc":int(time.time()),
  "git":shell_version("git","rev-parse","HEAD"),
  "go":shell_version("go","version"),"uname":shell_version("uname","-a"),
  "bpftrace":shell_version("bpftrace","--version"),
  "cpuinfo":platform.processor(),"python":platform.python_version(),
  "github_run_id":os.getenv("GITHUB_RUN_ID"),"github_sha":os.getenv("GITHUB_SHA"),
  "gomaxprocs":"4","cases":{c:CASES[c] for c in cases},
  "seed":20261022,"repeats":args.repeats,"ebpf_repeats":args.ebpf_repeats,
  "validation":"sha256 all output files after each trial",
 }
 (root/(args.phase+"-environment.json")).write_text(json.dumps(environment,indent=2)+"\n")
 sequence=0
 with records.open("x") as outfile:
  for case in cases:
   nodes,size,workers,shape=CASES[case]
   input_dir=workroot/("input-"+case)
   expected=build_dataset(input_dir,nodes,size,20261022)
   try:
    # Untimed, verified warmup for each variant; do not include these in records.
    for warm_variant in VARIANTS:
     warm_dir=workroot/("warm-"+case+"-"+warm_variant)
     warm_dir.mkdir()
     try:
      run_one(binary,input_dir,warm_dir,case,warm_variant,"native",profile_dir,-1)
      verify_output(warm_dir,expected)
     finally:shutil.rmtree(warm_dir,ignore_errors=True)
    trial_count=1 if args.smoke else args.repeats
    for round_id in range(trial_count):
     order=list(VARIANTS)
     random.Random(20261022+round_id*97+len(case)).shuffle(order)
     for variant in order:
      modes=("native","ebpf") if (round_id<args.ebpf_repeats and not args.skip_ebpf) else ("native",)
      if round_id%2:modes=tuple(reversed(modes))
      for mode in modes:
       output_dir=workroot/f"output-{sequence:04d}"
       output_dir.mkdir()
       try:
        sample=run_one(binary,input_dir,output_dir,case,variant,mode,profile_dir,sequence)
        verify_output(output_dir,expected)
        row={"case":case,"phase":args.phase,"round":round_id,
             "seq":sequence,"variant":variant,"mode":mode,"file_size":size,
             "input_digest":hashlib.sha256(json.dumps(expected,sort_keys=True).encode()).hexdigest(),
             "correct":True,**sample}
        outfile.write(json.dumps(row,sort_keys=True)+"\n")
        outfile.flush()
        print(f"{args.phase} {case} {variant} {mode} {sample['result']['duration_ns']/1e6:.3f} ms",flush=True)
        sequence+=1
       finally:shutil.rmtree(output_dir,ignore_errors=True)
    if not args.smoke:
     for variant in VARIANTS:
      output_dir=workroot/f"output-{sequence:04d}"
      output_dir.mkdir()
      try:
       sample=run_one(binary,input_dir,output_dir,case,variant,"goprof",profile_dir,sequence)
       verify_output(output_dir,expected)
       row={"case":case,"phase":args.phase,"round":-1,"seq":sequence,
            "variant":variant,"mode":"goprof","file_size":size,"correct":True,**sample}
       outfile.write(json.dumps(row,sort_keys=True)+"\n"); outfile.flush()
       sequence+=1
      finally:shutil.rmtree(output_dir,ignore_errors=True)
   finally:shutil.rmtree(input_dir,ignore_errors=True)
 print(f"DONE phase={args.phase} samples={sequence} output={records}",flush=True)
if __name__=="__main__":main()
