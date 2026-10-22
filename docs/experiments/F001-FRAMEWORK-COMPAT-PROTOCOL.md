# F001 — eBPF implementation paths on GitHub-hosted Actions

Status at registration: NOT RUN. This protocol precedes the first F001 run.

## Authorized question and scope

Can bpftrace, C/libbpf, C + Go/cilium-ebpf, Rust/Aya, and C + Python/BCC
build, load, attach, count accurately and clean up in standard GitHub-hosted
`ubuntu-24.04` x86_64 jobs? This is a capability experiment, not a language
performance benchmark or an autonomous code-improvement implementation.
dag-go, ebpf-study, operational workers and queues remain outside its changes.

The current PoC investigates whether execution evidence could support future
agent collaboration and context-sensitive quality decisions. Actual automated
code modification is not a completion requirement of this experiment.

## Fixed common observation

- Hook: `tracepoint/raw_syscalls/sys_enter` (not BPF_PROG_TYPE_RAW_TRACEPOINT).
- x86_64 getpid syscall ID 39; TGID filter for one explicitly launched process.
- Shared C target uses explicit `syscall(SYS_getpid)` and an idle/start handshake.
- Each collector emits READY after attach. Never start measured calls before it.
- The libbpf and Go loaders share the exact same compiled C BPF object.
- Aya uses Rust BPF code; BCC uses its C frontend; bpftrace uses its DSL.
- C/Go/Aya/BCC aggregate in an ARRAY map; bpftrace uses count aggregation.
- No per-event transport: ring-buffer loss is not a measured capability here.

## Predeclared trials and PASS

Each framework runs three repeats of three cases (nine fresh attachments):

| Case | Selected process batches | Unselected process calls | Expected |
|---|---|---|---|
| zero | none | 137 | 0 |
| single | 500 | 137 | 500 |
| batches | 1, 499, 5000 | 137 | 5500 |

PASS requires build success, a live new BPF program and map after READY,
exact counts in every case, normal collector exit and disappearance of every
introduced BPF program/map after exit. No tolerance, silent skip or missing
result is PASS. A failed build is BUILD_FAIL; not attempted runtime is NOT_RUN.
Stop that framework after its first failed trial, while other jobs continue.

Use separate matrix jobs for installation isolation, not timing comparisons.
Record runner image, kernel/BTF identity, exact source SHA, tool/package versions,
build output, raw collector stdout/stderr, trial JSON, object IDs and checksums.

## Toolchain controls and reproducibility

- cilium/ebpf v0.22.0; Aya userspace 0.13.1; aya-ebpf 0.1.1; libc 0.2.177.
- Rust nightly-2025-09-01 + rust-src; bpf-linker 0.9.15, using rustc LLVM.
- Ubuntu packages are image/repository-resolved; retain installed versions.
- Preserve first dependency resolution locks in artifacts and commit them for
  subsequent locked reruns. Initial transitive resolution is not pre-pinned.
- Every corrective rerun must have a new source SHA/run ID. Keep failed attempts.
- Compilation errors, unavailable matching BCC headers, privileges, verifier,
  attachment, counting and cleanup failures must be distinguished in the report.

## Limits

A passing framework demonstrates only this counter, hook, pinned toolchain and
recorded runner. It does not prove kprobe, fentry/fexit, uprobe, XDP, CO-RE,
portable kernel structure access, scheduling attribution or low overhead.
Neither it nor E005 proves improved agent decisions. E005 results are preserved.
