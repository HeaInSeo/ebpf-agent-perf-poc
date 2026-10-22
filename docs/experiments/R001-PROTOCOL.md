# R001 — selective tracing: incremental information and resource cost

Pre-registered before any R001 Actions run. This is a first-stage cost and
information ablation, not completion of E006's independent AI evaluation.

## Question and scope

Does adding one bpftrace collector to an existing Go file-copy operation provide
information useful enough to justify additional CI resources? The operation is
the explicit read/write copy path in `cmd/iobench`, isolated without the DAG
scheduler. It is an agent-written synthetic microbenchmark, not a production
repo audit. All historical E001–E005/F001 evidence remains unchanged.

Candidate A uses a 32KiB reusable buffer; B uses 64KiB. Both must produce identical
bytes and preserve error/cancellation behavior. No change to upstream repos.
Context: warm-cache sequential regular-file copies, throughput priority, one
worker, GOMAXPROCS=2, no fsync/durability claim. Buffer memory is 32/64KiB,
both within a predeclared 128KiB copy-buffer budget. RSS is measured, not capped.

## Fixed acquisition

| Case | File bytes | Copies per trial | Use |
|---|---:|---:|---|
| small | 131072 | 2048 | acquisition |
| large | 16777216 | 32 | acquisition |
| small-holdout | 196608 | 2304 | native validation only |
| large-holdout | 12582912 | 48 | native validation only |

Use 12 rounds per acquisition case/candidate/mode and 12 rounds per holdout
case/candidate. Seed 20261022. Shuffle candidate and mode order within rounds;
all modes execute the same immutable binary and data. Warm up each candidate
before each case, outside scored observations. No cache dropping, CPU affinity,
load injection or result-dependent workload tuning. One Ubuntu 24.04 x86_64
GitHub-hosted job, manual only, maximum 20 minutes. No five-framework matrix.

Three modes: native; Go CPU pprof + runtime trace; the exact same Go profiling
plus eBPF. Both assessment packages receive native timings, CPU/allocation
metrics, pprof and runtime trace and full candidate source. The second adds
eBPF counters, syscall return bytes and syscall elapsed sums. Go is not weakened
to timing-only. Separately compare Go profiling versus native to expose its cost.

The target opens input/output before READY and blocks until GO. The collector
attaches before GO and filters target TGID and the actual input/output FDs.
Only raw_syscalls enter/exit is used for read/write; sched_process_exit ends
collection. Map aggregation, no per-event userspace streaming. All target FDs
remain open until exit. Exact expected read/write counts and returned bytes
are checked in every traced trial, including EOF reads; output SHA256 is checked
after every trial. Zero and non-buffer-aligned positive controls precede study.
Nonempty stderr, lost events, count/byte mismatch or semantic mismatch stop it.

## Measurements and judgments fixed in advance

Record hot-path wall/CPU/allocations; whole-process wall and CPU; target and
collector maximum RSS separately; collector setup time and total lifetime;
artifact bytes. RSS is the maximum of each process, not a summed process-tree
peak. `/usr/bin/time` CPU accounts for the measured command and waited children.
Report both percentages and absolute costs. Include workflow total/setup/test
durations separately; no monetary or monthly fleet extrapolation.

Bootstrap 95% CI (10000 resamples, fixed seed) for paired median hot-path ratios
within round. Report median full-command wall differences. Ratios are eBPF+Go
divided by Go, and Go divided by native. No claim of zero overhead from a
statistically unresolved ratio. Practical ranking tie band is 5%: pick the
faster candidate only when the paired 95% CI lies entirely below 0.95 or above
1.05; otherwise ABSTAIN. Seal this Go-only choice before running holdout.
Kernel event count alone is not a quality score or valid tie-break for throughput.
Native holdout establishes whether the acquisition choice generalizes, not a
universal implementation winner. Both packages share this timing rule; any
change in judgment must be justified separately, not manufactured by a rule.

Information gain requires a correct, falsifiable observation not already
available in source or the Go package. More detailed counters alone do not
count as better diagnosis or selection. Preserve native/Go artifacts so an
independent evaluator can later challenge the first opinion.

Preliminary deployment view: routine CI needs demonstrated incremental decision
benefit and acceptable measured cost; on-demand diagnostics may remain a
candidate if kernel attribution is reliable. A same-choice outcome is not proof
that eBPF is useless. Unreliable measurements are INCONCLUSIVE, never PASS.

Limits: one author knows both implementations, no independent/blinded AI
evaluators, one hosted VM, cached regular files, no real application regression,
no autonomous edits. G6/E006 remain open regardless of R001 execution success.
