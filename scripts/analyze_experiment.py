#!/usr/bin/env python3
"""Pre-registered, rule-based candidate selection, sealed before holdout runs."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics

VARIANTS=("readall","buffered","optimized")
TRAIN=("train-small","train-large")
HOLDOUT=("holdout-wide","holdout-deep")

def median(xs):return statistics.median(xs)
def read_samples(path):
 return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
def calc_stats(rows):
 values=[r["result"]["duration_ns"]/1e6 for r in rows]
 if not values:raise ValueError("no samples")
 cv=statistics.stdev(values)/statistics.mean(values) if len(values)>1 else None
 result={"n":len(values),"median_ms":median(values),"mean_ms":statistics.mean(values),
         "cv":cv,"min_ms":min(values),"max_ms":max(values),
         "median_alloc_bytes":median([r["result"]["total_alloc_bytes"] for r in rows]),
         "median_maxrss_kib":median([r["result"]["process_maxrss_kib"] for r in rows])}
 if rows[0]["mode"]=="ebpf":
  result["syscalls"]={k:median([r["syscalls"][k] for r in rows]) for k in
                      ("read","write","copy_file_range","openat","close")}
 return result
def aggregate(rows,required_cases):
 grouped=defaultdict(list)
 for r in rows:
  if not r.get("correct") or not r["result"]["success"]:
   raise ValueError("failed data correctness")
  grouped[(r["case"],r["variant"],r["mode"])].append(r)
 report={}
 for case in required_cases:
  report[case]={}
  for variant in VARIANTS:
   report[case][variant]={}
   for mode in ("native","ebpf","goprof"):
    subset=grouped[(case,variant,mode)]
    if subset:report[case][variant][mode]=calc_stats(subset)
 return report
def scores(summary,cases):
 ratios={}
 for case in cases:
  best=min(summary[case][v]["native"]["median_ms"] for v in VARIANTS)
  ratios[case]={v:summary[case][v]["native"]["median_ms"]/best for v in VARIANTS}
 return {v:sum(ratios[case][v] for case in cases)/len(cases) for v in VARIANTS}

def select(summary,include_kernel):
 base_scores=scores(summary,TRAIN)
 go_choice=min(VARIANTS,key=lambda v:(base_scores[v],v))
 choice=go_choice
 explanation="minimum equally weighted normalized training latency"
 syscall_signature={}
 if include_kernel:
  for v in VARIANTS:
   per_case=[]
   for case in TRAIN:
    d=summary[case][v]["ebpf"]["syscalls"]
    per_case.append((d["read"]+d["write"]+d["copy_file_range"])/(
      summary[case][v]["native"]["median_ms"]*1000))
   syscall_signature[v]=sum(per_case)/len(per_case)
  # BPF is a tie breaker only when candidate latency differs < 5%.
  # Prefer fewer hot-path kernel entry events per task (relative proxy).
  close=[v for v in VARIANTS if base_scores[v]<=base_scores[go_choice]*1.05]
  choice=min(close,key=lambda v:(syscall_signature[v],base_scores[v],v))
  explanation=("among candidates within 5% training latency, prefer smaller "
               "observed kernel read/write/copy_file_range event density")
 return {"choice":choice,"scores":base_scores,"evidence":"go+ebpf" if include_kernel else "go-only",
         "rule":explanation,"kernel_event_density":syscall_signature}

def train(root):
 rows=read_samples(root/"train.jsonl")
 summary=aggregate(rows,TRAIN)
 for case in TRAIN:
  for v in VARIANTS:
   if summary[case][v].get("native",{}).get("n",0)<10:raise ValueError("train <10 native repeats")
   if summary[case][v].get("ebpf",{}).get("n",0)<5:raise ValueError("train <5 ebpf repeats")
   if summary[case][v].get("goprof",{}).get("n",0)<1:raise ValueError("profile missing")
 result={"go_only":select(summary,False),"go_and_ebpf":select(summary,True)}
 if (root/"sealed-predictions.json").exists():raise ValueError("sealed predictions already exist")
 (root/"train-summary.json").write_text(json.dumps(summary,indent=2)+"\n")
 (root/"sealed-predictions.json").write_text(json.dumps(result,indent=2)+"\n")
 print("TRAIN SEALED (no holdout results read):")
 print(json.dumps(result,indent=2))
def holdout(root):
 if not (root/"sealed-predictions.json").exists():
  raise ValueError("train selections must be sealed before holdout is run")
 pred=json.loads((root/"sealed-predictions.json").read_text())
 rows=read_samples(root/"holdout.jsonl")
 summary=aggregate(rows,HOLDOUT)
 for case in HOLDOUT:
  for v in VARIANTS:
   if summary[case][v].get("native",{}).get("n",0)<10:raise ValueError("holdout <10 native repeats")
   if summary[case][v].get("ebpf",{}).get("n",0)<5:raise ValueError("holdout <5 ebpf repeats")
 (root/"holdout-summary.json").write_text(json.dumps(summary,indent=2)+"\n")
 scores_out=scores(summary,HOLDOUT)
 choices={p:pred[p]["choice"] for p in ("go_only","go_and_ebpf")}
 regrets={p:(scores_out[v]-min(scores_out.values()))*100 for p,v in choices.items()}
 max_cv=max(summary[case][v]["native"]["cv"] for case in HOLDOUT for v in VARIANTS)
 ratios=[]
 train_summary=json.loads((root/"train-summary.json").read_text())
 for case in TRAIN:
  for v in VARIANTS:
   n=train_summary[case][v]["native"]["median_ms"]
   e=train_summary[case][v]["ebpf"]["median_ms"]
   ratios.append(e/n)
 median_overhead=median(ratios)
 gain=regrets["go_only"]-regrets["go_and_ebpf"]
 noise=max(5.0,200*max_cv)
 if max_cv>0.15 or not 0.75<=median_overhead<=1.20:
  verdict="INCONCLUSIVE_MEASUREMENT_NOISE_OR_OVERHEAD"
 elif choices["go_only"]==choices["go_and_ebpf"]:
  verdict="NO_ADDITIONAL_RANKING_VALUE_DEMONSTRATED"
 elif gain>noise:
  verdict="POSITIVE_RULE_BASED_EXPLORATORY"
 elif gain< -noise:
  verdict="NEGATIVE_RULE_BASED_EXPLORATORY"
 else:
  verdict="INCONCLUSIVE_DIFFERENCE_WITHIN_NOISE"
 out={"choices":choices,"holdout_relative_scores":scores_out,
      "regret_pct":regrets,"delta_regret_pct_points":gain,
      "max_holdout_native_cv":max_cv,"median_ebpf_overhead_ratio_train":median_overhead,
      "decision_noise_threshold_pct_points":noise,"verdict":verdict,
      "limitation":"Rule-based selectors were held out from validation outcomes, but no independent AI agent evaluation; not proof of AI decision improvement."}
 if (root/"evaluation.json").exists():raise ValueError("evaluation already exists; preserve earlier outcome")
 (root/"evaluation.json").write_text(json.dumps(out,indent=2)+"\n")
 print("HOLDOUT EVALUATION:")
 print(json.dumps(out,indent=2))
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--phase",choices=("seal-train","evaluate-holdout"),required=True)
 p.add_argument("--output",required=True,type=Path)
 a=p.parse_args()
 if a.phase=="seal-train":train(a.output)
 else:holdout(a.output)
if __name__=="__main__":main()
