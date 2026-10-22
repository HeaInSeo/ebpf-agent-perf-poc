# eBPF Agent Performance Evidence PoC

**Status: E001 eBPF feasibility PASS; E005 corrected kernel measurement PASS; extra implementation-ranking value NOT DEMONSTRATED. Final PoC hypothesis remains OPEN.**

## Experiment evidence

- [Required experiment record policy](docs/EXPERIMENT_RECORD_POLICY.md) · [new report template](docs/experiments/TEMPLATE.md)
- [E001 — GitHub Actions eBPF capability report, failures and immutable evidence](docs/experiments/2026-10-22-github-actions-ebpf.md)
- [E001 passing Actions run (500 observed getpid calls)](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39749779719)
- [E002–E004 historical results and measurement-method correction](docs/experiments/E004-RESULT.md)
- [E005 corrected experiment, full raw evidence and limitations](docs/experiments/E005-RESULT.md)
- Manually invoke the `eBPF capability probe (manual)` workflow; it does not trigger for untrusted pull requests.

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

## Framework compatibility experiment (F001)

**PASS: bpftrace, C/libbpf, Go/cilium-ebpf, Rust/Aya and Python/BCC each passed
9/9 exact-count, PID-isolation and BPF-object-cleanup trials (45/45 total).**

- [F001 detailed results, failures, corrections and scope](docs/experiments/F001-RESULT.md)
- [Final GitHub Actions run 39776073689](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39776073689)
- Tested source: `5d45ef49e26b81ab4495ce43fe4ef91959bd643a`.
- [Frozen compatibility protocol](docs/experiments/F001-FRAMEWORK-COMPAT-PROTOCOL.md)
- [Permanently preserved raw evidence](docs/experiments/f001-evidence/)

This confirms the recorded implementation paths and runner/kernel combinations,
not all hooks or kernels. Agent-driven code modification is a future objective;
F001 does not require implementing it. E005's lack of demonstrated ranking gain
and the remaining incremental-value questions are preserved.
