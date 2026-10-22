# E003 — raw eBPF syscall count vs strace (PASS)

- [GitHub Actions run 39754004777](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39754004777)
- Exact source SHA: e6662438c62cdc60cf6c5dc9085017e90c57b407.
- Environment: GitHub-hosted Ubuntu-24.04 x86_64 (see workflow run logs).
- Fixed DAG: chain, 8 nodes, each file 8 MiB, 2 workers.
- 3 variants × two **separate** tracing methods, every output verified SHA-256.

| Variant | Evidence | raw eBPF syscall ID count | strace -f count |
|---|---|---: | ---: |
| buffered | write (ID 1) | 2049 | 2049 |
| buffered | read (ID 0) | 2067 | 2067 |
| readall | write (ID 1) | 10 | 10 |
| readall | read (ID 0) | 308 | 308 |
| optimized | copy_file_range (ID 326) | 16 | 16 |
| optimized | read (ID 0) | 11 | 11 |

**PASS for the specific cross-check:** independently run syscall observation
methods show matching counts for the main I/O paths. This also demonstrates
that Go io.Copy selects kernel copy_file_range under the tested conditions.

This does not establish exact equivalence for all syscalls or all executions
and does not validate E002's *typed* write tracepoint. E004 follows up with
same-run typed-vs-raw measurement and finds an important mismatch.

- [Pre-registered protocol](E003-SYSCALL-CROSSCHECK-PROTOCOL.md).
- [Raw stdout/stderr, summary and SHA-256 manifest](e003-evidence/).
