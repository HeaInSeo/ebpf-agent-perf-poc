# Frozen experimental protocol (v0)

## Research question
Can eBPF observations cause *more accurate implementation choices or root-cause diagnoses* than Go benchmark + pprof + trace alone, for equal DAG execution contracts?

## Baseline
Upstream: https://github.com/HeaInSeo/dag-go
Pinned commit: 1b22842771198ce15714c4da4d496060c11dccb8.
Obtain with `git clone`, `git checkout <sha>` into isolated ephemeral workspace.
No fork/PR/patch to upstream is allowed.

## Workloads
Use one external harness, no internal dag-go instrumentation changes.
Pre-register chain, fanout/fanin, wide/deep, and one cancellation/error scenario.
Use deterministic fixed work per node, and vary number of nodes and worker concurrency.
Exclude setup/warmup from steady-state timing; separately measure whole-process costs.
Verify every node executed exactly once on successful cases; verify cancelled/error semantics.

## Metrics
- Primary: run duration distribution, completed nodes/sec, correct completion.
- Go: CPU pprof, heap allocations and peak RSS (external OS accounting), runtime execution trace.
- eBPF: per-TID kernel scheduling delay, syscalls/count and latency, voluntary/involuntary context switches where supported, page-fault events.
- OS metadata: CPU, Go version, kernel, filesystem/cgroup limits, governor, host load, BTF/tool versions.
- eBPF overhead: baseline/no instrumentation, Go-only, and Go+eBPF for each condition.

## Method
Warmup then paired interleaved runs on a dedicated VM. Fix GOMAXPROCS and constraints.
Record full upstream commit and PoC commit, build flags, artifacts, workload seed,
tracing configuration and raw outputs. Analyze run-to-run noise; avoid hardcoded 10%
improvement claims or external historic ns/op as a control.
Candidate code is acceptable only after functional/race/cancellation checks.
Establish a minimum meaningful performance difference from baseline variance.
Use held-out workload configurations to check generalization.
Distinguish kernel thread scheduling from Go goroutine scheduler.
Never infer CPU/memory improvement from syscall counts alone.

## Blinded incremental value
Prepare two evidence packages for the same candidates: (A) Go-only and (B)
Go+kernel. Do not reveal holdout outcomes to the evaluator. Require a ranked
decision and falsifiable bottleneck hypotheses for each package. Evaluate both
against independent repeated holdout measurements.
Mark eBPF 'value added' only if B meaningfully improves selection/explanation
beyond variance, with correct attribution and controlled tracing overhead.
Otherwise record NEGATIVE or INCONCLUSIVE honestly.

## Early stop
Wrong semantics, unknown upstream SHA, unsafe environment, noisy shared CPU,
incomplete eBPF evidence, privilege issues, or changing workloads -> BLOCKED.
