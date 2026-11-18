# eBPF Agent Performance Evidence PoC

**Status: E001 eBPF feasibility PASS; E005 corrected kernel measurement PASS; extra implementation-ranking value NOT DEMONSTRATED. Final PoC hypothesis remains OPEN.**

## 처음 해보는 eBPF: GitHub에서 Hello World 보기

커널에서 나온 **`Hello World!`**를 GitHub Actions 로그와 실행 요약 화면에서 확인할 수 있는 학습용 실험을 제공함.

- **[수정 후 성공한 실행·Summary 보기](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44311402173/attempts/1)** — 기본 Hello World 메시지 1건 수신과 CPU 0~3의 반복 검사 **8/8 통과**를 확인함.
- 같은 검증 러너에서 기존 연결 방식의 CPU별 메시지 누락을 재현하고 raw tracepoint 방식의 수신을 확인함. [CPU별 대조 결과와 검증 환경](docs/experiments/H001-CPU-REGRESSION.md)에 기록함.
- [Hello World 실행 화면](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/workflows/hello-world.yml)에서 **Run workflow → main → Run workflow**를 선택하여 실행함.
- 완료된 실행의 **Summary**와 **커널에서 Hello World 확인 → Hello World 실행 및 커널 메시지 확인** 로그에서 결과를 확인함.
- [쉬운 설명과 코드 읽는 순서](experiments/hello-world/README.md) · [H001 실험 기록](docs/experiments/H001-HELLO-WORLD.md)

`ebpf-study`의 예제를 이 저장소에 가져와 자동 실행에 맞게 확장함. 성능 실험과 별도로 실행하며, 실제 커널 메시지 수신으로 성공을 판정함.

수정된 최신 코드를 확인하려면 **Run workflow → main**으로 새 실행을 시작해야 함. 기존 실행의 **Re-run jobs**는 해당 실행 당시의 코드로 다시 실행됨.

## Experiment evidence

- [Required experiment record policy](docs/EXPERIMENT_RECORD_POLICY.md) · [new report template](docs/experiments/TEMPLATE.md)
- [E001 — GitHub Actions eBPF capability report, failures and immutable evidence](docs/experiments/2026-10-22-github-actions-ebpf.md)
- [E001 passing Actions run (500 observed getpid calls)](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39749779719)
- [E002–E004 historical results and measurement-method correction](docs/experiments/E004-RESULT.md)
- [E005 corrected experiment, full raw evidence and limitations](docs/experiments/E005-RESULT.md)
- Manually invoke the `eBPF capability probe (manual)` workflow; it does not trigger for untrusted pull requests.

## Hypothesis

Adding independently collected eBPF kernel observations to Go benchmarks,
profiles, and runtime traces may improve decisions between behaviorally equivalent
AI-generated implementations. The PoC must also permit a negative result.

## Hard boundaries

- NEVER modify `HeaInSeo/dag-go` or `HeaInSeo/ebpf-study`.
- Pin the dag-go baseline to exact source commit `1b22842771198ce15714c4da4d496060c11dccb8`.
- No modification to operational supervisor, queues, Notion, or production workers.
- Experimental variants reside here, preserve correctness contracts and are tested against the same workload.
- Keep kernel-observation collection opt-in. No sudo, mount, package installation or kernel tracing without an explicit controlled test environment.

## Stages

- **P0 – Protocol**: predeclare workloads, baseline, environment, measurements, equality conditions and thresholds.
- **P1 – Go-only evidence**: build external end-to-end DAG runner; collect timings, allocations, CPU/memory profiles and Go runtime trace; test correctness.
- **P2 – eBPF evidence**: isolate Linux VM, validate permissions and kernel capabilities, trace kernel scheduling/syscalls/page faults, measure tracing overhead.
- **P3 – Candidate comparison**: generate alternative implementations in PoC only; compare A/B/A/B paired trials in fixed, randomized order.
- **P4 – Added-value test**: blind two evaluations (Go-only vs Go+eBPF), compare explanations and choices on independent held-out workloads; report positive, negative, or inconclusive result.

See [protocol](docs/PROTOCOL.md) and [acceptance](docs/ACCEPTANCE.md).

This repository is **not** a kernel performance autotuner and does not claim eBPF directly observes Go goroutines.

## Framework compatibility experiment (F001)

**PASS: bpftrace, C/libbpf, Go/cilium-ebpf, Rust/Aya and Python/BCC each passed
9/9 exact-count, PID-isolation and BPF-object-cleanup trials (45/45 total).**

- [F001 detailed results, failures, corrections and scope](docs/experiments/F001-RESULT.md)
- [Final GitHub Actions run 39776073689](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39776073689)
- Tested source: `5d45ef49e26b81ab4495ce43fe4ef91959bd643a`.
- [Frozen compatibility protocol](docs/experiments/F001-FRAMEWORK-COMPAT-PROTOCOL.md)
- [Permanently preserved raw evidence](docs/experiments/f001-evidence/)

This confirms the recorded implementation paths and runner/kernel combinations,
not all hooks or kernels. Agent-driven code modification is a future objective;
F001 does not require implementing it. E005's lack of demonstrated ranking gain
and the remaining incremental-value questions are preserved.

## Selective tracing value and resource cost (R001)

Two unchanged manual Actions runs completed 384 timed observations and four
controls. Exact kernel counters and output hashes passed; 2,552 original files
were checksum-verified. Both runs used identical source and target binary, with
Intel/AMD hosted CPUs respectively.

Adding bpftrace to the same Go profiling increased hot-copy elapsed ratios by
11–63% across condition medians, added about 0.57–0.74s per collector invocation,
and used about 102MiB collector peak RSS. These are scoped measurements, not a
universal eBPF overhead estimate. Incremental AI decision quality remains open.

- [R001 first opinion and detailed results](docs/experiments/R001-RESULT.md)
- [Pre-registered protocol](docs/experiments/R001-PROTOCOL.md)
- [Full immutable evidence](docs/experiments/r001-evidence/README.md)

The author's first opinion is to withhold routine fleet-wide adoption and retain
selective diagnostics as a possibility. E006's independent evaluation is not
complete. No operational guardrail or upstream workflow was changed.

