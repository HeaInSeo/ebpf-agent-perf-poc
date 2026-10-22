# eBPF Agent Performance Evidence PoC

**Status: implementation bootstrap; no performance conclusion yet.**

## Hypothesis

Adding independently collected eBPF kernel observations to Go benchmarks,
profiles, and runtime traces may improve decisions between behaviorally equivalent
AI-generated implementations. The PoC must also permit a negative result.

## Hard boundaries

- NEVER modify `HeaInSeo/dag-go` or `HeaInSeo/ebpf-study`.
- Pin the dag-go baseline to exact source commit `1b22842771198ce15714c4da4d496060c11dccb8`.
- No modification to operational supervisor, queues, Notion, or production workers.
- Experimental variants reside here, preserve correctness contracts and are tested against the same workload.
- Keep kernel-observation collection opt-in. No sudo, mount, package installation or kernel tracing without an explicit controlled test environment.

## Stages

- **P0 – Protocol**: predeclare workloads, baseline, environment, measurements, equality conditions and thresholds.
- **P1 – Go-only evidence**: build external end-to-end DAG runner; collect timings, allocations, CPU/memory profiles and Go runtime trace; test correctness.
- **P2 – eBPF evidence**: isolate Linux VM, validate permissions and kernel capabilities, trace kernel scheduling/syscalls/page faults, measure tracing overhead.
- **P3 – Candidate comparison**: generate alternative implementations in PoC only; compare A/B/A/B paired trials in fixed, randomized order.
- **P4 – Added-value test**: blind two evaluations (Go-only vs Go+eBPF), compare explanations and choices on independent held-out workloads; report positive, negative, or inconclusive result.

See [protocol](docs/PROTOCOL.md) and [acceptance](docs/ACCEPTANCE.md).

This repository is **not** a kernel performance autotuner and does not claim eBPF directly observes Go goroutines.
