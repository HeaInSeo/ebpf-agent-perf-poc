# F001 implementation

See [pre-registered protocol](../../docs/experiments/F001-FRAMEWORK-COMPAT-PROTOCOL.md).
Invoke the manual `eBPF framework compatibility (manual)` Actions workflow.
The workflow alone installs dependencies and runs privileged probes on disposable
GitHub-hosted x86_64 runners. Do not run probes on an operational host.

`target.c` supplies deterministic syscall batches. `probe.py` owns readiness,
negative PID control, exact-count assertions and BPF object lifetime checks.
`counter.bpf.c` is shared by the libbpf and cilium loaders. Aya has a separate
Rust kernel program; BCC and bpftrace compile their own equivalent programs.

Artifacts retain setup/build logs even when compilation or attachment fails.
This suite deliberately does not estimate performance or implement agent-driven
code modification. A table of attempted paths and exact limitations is the
deliverable.
