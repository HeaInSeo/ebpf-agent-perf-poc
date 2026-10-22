# R001 immutable evidence

Both runs used source `24a6e4a3ca48a53d0b16bf22882c0a9793c60623`.
ZIPs are byte-for-byte copies of the original GitHub Actions artifacts, including
all native observations, target/collector stdout/stderr, resource files, generated
BPF scripts, raw CPU pprof and runtime traces. Extract each ZIP into its own empty
directory. `SHA256SUMS.txt` inside each ZIP hashes all other original files.

| Run | Original artifact ID | ZIP bytes | SHA256 |
|---|---:|---:|---|
| [39781417174](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39781417174) | 12427281865 | 7278719 | `811b9eeeb22ee57879b621d7122020627d80583860658eaece8e43ba5fb3921f` |
| [39782110137](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39782110137) | 12426768682 | 7033192 | `005dc774d8acd5fac2fdb58dbd35c4abf10e500ddb7d8e661e768dd71b2e91af` |

- [Run 1 complete ZIP](39781417174.zip) / [summary](39781417174/summary.json)
- [Run 2 complete ZIP](39782110137.zip) / [summary](39782110137/summary.json)
- The per-run folders expose selected original text files and Go-only profile
  summaries for review without extracting an archive. Full profiles are in ZIPs.
- `run.json`, `jobs.json` and `job.log` were separately retrieved from GitHub;
  they were not part of the original artifact manifest.
- [Audit](AUDIT.json) is a post-run recalculation by the same author, not a claim
  of independent human/AI review. [Replication decision](REPLICATION-DECISION.json)
  records why the second unchanged run was requested after the first.

After extracting, run:

```sh
python3 experiments/value-cost/audit.py /absolute/run1 /absolute/run2
```

The separately generated `ARCHIVE-SHA256SUMS.txt` covers published ZIPs and text
snapshots, excluding itself. Do not overwrite earlier evidence.
