#!/usr/bin/env python3
"""Seal the complete artifact only after all writers and metadata steps exit."""
import hashlib
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve(strict=True)
if not root.is_dir():
    raise ValueError("evidence directory required")
lines = []
for path in sorted(root.rglob("*")):
    if path.is_symlink():
        raise ValueError(f"unexpected evidence symlink: {path}")
    if path.is_file() and path != root / "SHA256SUMS.txt":
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root)}")
(root / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n")
print(f"sealed {len(lines)} evidence files")
