# E004 — same-run eBPF typed/raw syscall validation (pre-registered)

## Motivation
In E002, typed sys_enter_write counts for large-file variants were sometimes
unexpectedly near zero despite successful output SHA-256 verification.
E003 raw syscall counts matched independent strace -f counts in a **different**
execution. E004 must test both eBPF probes within one identical child process.

## Setup and success condition
Use GitHub-hosted Ubuntu 24.04, same pinned dag-go engine, eight 8-MiB files,
chain DAG, two workers, all three variants, exact SHA-256 outputs.
In a single bpftrace process, attach:
- typed sys_enter_read, sys_enter_write, sys_enter_copy_file_range;
- raw_syscalls:sys_enter filtered respectively by IDs 0, 1 and 326.
Both probes filter pid == cpid and attach before the child starts.
Require nonzero raw read count and exact same-run count equality for each
typed/raw pair; zero counts are allowed only when they agree.
Any mismatch FAILS, even if file outputs match.

## Interpretation
Agreement establishes consistency for these probes on this runner; it cannot
retroactively repair E002's unexpectedly low per-run counters or prove no
lost tracepoints on other kernels. No adjustments are allowed to E002's
sealed training predictions or held-out verdict. Persist full raw outputs,
workflow result, source SHA and run ID; never erase failures.
