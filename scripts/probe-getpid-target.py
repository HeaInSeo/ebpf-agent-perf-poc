#!/usr/bin/env python3
"""Process started by bpftrace -c without nested shell quoting."""
import os

for _ in range(500):
    os.getpid()
print("target_getpid_calls=500")
