#!/usr/bin/env python3
"""Concurrent typed and raw eBPF syscall counters against the same child."""
import json
from pathlib import Path
import re
import shutil
import subprocess
from experiment_runner import build_dataset, verify_output

OUT=Path("results/e004").resolve()
BIN=Path("bin/iobench").resolve()
PROBE="""tracepoint:syscalls:sys_enter_read /pid == cpid/ { @named_read = count(); }
tracepoint:raw_syscalls:sys_enter /pid == cpid && args->id == 0/ { @raw_read = count(); }
tracepoint:syscalls:sys_enter_write /pid == cpid/ { @named_write = count(); }
tracepoint:raw_syscalls:sys_enter /pid == cpid && args->id == 1/ { @raw_write = count(); }
tracepoint:syscalls:sys_enter_copy_file_range /pid == cpid/ { @named_cfr = count(); }
tracepoint:raw_syscalls:sys_enter /pid == cpid && args->id == 326/ { @raw_cfr = count(); }"""

def main():
 if OUT.exists():raise SystemExit("E004 output exists; do not overwrite")
 OUT.mkdir(parents=True)
 in_dir=OUT/"input"
 expected=build_dataset(in_dir,8,8388608,20261022)
 result=[]
 for variant in ("buffered","readall","optimized"):
  out_dir=OUT/("out-"+variant)
  out_dir.mkdir()
  command=[str(BIN),"-variant",variant,"-shape","chain","-nodes","8","-workers","2",
           "-input-dir",str(in_dir),"-output-dir",str(out_dir)]
  proc=subprocess.run(["sudo","bpftrace","-q","-c"," ".join(command),"-e",PROBE],
                      capture_output=True,text=True,timeout=100)
  (OUT/(variant+".stdout")).write_text(proc.stdout)
  (OUT/(variant+".stderr")).write_text(proc.stderr)
  if proc.returncode:raise RuntimeError(f"bpftrace failed ({variant}): {proc.stderr}")
  verify_output(out_dir,expected)
  observed={m.group(1):int(m.group(2)) for m in re.finditer(
   r"(?m)^@([a-z_]+):\s*(\d+)\s*$",proc.stdout)}
  pairs={name:{"named":observed.get("named_"+name,0),
               "raw":observed.get("raw_"+name,0)} for name in ("read","write","cfr")}
  if pairs["read"]["raw"]<8:raise ValueError("No expected read events")
  if any(pairs[name]["named"]!=pairs[name]["raw"] for name in ("read","write","cfr")):
   raise ValueError(f"Same-run counter mismatch: {variant}: {pairs}")
  result.append({"variant":variant,"sha256_verified":True,"kernel_event_counts":pairs})
  print(variant,pairs,flush=True)
  shutil.rmtree(out_dir)
 (OUT/"result.json").write_text(json.dumps(result,indent=2)+"\n")
 shutil.rmtree(in_dir)
 print("E004 PASS: concurrent typed/raw tracepoints agree",flush=True)
if __name__=="__main__":main()
