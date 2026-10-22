#!/usr/bin/env python3
"""R001 fixed summaries; no information-count proxy is called code quality."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics as st
import subprocess
import time

def write(path, obj):
    with path.open("x") as f:
        json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")

def rows(path):
    result=[json.loads(x) for x in path.read_text().splitlines()]
    if not result or any(not r["correct"] for r in result):
        raise ValueError("missing/corrupt observations")
    return result

def quant(xs,p):
    return sorted(xs)[round((len(xs)-1)*p)]

def bootstrap(values):
    rng=random.Random(20261022)
    draws=[st.median(rng.choices(values,k=len(values))) for _ in range(10000)]
    return {"n":len(values),"median":st.median(values),"ci95":[quant(draws,.025),quant(draws,.975)],
            "min":min(values),"max":max(values)}

def rank(pair_ratios):
    bounds=bootstrap(pair_ratios)
    return {"B_over_A":bounds,"choice":"B" if bounds["ci95"][1]<.95 else "A" if bounds["ci95"][0]>1.05 else "ABSTAIN"}

def group(data):
    grouped={}
    for r in data:
        grouped.setdefault((r["case"],r["chunk"],r["mode"]),[]).append(r)
    for k,v in grouped.items():
        v.sort(key=lambda r:r["round"])
        if [x["round"] for x in v] != list(range(12)):
            raise ValueError("missing/duplicate rounds: "+str(k))
    return grouped

def profiles(root, grouped):
    for (case,chunk,mode),data in grouped.items():
        if mode=="native":continue
        folder=root/(f"{case}-{chunk}-{mode}-profiles")
        folder.mkdir()
        cpu=[str(root/"acquire"/r["folder"]/"go.cpu.pprof") for r in data]
        with (folder/"cpu-top.txt").open("w") as out:
            subprocess.run(["go","tool","pprof","-top","-nodecount=40"]+cpu,stdout=out,stderr=subprocess.STDOUT,check=True)
        trace=root/"acquire"/data[0]["folder"]/"go.runtime.trace"
        for kind in ("syscall","sched","sync"):
            profile=folder/(kind+".pprof")
            with profile.open("wb") as out:
                subprocess.run(["go","tool","trace","-pprof="+kind,str(trace)],stdout=out,check=True)
            with (folder/(kind+"-top.txt")).open("w") as out:
                subprocess.run(["go","tool","pprof","-top",str(profile)],stdout=out,stderr=subprocess.STDOUT,check=True)

def seal(root):
    data=rows(root/"acquire/raw.jsonl");g=group(data)
    if len(data)!=144:raise ValueError("expected 144 acquisition trials")
    decisions={}
    for case in ("small","large"):
        a=g[(case,32768,"native")];b=g[(case,65536,"native")]
        decisions[case]=rank([y["result"]["duration_ns"]/x["result"]["duration_ns"] for x,y in zip(a,b)])
    write(root/"sealed-go-choice.json",{"epoch":time.time(),"choices":decisions,
          "method":"Fixed native timing rule, Go profiles available; not an independent AI evaluator",
          "kernel_tie_break":"none: fewer syscalls is not a throughput objective"})
    profiles(root,g)
    print(json.dumps(decisions,indent=2))

def evaluate(root):
    data=rows(root/"acquire/raw.jsonl");holdout=rows(root/"holdout/raw.jsonl")
    g=group(data);hg=group(holdout)
    if len(data)!=144 or len(holdout)!=48:raise ValueError("trial cardinality")
    summary={"acquisition_trials":len(data),"holdout_trials":len(holdout),"cases":{},"holdout":{},
             "interpretation":"resource/information ablation, not independent AI decision improvement"}
    for case in ("small","large"):
        part={}
        for chunk in (32768,65536):
            native=g[(case,chunk,"native")];go=g[(case,chunk,"go")];ebpf=g[(case,chunk,"go-ebpf")]
            bymode={}
            for mode,rs in (("native",native),("go",go),("go-ebpf",ebpf)):
                bymode[mode]={
                    "hot_ms":bootstrap([r["result"]["duration_ns"]/1e6 for r in rs]),
                    "hot_cpu_ms":st.median(r["result"]["cpu_ns"]/1e6 for r in rs),
                    "target_maxrss_kib":st.median(r["target_resource"]["maxrss_kib"] for r in rs),
                    "target_process_cpu_s":st.median(r["target_resource"]["user_s"]+r["target_resource"]["system_s"] for r in rs),
                    "full_s":bootstrap([r["end_to_end_s"] for r in rs]),
                    "alloc_bytes":st.median(r["result"]["alloc_bytes"] for r in rs)}
                if mode=="go-ebpf":
                    bymode[mode].update({
                        "collector_attach_s":st.median(r["collector_attach_s"] for r in rs),
                        "collector_maxrss_kib":st.median(r["collector_resource"]["maxrss_kib"] for r in rs),
                        "collector_cpu_s":st.median(r["collector_resource"]["user_s"]+r["collector_resource"]["system_s"] for r in rs),
                        "maps_first":rs[0]["maps"]})
            part[str(chunk)]={"modes":bymode,
                "ebpf_over_go_hot_ratio":bootstrap([e["result"]["duration_ns"]/o["result"]["duration_ns"] for o,e in zip(go,ebpf)]),
                "go_over_native_hot_ratio":bootstrap([o["result"]["duration_ns"]/n["result"]["duration_ns"] for n,o in zip(native,go)]),
                "ebpf_minus_go_full_s":bootstrap([e["end_to_end_s"]-o["end_to_end_s"] for o,e in zip(go,ebpf)]),
                "ebpf_minus_go_total_cpu_s":bootstrap([
                    e["target_resource"]["user_s"]+e["target_resource"]["system_s"]+
                    e["collector_resource"]["user_s"]+e["collector_resource"]["system_s"]-
                    o["target_resource"]["user_s"]-o["target_resource"]["system_s"] for o,e in zip(go,ebpf)])}
        summary["cases"][case]=part
        a=hg[(case+"-holdout",32768,"native")];b=hg[(case+"-holdout",65536,"native")]
        summary["holdout"][case]=rank([y["result"]["duration_ns"]/x["result"]["duration_ns"] for x,y in zip(a,b)])
    sizes={}
    for mode in ("native","go","go-ebpf"):
        sizes[mode]=sum(p.stat().st_size for r in data if r["mode"]==mode
                        for p in (root/"acquire"/r["folder"]).rglob("*") if p.is_file())
    summary["acquisition_artifact_bytes_by_mode"]=sizes
    summary["sealed_go_choice"]=json.loads((root/"sealed-go-choice.json").read_text())
    write(root/"summary.json",summary)
    print(json.dumps(summary,indent=2))

def manifest(root):
    lines=[]
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name!="SHA256SUMS.txt":
            lines.append(hashlib.sha256(p.read_bytes()).hexdigest()+"  "+str(p.relative_to(root)))
    (root/"SHA256SUMS.txt").write_text("\n".join(lines)+"\n")

def main():
    p=argparse.ArgumentParser();p.add_argument("phase",choices=("seal","evaluate","manifest"));p.add_argument("root",type=Path)
    a=p.parse_args()
    {"seal":seal,"evaluate":evaluate,"manifest":manifest}[a.phase](a.root.resolve())
if __name__=="__main__":main()
