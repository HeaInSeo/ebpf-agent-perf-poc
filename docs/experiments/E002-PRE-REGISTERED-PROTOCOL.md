# E002 — dag-go candidate comparison (pre-registered)

**Status: planned; this document is written before the hosted E002 experiment.**

## Research question
Does syscall-level eBPF evidence improve a predeclared implementation-selection
rule compared with Go-only timing/profiling, on held-out workloads? The upstream
dag-go source is unchanged, pinned to commit
1b22842771198ce15714c4da4d496060c11dccb8.

## Three candidates (in the new PoC only)
- readall: entire file into a slice, write entire file.
- buffered: explicit 32-KiB bounded read/write loop.
- optimized: io.Copy between two *os.File handles (may use copy_file_range).
All variants are scheduled by the same dag-go engine, with equal topology,
worker caps, independent file per node, and exact SHA-256 output verification.
Tests must pass for both chain and fanout; pre-cancelled and missing-input cases
must not silently succeed. Immediate cancellation during one large copy is
not guaranteed equivalent and is outside the comparison.

## Fixed training and withheld test configurations

| Case | Phase | Nodes | Bytes/file | Workers | Topology |
|---|---|---:|---:|---:|---|
| train-small | train | 12 | 65536 | 4 | fanout |
| train-large | train | 8 | 2097152 | 4 | fanout |
| holdout-wide | withheld | 24 | 1048576 | 8 | fanout |
| holdout-deep | withheld | 8 | 8388608 | 2 | chain |

Inputs: deterministic repeated 16-KiB pseudo-random chunks seeded with
20261022 + file index. Build, input setup, file SHA-256 verification and
cleanup are excluded from per-DAG Go elapsed time. No fsync/durability claim.
## Environment and evidence

- Manually started GitHub-hosted Ubuntu 24.04 job, read-only GitHub token.
- Fixed GOMAXPROCS=4; record host, kernel, BPF tool, Go and exact source SHA.
- Warm up every variant once per case, verifying outputs; exclude warmups.
- Repeat untraced native 10 times per candidate/case and eBPF traced 5 times
  paired with the first five native runs; random candidate order with fixed seed.
- One separate CPU pprof and runtime trace per candidate/case (adds overhead).
- Observe tracepoint counts for read, write, openat, close, copy_file_range
  filtered to the Go process PID. eBPF counts include program startup and
  shutdown; Go duration times only DAG Start-to-Wait. **Never compare the two
  as measurements of the exact same time interval.**
- Capture Go total allocated bytes, GC cycles, process peak RSS, duration.
- Quantify tracing cost by eBPF/native median Go duration ratio per case.
- Preserve raw stdout, syscall maps, full experiment JSONL, profiler traces
  and original GitHub run artifacts. Shared runner contention and cache
  effects are uncontrolled and may invalidate performance claims.

## Sealed selection rule (does not look at held-out outcomes)

1. Normalize each training case's native median latency by the fastest
   candidate. Average equal-weight normalized ratios for each candidate.
2. Go-only choice is minimum resulting relative latency score.
3. Combined evidence begins with the same timing score; among candidates
   within 5% of the Go-only score it chooses the minimum mean value of
   (read + write + copy_file_range events) / native-median-ns across training.
4. Write both choices to sealed-predictions.json **before** running holdout.
5. Holdout score is mean normalized native median latency across the two
   unseen cases. Percent regret is the excess versus best heldout score.
6. Exploratory positive requires >max(5 percentage points, 200 * maximum
   native heldout CV) lower regret, maximum heldout CV <=15%, and BPF/native
   training duration median ratio 0.75..1.20. Negative for robust reverse;
   otherwise INCONCLUSIVE or NO_ADDITIONAL_RANKING_VALUE_DEMONSTRATED.

The evaluator is a deterministic rule, NOT an independently blinded AI
developer agent. It demonstrates an evidence-based comparison pipeline,
not that an actual agent has become more effective.

## Stops and untested territory

Abort on any incorrect digest, failed run, unavailable syscall tracepoint,
missing profile or missing training samples. A failure and its corrective
rerun remain documented with separate immutable GitHub URLs and SHAs.

Outside E002: fully controlled dedicated CPU/kernel, scheduler tracepoints,
per-syscall latency, exact separation of app startup and execution kernel
events, a blind independent human/AI reviewer, richer error/cancel semantics.
The final report must explicitly mark any unproven area without inventing PASS.
