# E005 — raw syscall counter corrected rerun (pre-registered)

## Trigger / corrective scope
E004 run 39754465616 found the same child process had
typed-write=1 but raw-write=2049, while both read counters=2067.
The cause inside kernel/tracepoint instrumentation is not established.
Therefore E002's typed sys_enter_write counts are NOT accepted as
reliable evidence for event density or candidate selection.

## Controlled correction
Change only the E002 bpftrace collection string from typed sys_enter
probes to independently cross-checked raw_syscalls:sys_enter probes.
Filter pid==cpid and x86_64 syscall IDs:
read 0; write 1; close 3; openat 257; copy_file_range 326.
Require x86_64 host and the raw tracepoint to be present.

No change to:
- the pinned dag-go upstream commit;
- Go source candidate semantics;
- train and holdout workload sizes/seeds/worker limits;
- 10 native runs, 5 traced runs and one Go profile per variant/case;
- the seal-train-before-holdout order;
- Go-only and combined evidence selection formulas or thresholds.

Use the existing manual GitHub Actions experiment workflow with fresh run ID
and source SHA. Retain E002 and E004 failures and raw logs without alteration.

## Pass / limits
PASS for E005 execution requires all tests and output SHA-256 checks,
positive expected raw syscall events, 10/5 samples, sealed choices,
heldout evaluation, complete artifact upload.
E005 does not automatically prove added value: report the sealed verdict,
including no improvement or inconclusive. E003 establishes the accuracy
of raw ID counts on three separately executed variants; E005 itself
does not run strace on every sample. This is Linux x86_64 only.
