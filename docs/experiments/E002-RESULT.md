# E002 — initial typed-tracepoint run (historical result, superseded)

- Run: [39753049985](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39753049985)
- Source: 352d27a36e45782f4fdb85bc501ccb5da77aaf4d
- Ubuntu-hosted kernel: 7.0.0-1017-azure; Go 1.25.5; bpftrace 0.20.2.
- Status: all GitHub Actions jobs PASS, file digests PASS, 10 native and
  5 BPF repetitions per variant/case, plus one CPU/runtime profile each.

## Untraced Go execution medians

| Case | readall (ms) | buffered (ms) | optimized (ms) |
| --- | ---: | ---: | ---: |
| train-small | 2.582 | 1.249 | 1.284 |
| train-large | 31.604 | 3.793 | 3.004 |
| holdout-wide | 32.898 | 5.629 | 4.581 |
| holdout-deep | 182.601 | 29.582 | 22.396 |

The sealed Go-only choice was optimized; the combined-rule choice was
also optimized. Holdout regret was 0% for both, so added ranking value
was **not demonstrated**. Median observed BPF/native duration ratio
was 0.988; do not infer tracing accelerates computation from this
noisy measurement. Maximum native holdout CV was 11.37%.

## Critical limitation discovered during post-run verification

The E002 typed sys_enter_write counts were sometimes suspiciously low.
E003 checked raw syscall counts against strace, and E004 demonstrated
a same-process mismatch: typed write=1 vs raw write=2049.
Therefore E002's typed-write counts are **NOT RELIABLE** as evidence
for its kernel-event-density tie breaker. E002 is an immutable
historical experiment, not the final validated kernel comparison.
See [E004 failure](E004-RESULT.md) and [E005 corrective rerun](E005-RAW-RETEST-PROTOCOL.md).
The E002 heldout and sealed choices are not changed retroactively.

## Reproduction

- [Pre-registered protocol](E002-PRE-REGISTERED-PROTOCOL.md).
- [Raw JSONL, environments, sealed predictions, summaries, profiles bundle,
  hashes](e002-evidence/).
- Original downloadable Actions artifact: run 39753049985,
  artifact ID 12415036434 (GitHub retention is limited).
- Per-DAG Go timing excludes process start; BPF syscall counts cover
  full process. Host cache and CPU contention were uncontrolled.
- No independent blind AI evaluation was performed.
