# eBPF Agent Performance Evidence PoC

이 저장소에는 두 종류의 실험이 있음.

- **eBPF 학습:** GitHub Actions에서 커널 프로그램을 직접 실행하고 결과를 확인함. 처음에는 **H001 → H002** 순서로 진행.
- **성능·가치 검증 PoC:** 커널 관측 정보가 실제 구현 선택에 도움이 되는지 별도 실험으로 평가함. 학습 실험의 PASS와 성능 가설의 입증은 구분함.

**PoC 상태:** E001 eBPF 실행 가능성 PASS, E005 보정된 커널 측정 PASS. 커널 관측이 구현 선택의 품질을 추가로 높인다는 가설은 **입증되지 않음(OPEN)**.

## GitHub에서 바로 실행하기

별도 Linux 서버 설치나 두 번째 터미널 없이, GitHub-hosted Ubuntu 러너에서 커널 프로그램 실행 및 결과 수집 가능.

| 순서 | 학습 내용 | 직접 실행 | 검증된 실행 결과 |
| --- | --- | --- | --- |
| **H001 — Hello World** | 커널 이벤트를 감지하고 메시지 출력 | [Hello World Actions](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/workflows/hello-world.yml) | [8/8 PASS 기록](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44311402173) |
| **H002 — Chapter 3** | XDP 연결·해제, bpftool, tail call, 패킷 차단 | [Chapter 3 Actions](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/workflows/chapter3-exercises.yml) | [4/4 PASS 기록](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44529301680) |

1. 위 표의 **직접 실행** 링크 선택.
2. **Run workflow → Branch: main → Run workflow** 선택.
3. 실행 목록에서 새 실행 선택. **Summary**에서 실험별 PASS/FAIL과 측정값 확인.
4. **Jobs**의 단계별 로그에서 커널에서 나온 실제 출력 확인.
5. **Artifacts**에서 원본 결과 JSON·bpftool 덤프·실행 환경·SHA-256 체크섬 확인.

> **재실행 주의:** 기존 실행의 **Re-run jobs**는 당시의 코드를 다시 실행함. 최신 `main` 코드로 확인하려면 새 **Run workflow** 실행 필요. syscall 카운터와 프로그램 ID는 실행할 때마다 달라질 수 있음.

## H001 — Hello World: 첫 번째 eBPF 실험

커널에서 만들어진 `Hello World!` 메시지를 Actions 로그에서 직접 확인하는 기초 실험.

- [성공 실행](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44311402173): 기본 메시지 1건과 CPU 0~3 반복 검사 **8/8 PASS**.
- 기존 연결 방식의 CPU별 메시지 누락을 재현하고 raw tracepoint 방식의 수신을 확인함. [CPU별 대조 결과](docs/experiments/H001-CPU-REGRESSION.md)에 기록함.
- [H001 쉬운 설명·코드 읽는 순서](experiments/hello-world/README.md) · [H001 실험 기록](docs/experiments/H001-HELLO-WORLD.md)

`ebpf-study`의 예제를 GitHub Actions에 맞게 확장함. 이 학습 실험은 성능 PoC와 별도로 실행함.

## H002 — Chapter 3: XDP와 bpftool 연습문제 4개

『Learning eBPF』 Chapter 3의 Exercises를 커널에서 재현한 실습. 책에 등장하는 호스트 `eth0` 대신 **격리된 임시 가상 인터페이스(veth)** 사용.

| 문제 | 배우는 내용 | 실제로 검사하는 것 |
| --- | --- | --- |
| **EX01 · XDP 연결과 해제** | XDP 프로그램이 패킷을 통과시키는 과정 | `XDP_PASS` 연결 전·후 ping 성공, 연결 해제 후 통신 복원 |
| **EX02 · bpftool로 내부 검사** | 실행 중 eBPF 프로그램과 기계어 확인 | BCC `hello` kprobe의 ID·Map·`xlated` 바이트코드·JIT 덤프 |
| **EX03 · Tail call 분석** | eBPF에서 다른 eBPF 프로그램으로 호출 전달 | `hello`, `ignore_opcode`, `hello_exec`, `hello_timer` 4개 프로그램 및 Map 집계 |
| **EX04 · XDP_ABORTED=0** | XDP 반환값 0이 패킷 차단을 의미하는 이유 | 격리된 veth에서 ping 차단 후 연결 해제 및 통신 복원 |

### 실제 실행 결과

[2026-11-19 main 실행 #44529301680](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44529301680): **4/4 PASS**, 증거 파일 **39개 SHA-256 검증 통과**.

```text
EX01  XDP_PASS 연결 → ping 성공 → 연결 해제 → ping 성공  PASS
EX02  BCC kprobe hello 프로그램과 bpftool 덤프 확인   PASS
      UID 0의 execve 호출: 26회
EX03  raw tracepoint와 tail call 프로그램 4개 확인    PASS
      getpid 93회 / gettid 91회 / uname 91회
EX04  XDP_ABORTED 연결 → ping 차단 → 연결 해제 → 복원 PASS
```

위 수치는 **해당 실행에서 측정한 값**이며 고정된 기대값이 아님. 성공 판정은 코드 컴파일만으로 이루어지지 않음. 실제 커널 부착·패킷/시스템콜 관측·Map 집계·정리 및 복구까지 검사함.

### 실습 코드를 읽는 순서

1. [`xdp_pass.bpf.c`](experiments/chapter3-exercises/xdp_pass.bpf.c) / [`xdp_abort.bpf.c`](experiments/chapter3-exercises/xdp_abort.bpf.c) — XDP_PASS와 XDP_ABORTED의 차이
2. [`xdp_isolated.sh`](experiments/chapter3-exercises/xdp_isolated.sh) — 가상 네트워크 구성, 부착·해제, ping 검사
3. [`bcc_worker.py`](experiments/chapter3-exercises/bcc_worker.py) — kprobe와 tail call 실행, Map 집계
4. [`inspect.py`](experiments/chapter3-exercises/inspect.py) — 실행 중 bpftool 검사, 바이트코드/JIT 덤프, 종료 후 해제 확인
5. [`report.py`](experiments/chapter3-exercises/report.py) / [Actions 설정](.github/workflows/chapter3-exercises.yml) — 결과 판정 및 Summary·Artifact 기록

**원본 증거 확인:** Actions 실행 화면의 **Summary**에서 결과를 먼저 확인한 뒤, **Artifacts**의 `chapter3-exercises-<run_id>-<attempt>` ZIP을 확인함. `ex01.json`~`ex04.json`(판정), `ex02-hello-xlated.txt`·`ex02-hello-jited.txt`(명령어 덤프), `xdp.log`(패킷 검사), `SHA256SUMS.txt`(무결성 확인) 등이 포함됨.

**안전 경계:** XDP는 GitHub-hosted 러너의 일회용 network namespace 내부 veth에만 연결함. 호스트 `eth0`, 원격 개발 서버, Kubernetes 노드의 네트워크 인터페이스에는 연결하지 않음. EX04는 차단과 **차단 해제 후 통신 복구**를 모두 확인해야 PASS. JIT 역어셈블 기능을 포함한 bpftool을 Actions에서 빌드해 실제 기계어를 기록함.

[H002 상세 실험 기준](docs/experiments/H002-CHAPTER3-EXERCISES.md) · [원본 책 예제 — lizrice/learning-ebpf](https://github.com/lizrice/learning-ebpf)

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

