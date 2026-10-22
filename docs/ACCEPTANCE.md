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

## F001 — implementation-path capability (registered, not run)

Per the 2026-10-22 scope clarification, this stage validates execution evidence
and future integration feasibility. Automated agent code modification is not
required to complete F001. Its PASS does not close the incremental-value gates.

Five paths must be attempted: bpftrace, libbpf, cilium/ebpf, Aya and BCC. For each,
retain build/load/attach, exact counts, PID isolation, repeat and cleanup results;
report unsupported or blocked paths explicitly. See the
[F001 protocol](experiments/F001-FRAMEWORK-COMPAT-PROTOCOL.md).
