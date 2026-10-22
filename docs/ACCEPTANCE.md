# PoC Acceptance Gates

| Gate | Must demonstrate | Current |
|---|---|---|
| G0 scope | exact upstream commit pinned, upstream untouched | PASS (documented) |
| E001 GitHub-hosted feasibility | exact run demonstrates eBPF tracepoint load, attach and positive child-process events | PASS — 500/500 events, [report](experiments/2026-10-22-github-actions-ebpf.md) |
| G1 workload | end-to-end deterministic DAG success and cancellation tests | PARTIAL — external chain/fanout and I/O tests; full cancellation matrix pending |
| G2 Go benchmark | >= 10 repeats and baseline variance reported | PASS for E005 scenarios; hosted-runner noise remains |
| G3 kernel | capability preflight, controlled eBPF collection | PASS for raw syscalls on Actions x86_64; scheduling/page faults untested |
| G4 overhead | same workload without tracing / Go-only / Go+eBPF | PARTIAL — R001 controlled costs for buffered file copy; other paths pending |
| G5 alternatives | >= 2 semantically equivalent candidate implementations, correctness/race tests | PARTIAL — three I/O candidates and digest checks; full race/cancel coverage pending |
| G6 incremental value | blinded comparison vs independent held-out measurements | NOT DEMONSTRATED — both sealed E005 rules chose optimized; independent AI evaluator pending |
| G7 report | immutable input, raw data, CI, and clear positive/negative/inconclusive verdict | PARTIAL — E001–E005/F001/R001 retained; E006 and independent review pending |

A successful instrumentation demo **does not** count as an accepted PoC.

## F001 — implementation-path capability: PASS

The 2026-10-22 scope clarification asks for evidence and future integration
feasibility. Automated agent code modification is not required in this phase.

| Path | Exact count / PID isolation / repeat / cleanup |
|---|---|
| bpftrace | PASS 9/9 |
| C/libbpf | PASS 9/9 |
| Go/cilium-ebpf | PASS 9/9 |
| Rust/Aya | PASS 9/9 |
| Python/BCC | PASS 9/9 |

[Final run 39776073689](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39776073689)
used exact source `5d45ef49e26b81ab4495ce43fe4ef91959bd643a`.
All 185 artifact files matched their final checksum manifests; raw counters were
independently rechecked for all 45 trials. See [full results](experiments/F001-RESULT.md).

These results close F001 for the recorded environments. They do not close G6,
prove improved agent decisions, or establish support for other hook/kernel types.
Earlier failed attempts and their original manifests remain available.

## R001 — first-stage selective tracing cost/information study

Measurement and evidence integrity: PASS for the buffered file-copy scope.
Two runs at source `24a6e4a3ca48a53d0b16bf22882c0a9793c60623` completed 384 timed
observations plus four controls. G4 now has controlled native/Go/Go+eBPF cost
evidence for this narrow path; broader workload coverage remains open.

Incremental implementation-selection or independent AI diagnosis improvement:
NOT DEMONSTRATED / independent AI comparison NOT PERFORMED. G6/E006 remain open.
R001 is not a replacement for E006. Author's first opinion: withhold routine
adoption; selective diagnostic use remains a candidate. See
[R001 results](experiments/R001-RESULT.md) and
[raw evidence](experiments/r001-evidence/README.md).
