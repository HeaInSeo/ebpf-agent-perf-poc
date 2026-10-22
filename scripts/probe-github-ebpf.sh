#!/usr/bin/env bash
# Validates real eBPF load, tracepoint attach, and target process event collection.
# No privileged containers, permanent BPF attachments, or upstream repository edits.
set -Eeuo pipefail
OUT="results/actions-ebpf-probe"
mkdir -p "$OUT"
trap 'printf "exit=%d\n" "$?" > "$OUT/exit-status.txt"' EXIT

{
  echo "utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "runner_os=${RUNNER_OS:-unknown}"
  echo "runner_image=${ImageOS:-unknown}"
  echo "runner_image_version=${ImageVersion:-unknown}"
  echo "repository_sha=${GITHUB_SHA:-unknown}"
  echo "kernel=$(uname -srvm)"
  echo "architecture=$(uname -m)"
  echo "uid=$(id -u)"
  echo "cpus=$(nproc)"
  if test -r /sys/kernel/btf/vmlinux; then echo "btf=present"; else echo "btf=not-readable"; fi
  for setting in /proc/sys/kernel/unprivileged_bpf_disabled /proc/sys/kernel/perf_event_paranoid; do
    if test -r "$setting"; then echo "${setting}=$(cat "$setting")"; fi
  done
} | tee "$OUT/environment.txt"

if ! command -v bpftrace >/dev/null 2>&1; then
  echo "Installing bpftrace on this disposable runner"
  sudo apt-get update -qq
  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends bpftrace
fi
bpftrace --version | tee "$OUT/bpftrace-version.txt"

echo "Checking for sys_enter_getpid tracepoint"
sudo bpftrace -l 'tracepoint:syscalls:sys_enter_getpid' | tee "$OUT/tracepoints.txt"
grep -Fxq 'tracepoint:syscalls:sys_enter_getpid' "$OUT/tracepoints.txt" || {
  echo "FAIL: required tracepoint not available" | tee "$OUT/verdict.txt"
  exit 1
}

echo "Attaching eBPF tracepoint and issuing target getpid() syscalls"
# -c starts a child *after* BPF programs are loaded/attached. cpid restricts
# the map to that child so unrelated runner processes cannot pass the test.
# timeout makes hangs observable instead of consuming the job indefinitely.
set +e
timeout -s INT -k 5s 40s sudo bpftrace -q \
  -c "/usr/bin/python3 scripts/probe-getpid-target.py" \
  -e 'tracepoint:syscalls:sys_enter_getpid /pid == cpid/ { @target_getpid = count(); }' \
  > "$OUT/trace.log" 2> "$OUT/trace-stderr.log"
rc=$?
set -e
printf "bpftrace_exit_code=%d\n" "$rc" | tee "$OUT/bpftrace-exit.txt"
cat "$OUT/trace.log"
cat "$OUT/trace-stderr.log"
if [ "$rc" -ne 0 ]; then
  echo "FAIL: bpftrace did not complete successfully (load/attach/run)" | tee "$OUT/verdict.txt"
  exit 1
fi
python3 - "$OUT/trace.log" "$OUT/verdict.txt" <<'PY'
import pathlib
import re
import sys
log = pathlib.Path(sys.argv[1]).read_text()
m = re.search(r"(?m)^@target_getpid:\s*(\d+)\s*$", log)
if not m or int(m.group(1)) < 1:
    result = "FAIL: no target-process getpid tracepoint events observed"
    pathlib.Path(sys.argv[2]).write_text(result + "\n")
    sys.exit(result)
result = f"PASS: eBPF loaded, attached to syscall tracepoint, collected {m.group(1)} target getpid events"
pathlib.Path(sys.argv[2]).write_text(result + "\n")
print(result)
PY
