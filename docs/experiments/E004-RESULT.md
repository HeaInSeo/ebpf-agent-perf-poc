# E004 result — FAIL (same-run typed syscall undercount)

- GitHub Actions: [run 39754465616](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39754465616)
- Source SHA: 8c2ac0047d3796dbb334a61f40a7ed495db3a3e9
- Date: 2026-10-22, UTC 09:19
- Context: Ubuntu 24.04, Linux 7.0.0-1017-azure; Go 1.25.5.
- Scenario: buffered, chain DAG, 8 × 8 MiB, 2 workers.
- All eight files were written and verified by SHA-256 before the assertion.

| Event | Typed tracepoint | Raw syscalls tracepoint |
| --- | ---: | ---: |
| read | 2067 | 2067 |
| write | **1** | **2049** |
| copy_file_range | 0 | 0 |

**Verdict: FAIL.** Two eBPF tracing methods attached before one child run
report dramatically different write counts. The assertion stopped the workflow
without continuing to the other variants; this behavior is intentional.
E003's independent strace observed write=2049 for the same workload variant,
supporting the raw count and calling the typed-write data into question.

The exact underlying kernel/tracepoint implementation cause remains unknown.
No assertion of a universal kernel bug or bpftrace bug is justified.
E002's typed-write counts cannot be used as reliable Go+eBPF evidence.
A full rerun with independently checked raw syscall IDs is required
([E005 plan](E005-RAW-RETEST-PROTOCOL.md)). Previous measurements and
sealed choices must not be overwritten.

[Preserved failed attempt stdout/stderr and hashes](e004-evidence/).
