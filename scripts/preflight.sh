#!/usr/bin/env bash
set -euo pipefail
echo "host=$(hostname) kernel=$(uname -r) arch=$(uname -m)"
echo "go=$(go version)"
for x in bpftool bpftrace clang perf; do command -v "$x" || true; done
test -r /sys/kernel/btf/vmlinux && echo 'BTF=present' || echo 'BTF=missing'
if [ -e /proc/sys/kernel/perf_event_paranoid ]; then
  printf 'perf_event_paranoid='; cat /proc/sys/kernel/perf_event_paranoid
fi
if [ -e /proc/sys/kernel/unprivileged_bpf_disabled ]; then
  printf 'unprivileged_bpf_disabled='; cat /proc/sys/kernel/unprivileged_bpf_disabled
fi
echo "No privilege escalation or tracing performed."
