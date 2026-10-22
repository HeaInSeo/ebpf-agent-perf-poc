# Experiment E001 — GitHub Actions eBPF capability

## Goal and scope

Can an unmodified GitHub-hosted `ubuntu-24.04` runner load an eBPF
tracepoint program, attach it, and collect events belonging to a launched
child process? No dag-go execution or performance claims are in scope.

- Trigger: manual `workflow_dispatch`, minimal `contents: read` token.
- Workflow: [ebpf-capability.yml](../../.github/workflows/ebpf-capability.yml)
- Probe: [probe-github-ebpf.sh](../../scripts/probe-github-ebpf.sh)
- Workload: [probe-getpid-target.py](../../scripts/probe-getpid-target.py)
- Pass: tracepoint exists, program exits normally after attach, positive
  `getpid` counter from the targeted child PID. Clean process exit alone is
  insufficient; zero events is failure.

## Attempt 1 — FAIL (test harness quoting)

- UTC: 2026-10-22 08:39:18Z (KST 17:39:18).
- Commit: `d5e6bb41fb67b1851d0e4eda698cb4028c8a1614`.
- [Actions run 39749329292](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39749329292).
- Runner image `ubuntu24` version `20261018.339.1`.
- Kernel `7.0.0-1017-azure` x86_64; BTF present.
- Unprivileged BPF disabled=2; perf paranoid=4; run with sudo.
- `bpftrace v0.20.2`; tracepoint `syscalls:sys_enter_getpid` found.
- Bpftrace process exit=0, but `@target_getpid: 0`; no useful events.
- Python target stderr: `SyntaxError: unterminated string literal`.
- Root cause: nested quotes within bpftrace `-c` were not preserved, so
  Python could not execute the specified workload. This is a harness defect,
  **not proof that GitHub-hosted runner cannot run eBPF**.
- Correction: commit a standalone Python target and launch via
  `-c "/usr/bin/python3 scripts/probe-getpid-target.py"`.

## Follow-up runs

Recorded after a fresh workflow execution; each attempt requires exact commit,
timestamp, run URL, kernel/tool versions, actual positive/zero event counts,
verdict, and if needed diagnosis and correction. Never overwrite an earlier
attempt's observation to make the history appear clean.

## Interpretation, safety and preservation

- A passing syscall tracepoint experiment proves only basic eBPF loading,
  attachment and event collection on that specific hosted runner.
- It does not establish other eBPF program types, Go goroutine visibility,
  performance measurement accuracy, stable runners, or incremental value over
  Go profiling. Those must be evaluated separately.
- Artifact upload uses 14-day retention for raw stdout, stderr, environment,
  verdict and exit code; exact run URL and source commit remain in this report.
- No sudo privilege is escalated outside the disposable GitHub-hosted job,
  and no upstream source repo or production service is modified.
