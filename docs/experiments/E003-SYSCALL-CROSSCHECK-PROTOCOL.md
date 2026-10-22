# E003 — syscall counting cross-check (pre-registered)

## Why this experiment was added
E002 finished successfully, but a subset of buffered-copy records showed
zero or unexpectedly few sys_enter_write events even though SHA-256 file
verification passed. This mismatch is a **measurement validity concern**.
E002 selection and sealed holdout results will not be rewritten or re-scored.

## Hypothesis and test
One Ubuntu-24.04 GitHub-hosted Actions job will run the same unchanged
dag-go-based child binary against deterministic 8 × 8 MiB input files
(chain DAG, 2 concurrent workers). Execute readall, buffered and optimized
on distinct output directories. Each execution must pass SHA-256 equality.

For each variant run separately:
1. sudo bpftrace attached to raw_syscalls:sys_enter, filtered by pid == cpid.
   Capture numeric syscall IDs (0 read, 1 write, 18 pwrite64,
   20 writev, 326 copy_file_range on Linux x86_64).
2. strace -f -c on the same binary, input and topology, record counts
   for read, write, pwrite64, writev, pwritev, copy_file_range, openat, close.

These are **separate executions** under different measurement tools.
Counts may differ due to runtime startup and timing; no exact matching
threshold is assumed. Gross path inconsistencies must be reported.

## Interpretation
If a syscall family appears in strace but never in raw eBPF for the
same variant and same workload, treat prior kernel counters as partial/
uncertain until the filter/program semantics are understood.
Do not conclude performance superiority from counts alone.
Store raw stdout/stderr, repository SHA and tool/kernel versions,
GitHub Actions URL and result JSON. Preserve any failure.
