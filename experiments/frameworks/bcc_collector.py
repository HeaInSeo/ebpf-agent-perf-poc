#!/usr/bin/python3
import ctypes
import json
import signal
import sys
from bcc import BPF

pid = int(sys.argv[1])
if not 0 < pid < 2**32:
    raise ValueError("invalid PID")
signals = {signal.SIGINT, signal.SIGTERM}
signal.pthread_sigmask(signal.SIG_BLOCK, signals)
source = r'''
#include <uapi/linux/ptrace.h>
BPF_ARRAY(COUNTS, u64, 1);
TRACEPOINT_PROBE(raw_syscalls, sys_enter) {
    if ((bpf_get_current_pid_tgid() >> 32) != TARGET || args->id != 39) return 0;
    u32 key = 0;
    u64 *value = COUNTS.lookup(&key);
    if (value) __sync_fetch_and_add(value, 1);
    return 0;
}
'''.replace("TARGET", str(pid))
bpf = BPF(text=source)
try:
    print("READY", flush=True)
    signal.sigwait(signals)
    value = bpf["COUNTS"][ctypes.c_int(0)].value
finally:
    bpf.cleanup()
print(json.dumps({"observed": value}), flush=True)
