#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
runs="${RUNS:-10}"
if ! [[ "$runs" =~ ^[0-9]+$ ]] || ((runs<10)); then echo 'RUNS must be >=10' >&2; exit 2; fi
mkdir -p results
go build -o ./bin/benchrun ./cmd/benchrun
./bin/benchrun -shape fanout -nodes 100 -workers 8 -spins 10000 >/dev/null
file="results/go-only-$(date -u +%Y%m%dT%H%M%SZ).jsonl"
for ((i=0;i<runs;i++)); do ./bin/benchrun -shape fanout -nodes 100 -workers 8 -spins 10000 >>"$file"; done
echo "$file"
python3 scripts/summarize.py "$file"
