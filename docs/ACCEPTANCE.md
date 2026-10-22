# PoC Acceptance Gates

| Gate | Must demonstrate | Current |
|---|---|---|
| G0 scope | exact upstream commit pinned, upstream untouched | PASS (documented) |
| E001 GitHub-hosted feasibility | exact run demonstrates eBPF tracepoint load, attach and positive child-process events | PASS — 500/500 events, [report](experiments/2026-10-22-github-actions-ebpf.md) |
| G1 workload | end-to-end deterministic DAG success and cancellation tests | PARTIAL — external chain/fanout and I/O tests; full cancellation matrix pending |
| G2 Go benchmark | >= 10 repeats and baseline variance reported | PASS for E005 scenarios; hosted-runner noise remains |
| G3 kernel | capability preflight, controlled eBPF collection | PASS for raw syscalls on Actions x86_64; scheduling/page faults untested |
| G4 overhead | same workload without tracing / Go-only / Go+eBPF | PARTIAL — native/traced/profiler runs; controlled overhead study pending |
| G5 alternatives | >= 2 semantically equivalent candidate implementations, correctness/race tests | PARTIAL — three I/O candidates and digest checks; full race/cancel coverage pending |
| G6 incremental value | blinded comparison vs independent held-out measurements | NOT DEMONSTRATED — both sealed E005 rules chose optimized; independent AI evaluator pending |
| G7 report | immutable input, raw data, CI, and clear positive/negative/inconclusive verdict | PARTIAL — E001–E005 retained; E006 and independent review pending |

A successful instrumentation demo **does not** count as an accepted PoC.
