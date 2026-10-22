# E005 — corrected raw-syscall eBPF comparison

## Run and protocol

- [Pre-registered E005 protocol](E005-RAW-RETEST-PROTOCOL.md)
- Exact source SHA: `9705aaa6a182e097834a33ceeca6e6c7e2dabca4`
- [GitHub Actions run 39755011283](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39755011283), conclusion SUCCESS.
- Artifact ID: `12415331960` (`dag-go-evidence-39755011283-1`).
- Upstream dag-go pinned at `1b22842771198ce15714c4da4d496060c11dccb8` and unmodified.
- Three candidates: readall, buffered, optimized; two training and two withheld scenarios.
- Per candidate and scenario: 10 native samples, 5 eBPF samples, 1 profiled sample.

## Outcomes

| Assessment | Result |
| --- | --- |
| Sealed Go-only choice | optimized |
| Sealed Go+eBPF choice | optimized |
| Go-only holdout regret | 0% |
| Go+eBPF holdout regret | 0% |
| Regret improvement | **0 percentage points** |
| Maximum holdout native coefficient of variation | 8.90% |
| Median training eBPF/native duration ratio | 1.0264 |

**Verdict: NO_ADDITIONAL_RANKING_VALUE_DEMONSTRATED.**

The 1.0264 ratio is not a precise tracing overhead measurement on shared runners.
A successful pipeline is not proof that eBPF improves implementation selection.

## Evidence and audit

- [Preserved E005 raw evidence](e005-evidence/) includes train/holdout JSONL,
  sealed decisions, summaries, environment, SHA256 checks and CPU/runtime profiles.
- Locally verified every entry in `SHA256SUMS.txt` against retained files.
- Compared the eight plain-text result files byte-for-byte (SHA256) against
  the independently downloaded Actions artifact from run 39755011283;
  all eight matched exactly.
- Historical [E002 result](E002-RESULT.md) is superseded for syscall counts,
  after the [E004 same-run mismatch](E004-RESULT.md).
- [E003 raw syscall vs strace](E003-RESULT.md) validated the corrected method
  on the selected workload cases, but does not prove universal counter accuracy.

## Boundaries and follow-up

- Timing is Go DAG Start-to-Wait; eBPF counters include process startup.
- GitHub-hosted runner caching and noisy neighbor effects were uncontrolled.
- This was a deterministic sealed ranking rule, not an independently blinded AI agent.
- No evidence yet of eBPF-added ranking benefit, syscall timing attribution,
  per-goroutine scheduling insight or causal diagnosis improvement.
- Next experiment should pre-register *ambiguous candidate pairs* and a
  blinded diagnosis test; avoid changing this E005 result retroactively.
