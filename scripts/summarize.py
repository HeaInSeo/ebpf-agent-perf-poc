#!/usr/bin/env python3
"""Summarize one raw JSONL sample set; not a comparative or causal verdict."""
import json
import statistics
import sys
from pathlib import Path
if len(sys.argv) != 2:
    sys.exit("Usage: summarize.py results/go-only-*.jsonl")
items = [json.loads(x) for x in Path(sys.argv[1]).read_text().splitlines() if x.strip()]
if len(items) < 10 or not all(x["success"] and x["executed"] == x["nodes"] for x in items):
    sys.exit("INVALID: expected >=10 correct repeated runs")
keys = {(x["shape"],x["nodes"],x["workers"],x["spins"]) for x in items}
if len(keys) != 1:
    sys.exit("INVALID: mixed workload configurations")
ms = [x["duration_ns"]/1e6 for x in items]
print(json.dumps({"n":len(ms),"workload":list(keys)[0],"median_ms":statistics.median(ms),
"mean_ms":statistics.mean(ms),"stddev_ms":statistics.stdev(ms),
"cv":statistics.stdev(ms)/statistics.mean(ms),
"min_ms":min(ms),"max_ms":max(ms),"interpretation":"exploratory only; no instrumented or candidate comparison"},
indent=2))
