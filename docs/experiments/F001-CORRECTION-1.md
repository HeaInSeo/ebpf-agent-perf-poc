# F001 correction 1 — registered before second run

First run: https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39774887636
Source: f12a3aaa059c0e29d2736580ef2a23ab1b2309e6.
libbpf and cilium passed all nine trials; three paths need bounded corrections.

1. BCC: our file `bcc.py` shadowed the installed `bcc` package. Rename it
   `bcc_collector.py`. This was an import defect, not a BCC/kernel limitation.
2. bpftrace: raw stdout actually contained `@events: 500` followed by
   `@events: 0`: explicit END print/clear plus automatic exit printing created
   two snapshots, and our parser selected the last. Remove explicit print/clear;
   reject multiple snapshots. Also use a `-c` child readiness helper so the
   measured target starts only after attachment, without depending on BEGIN.
3. Aya: the pinned Rust BPF target did not expose AtomicU64::fetch_add.
   Use CPU-local counters (PERCPU_ARRAY) and sum all CPU values in userspace.
   The declared target remains single-threaded. This does not validate general
   shared-counter atomics, reentrant probes or multi-thread counting in Rust.

Retain original failed logs and outputs. Thresholds, workloads, PID controls,
repeat count and cleanup requirements are unchanged. This is a new source/run,
not a rewrite or reinterpretation of the first run as PASS.

Freeze Cargo.lock from the first artifact resolution and the verified Go module
checksums. Subsequent builds use Cargo --locked and Go -mod=readonly. Ubuntu
package versions and runner images remain recorded environmental inputs.
