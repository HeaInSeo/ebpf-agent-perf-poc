# PoC Acceptance Gates

| Gate | Must demonstrate | Current |
|---|---|---|
| G0 scope | exact upstream commit pinned, upstream untouched | PASS (documented) |
| E001 GitHub-hosted feasibility | exact run demonstrates eBPF tracepoint load, attach and positive child-process events | PASS — 500/500 events, [report](experiments/2026-10-22-github-actions-ebpf.md) |
| G1 workload | end-to-end deterministic DAG success and cancellation tests | NOT VERIFIED |
| G2 Go benchmark | >= 10 repeats and baseline variance reported | NOT RUN |
| G3 kernel | dedicated VM capability preflight, controlled eBPF collection | NOT RUN |
| G4 overhead | same workload without tracing / Go-only / Go+eBPF | NOT RUN |
| G5 alternatives | >= 2 semantically equivalent candidate implementations, correctness/race tests | NOT RUN |
| G6 incremental value | blinded comparison vs independent held-out measurements | NOT RUN |
| G7 report | immutable input, raw data, CI, and clear positive/negative/inconclusive verdict | NOT RUN |

A successful instrumentation demo **does not** count as an accepted PoC.
