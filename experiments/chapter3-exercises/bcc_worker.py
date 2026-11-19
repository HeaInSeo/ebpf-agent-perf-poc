#!/usr/bin/env python3
"""Root-only BCC examples kept alive while a separate bpftool process inspects them."""
import argparse
import ctypes as ct
import json
import os
from pathlib import Path
import signal
import time
from bcc import BPF

MAP_SOURCE = r"""
BPF_HASH(counter_table, u64, u64, 128);
int hello(struct pt_regs *ctx) {
    u64 uid = bpf_get_current_uid_gid() & 0xffffffff;
    u64 zero = 0;
    u64 *counter = counter_table.lookup_or_try_init(&uid, &zero);
    if (counter) __sync_fetch_and_add(counter, 1);
    return 0;
}
"""

TAIL_SOURCE = r"""
BPF_PROG_ARRAY(jump, 512);
BPF_ARRAY(hits, u64, 3);
static __always_inline void bump(u32 slot) {
    u64 *count = hits.lookup(&slot);
    if (count) __sync_fetch_and_add(count, 1);
}
int hello(struct bpf_raw_tracepoint_args *ctx) {
    u32 tgid = bpf_get_current_pid_tgid() >> 32;
    if (tgid != TARGET_TGID) return 0;
    u32 syscall_nr = ctx->args[1];
    jump.call(ctx, syscall_nr);
    return 0;
}
int ignore_opcode(struct bpf_raw_tracepoint_args *ctx) {
    bump(0);
    return 0;
}
int hello_exec(struct bpf_raw_tracepoint_args *ctx) {
    bump(1);
    return 0;
}
int hello_timer(struct bpf_raw_tracepoint_args *ctx) {
    bump(2);
    return 0;
}
"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("map", "tail"), required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--counts", type=Path, required=True)
    args = parser.parse_args()
    running = True

    def stop(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    if args.mode == "map":
        b = BPF(text=MAP_SOURCE)
        b.attach_kprobe(event=b.get_syscall_fnname("execve"), fn_name="hello")
        expected = ["hello"]
    else:
        if os.uname().machine != "x86_64":
            raise RuntimeError("tail-call syscall numbers require x86_64")
        b = BPF(text=TAIL_SOURCE.replace("TARGET_TGID", str(os.getpid())))
        ignore = b.load_func("ignore_opcode", BPF.RAW_TRACEPOINT)
        execute = b.load_func("hello_exec", BPF.RAW_TRACEPOINT)
        timer = b.load_func("hello_timer", BPF.RAW_TRACEPOINT)
        prog_array = b.get_table("jump")
        # x86_64: uname=63, getpid=39, gettid=186
        prog_array[ct.c_int(63)] = ct.c_int(ignore.fd)
        prog_array[ct.c_int(39)] = ct.c_int(execute.fd)
        prog_array[ct.c_int(186)] = ct.c_int(timer.fd)
        b.attach_raw_tracepoint(tp="sys_enter", fn_name="hello")
        expected = ["hello", "ignore_opcode", "hello_exec", "hello_timer"]

    args.ready.write_text(json.dumps({"pid": os.getpid(), "expected": expected}) + "\n")
    print(f"READY mode={args.mode}, pid={os.getpid()}, loaded={expected}", flush=True)
    libc = ct.CDLL(None)
    while running:
        if args.mode == "tail":
            os.getpid()
            libc.syscall(186)
            os.uname()
        time.sleep(0.05)

    if args.mode == "map":
        counts = {str(key.value): int(value.value)
                  for key, value in b["counter_table"].items()}
    else:
        values = {int(key.value): int(value.value)
                  for key, value in b["hits"].items()}
        counts = {"uname": values.get(0, 0),
                  "getpid": values.get(1, 0),
                  "gettid": values.get(2, 0)}
    args.counts.write_text(json.dumps(counts, sort_keys=True, indent=2) + "\n")
    print(f"COUNTS mode={args.mode} {counts}", flush=True)

if __name__ == "__main__":
    main()
