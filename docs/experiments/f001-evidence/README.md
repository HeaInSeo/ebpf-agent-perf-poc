# F001 raw evidence archive

Three byte-preserved Actions artifact snapshots:

- 39774887636: initial run; libbpf/cilium passed, three paths failed.
- 39775718563: corrected run; all five paths passed.
- 39776073689: final run; all five paths and complete artifact sealing passed.

Each run has run.json, archive-validation.json and ARCHIVE-SHA256SUMS.txt.
Framework subdirectories retain the downloaded artifact files without rewriting
original logs, counters or checksum manifests. The first two runs retain the
known probe.log manifest mismatch; final-run manifests match every listed file.
See ../F001-RESULT.md for interpretation and precise limits.
