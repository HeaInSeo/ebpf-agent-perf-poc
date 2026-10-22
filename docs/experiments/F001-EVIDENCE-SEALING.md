# F001 evidence sealing correction

During evidence review, the initial harness checksum manifest was found to
include `probe.log` while the outer workflow's tee still had that file open.
The final summary line can therefore change that log after the hash is read.
The initial manifest also precedes provenance and lock-file copies.

This affects artifact sealing, not the collector counts or their raw trial
records. Preserve the original manifests and report any mismatches. Never
rewrite downloaded artifact bytes to match an earlier checksum.

The final workflow seals every artifact file after the probe process, tee,
and provenance-copy step have exited. It also rejects changed committed
dependency lock files. The final confirmation uses a fresh source/run.

For archived earlier attempts, create a separate ARCHIVE-SHA256SUMS.txt over
the byte-for-byte downloaded files and keep the original SHA256SUMS.txt too.
