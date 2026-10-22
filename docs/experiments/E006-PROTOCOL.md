# E006 — pre-registration: does eBPF improve decisions?

**Status: NOT RUN / DESIGN ONLY.** No positive result is assumed.

## Research question

Given two semantically equivalent candidate implementations whose Go-only
performance is close enough to make a choice uncertain, can independently
collected eBPF evidence improve either (a) correct bottleneck diagnosis or
(b) held-out implementation selection, beyond Go profiling alone?

## Preconditions and control

- Keep `dag-go` fixed at `1b22842771198ce15714c4da4d496060c11dccb8`.
- E005's `optimized` victory in all cases is historical and cannot be relabeled.
- Implement candidate changes only in PoC, never in dag-go or ebpf-study.
- Functional equivalence: hash outputs, error and cancel cases, race tests.
- Require a signal detectably above run-to-run variance before scoring choices.
- Compare native, Go profiler and Go+eBPF on same image/runner and fixed workload.
- Use a new Actions run and immutable raw evidence; no rewriting earlier runs.

## Blinded test design

1. Freeze scenario names, CPU/GOMAXPROCS, data seed, repetitions and metric rules.
2. Generate candidate binaries from pinned source; do not allow package changes
   or candidate-specific flags outside the declared controlled variable.
3. Verify equal semantics with race/cancel/error and digest checks first.
4. Capture independent training runs on the same runner in shuffled ABBA order.
5. Prepare anonymized package A: timing, Go pprof and runtime traces only.
6. Prepare anonymized package B: same A plus raw-syscall/kernel evidence.
7. Have independent evaluators record choice, confidence, and falsifiable
   root-cause hypothesis without seeing holdout outcomes or the other package.
8. Freeze both predictions with SHA256 and timestamp before evaluating holdout.
9. Run held-out workloads, replicate results and publish regret and attribution
   accuracy, noise bounds, and tracing overhead.
10. Accept positive result only if B is demonstrably more accurate beyond noise;
    otherwise report NEGATIVE, NO_ADDITIONAL_VALUE, or INCONCLUSIVE.

## Hard stop and boundaries

Block on any semantic mismatch, nonreproducible workload, unstable CPU
measurements, inconsistent syscall counts, nonzero lost events or leakage of
holdout labels to evaluators. Treat Linux thread scheduling and Go goroutine
scheduling separately. E006 does not require claiming all eBPF features work
on GitHub-hosted runners; nonportable tracing must be detected and gated.
