#!/usr/bin/python3
"""bpftrace -c launches this only after attachment; it supplies readiness."""
import ctypes
import os
import signal

parent = os.getppid()
libc = ctypes.CDLL(None, use_errno=True)
if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
    raise OSError(ctypes.get_errno(), "prctl failed")
if os.getppid() != parent:
    raise SystemExit(1)
print("READY", flush=True)
signal.pause()
