#!/usr/bin/env python3
"""Compare eBPF syscall counts with strace -f for the same DAG copy variants."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from experiment_runner import build_dataset, verify_output

ROOT=Path("results/e003").resolve()
BIN=Path("bin/iobench").resolve()
RAW="""tracepoint:raw_syscalls:sys_enter /pid == cpid/ {
 @syscall_id[args->id] = count();
}"""
NODES=8
SIZE=8388608

def call(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=120)
 if p.returncode:raise RuntimeError(f"exit={p.returncode} stdout={p.stdout[-300:]} stderr={p.stderr[-1000:]}")
 return p
def checksum_outputs(path,expected):
 verify_output(path,expected)
 return {"count":len(expected),"sha256_verified":True}
def main():
 if ROOT.exists():raise SystemExit("E003 results already present (no overwrite)")
 ROOT.mkdir(parents=True)
 input_dir=ROOT/"inputs"
 expected=build_dataset(input_dir,NODES,SIZE,20261022)
 reports=[]
 for v in ("buffered","readall","optimized"):
  report={"variant":v,"nodes":NODES,"bytes_per_file":SIZE}
  for method in ("ebpf","strace"):
   out=ROOT/f"out-{v}-{method}"
   out.mkdir()
   cmd=[str(BIN),"-variant",v,"-shape","chain","-nodes",str(NODES),
        "-workers","2","-input-dir",str(input_dir),"-output-dir",str(out)]
   if method=="ebpf":
    wrapped=["sudo","bpftrace","-q","-c"," ".join(cmd),"-e",RAW]
   else:
    wrapped=["strace","-f","-c","-e","trace=read,write,pwrite64,writev,pwritev,copy_file_range,openat,close",*cmd]
   p=call(wrapped)
   (ROOT/f"{v}-{method}.stdout").write_text(p.stdout)
   (ROOT/f"{v}-{method}.stderr").write_text(p.stderr)
   report[method+"_exit"]=p.returncode
   report[method+"_output"]=checksum_outputs(out,expected)
   if method=="ebpf":
    matches=re.findall(r"(?m)^@syscall_id\[(\d+)\]:\s*(\d+)\s*$",p.stdout)
    report["raw_syscall_ids"]={k:int(n) for k,n in matches}
    if not matches:raise ValueError("empty raw syscall event map")
   else:
    report["strace_summary"]=p.stderr
   shutil.rmtree(out)
  reports.append(report)
 (ROOT/"result.json").write_text(json.dumps(reports,indent=2)+"\n")
 shutil.rmtree(input_dir)
 for row in reports:
  print(row["variant"],"eBPF ID counts (0 read/1 write/18 pwrite/326 copy_file_range):",
        {i:row["raw_syscall_ids"].get(str(i),0) for i in (0,1,18,326)})
  print("strace:",row["strace_summary"][-650:])
 print("E003 executed and raw evidence saved")
if __name__=="__main__":main()
