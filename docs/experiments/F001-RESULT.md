# F001 결과 — 다섯 eBPF 구현 경로의 GitHub Actions 실행 가능성

**최종 판정: PASS — 다섯 방식 모두 9/9, 총 45/45 시험 통과.**

이 보고서는 실제 GitHub-hosted Ubuntu 24.04 x86_64 실행 증거를 근거로 한다.
이번 완료 범위는 구현 방식별 실행 가능성과 계측 정확성이다. 에이전트가 증거를 받아
자동으로 코드를 개선하는 기능, 성능 우위, 컨텍스트 부합성 개선은 아직 검증하지 않았다.

## 1. 실행과 고정 입력

- 최종 실행: [39776073689](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39776073689)
- 시험 코드: `5d45ef49e26b81ab4495ce43fe4ef91959bd643a`
- 실행 시작: 2026-10-22 21:09:33 KST / 12:09:33 UTC
- 실행 종료: 2026-10-22 21:11:49 KST / 12:11:49 UTC
- [사전 등록](F001-FRAMEWORK-COMPAT-PROTOCOL.md), [1차 보정](F001-CORRECTION-1.md),
  [증거 봉인 보정](F001-EVIDENCE-SEALING.md)
- 원본 dag-go와 ebpf-study는 수정하지 않았다. E005의 기존 측정과 판정을 보존했다.

## 2. 방식별 결과

| 방식 | 커널 계측 / 사용자 공간 | 고정 또는 관측 버전 | 최종 시험 |
|---|---|---|---|
| bpftrace | bpftrace DSL / bpftrace CLI | bpftrace 0.20.2 | PASS 9/9 |
| libbpf | C / C loader | Ubuntu libbpf-dev 1.3.0 계열, 정확한 패키지 버전은 setup.log | PASS 9/9 |
| cilium/ebpf | 공유 C BPF object / Go loader | cilium/ebpf 0.22.0, Go는 build.log 기록 | PASS 9/9 |
| Aya | Rust BPF / Rust loader | aya 0.13.1, aya-ebpf 0.1.1, nightly-2025-09-01, bpf-linker 0.9.15 | PASS 9/9 |
| BCC | C BPF / Python loader | BCC 0.29.1, /usr/bin/python3 | PASS 9/9 |

Cilium의 Go 코드는 C로 컴파일한 BPF object를 로드·연결·조회한다.
Python은 이번 BCC 구현에서는 loader이고, 공통 probe.py에서는 실험 제어기다.
bpftrace는 자체 DSL을 컴파일한다. tracepoint는 이들과 별개의 커널 관찰 지점이다.

libbpf와 cilium이 사용한 C BPF object의 SHA256은 두 job에서 동일했다:
`d497c5248cc3436e97a79a649eca5343f862225c1ffca2d9091e3921db2bcb0a`.
다섯 job의 관찰 대상 실행 파일도 모두 동일한 SHA256이었다:
`771c26d1a9f8364734dd74a2a1d1c55381b5d8ed10b993e964b7ad8187962365`.

## 3. 실제 runner 차이

같은 `ubuntu-24.04` 라벨이어도 job마다 실제 image와 kernel이 달랐다.

| 방식 | runner image | Linux kernel |
|---|---|---|
| bpftrace | 20261012.334.1 | 6.17.0-1022-azure |
| libbpf | 20261012.334.1 | 6.17.0-1022-azure |
| cilium/ebpf | 20261018.339.1 | 7.0.0-1017-azure |
| BCC | 20261018.339.1 | 7.0.0-1017-azure |
| Aya | 20261021.345.10 | 7.0.0-1017-azure |

따라서 이 결과는 위 조합에서의 capability PASS다. 모든 방식이 모든 kernel에서
동작한다고 일반화할 수 없다. job 간 소요시간을 언어·라이브러리 성능으로 비교하지 않았다.
특히 향후 정밀 성능 실험은 동일 job의 교차 측정 등 별도 통제가 필요하다.

## 4. 시험 계약과 재검산

공통 hook은 `tracepoint/raw_syscalls/sys_enter`, 관찰 syscall은 x86_64 getpid ID 39다.
이 hook 이름의 raw_syscalls는 BPF_PROG_TYPE_RAW_TRACEPOINT를 뜻하지 않는다.

관찰 대상 C 프로그램은 대기 상태로 시작하며 loader의 연결 완료 신호 후에만
명시적 `syscall(SYS_getpid)`를 실행한다. bpftrace는 -c child를 이용해 연결 완료를 보장한다.
선택하지 않은 별도 PID가 매 시험 137회를 호출하는 음성 대조도 포함한다.

| 시험 | 선택 PID의 호출 | 다른 PID의 호출 | 기대 관측 | 반복 |
|---|---|---|---|---|
| zero | 없음 | 137 | 0 | 3 |
| single | 500 | 137 | 500 | 3 |
| batches | 1 + 499 + 5000 | 137 | 5500 | 3 |

각 방식에서 선택 PID의 기대 호출 18,000회, 전체 다섯 방식에서 90,000회를 정확히 관측했다.
관찰하지 않을 PID는 방식별 1,233회를 호출했다.
READY 후 실제 새 BPF program/map이 존재하는지도 검사했다.
매 시험에서 도입된 모든 program/map ID가 collector 종료 후 사라졌고 collector exit는 0이었다.

원시 stdout을 별도로 다시 읽어 45개 trial JSON과 기대값을 대조했다.
최종 artifact의 전체 185개 파일에 대해 내부 SHA256 manifest와 파일 집합을 검증했다.
불일치와 manifest에서 빠진 파일은 0개였다. 각 artifact의 manifest 자체는 자기 해시에서 제외한다.
[독립 재검산 기록](f001-evidence/39776073689/archive-validation.json)에 검증 결과를 보존했다.

## 5. 실패와 보정 이력

| 실행 / 코드 | 실제 결과 | 처분 |
|---|---|---|
| [첫 실행 39774887636](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39774887636), f12a3aaa | libbpf·cilium PASS; BCC import 실패; Aya compile 실패; bpftrace 출력 판정 실패 | 원시 증거 보존 후 bounded correction |
| [보정 실행 39775718563](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39775718563), feb15112 | 다섯 방식 모두 9/9 PASS | artifact 봉인 시점 문제를 별도로 보정 |
| [최종 실행 39776073689](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/39776073689), 5d45ef49 | 다섯 방식 9/9 PASS, 전체 artifact checksum 검증 PASS | F001 완료 |

### BCC 이름 충돌

우리의 bcc.py가 설치된 bcc 패키지를 가려 순환 import가 발생했다.
bcc_collector.py로 이름을 바꾸어 해결했다. 이 실패는 BCC의 커널 지원 불가 증거가 아니다.

### bpftrace 중복 snapshot

최초 원시 stdout에는 실제 `@events: 500`과, clear 후 자동 출력된 `@events: 0`이 함께 있었다.
이전 parser가 마지막 값을 읽어 실패로 판정했다. 실제 500회를 누락한 것으로 해석하지 않는다.
명시적 END print/clear를 제거하고 단일 snapshot만 허용했다.
이 실패 출력을 넣는 회귀 검사도 추가했다.

### Aya 원자적 연산

고정한 Rust BPF target에서 AtomicU64::fetch_add가 제공되지 않아 compile에 실패했다.
CPU별 PERCPU_ARRAY 카운터를 사용하고 사용자 공간에서 합산하도록 보정했다.
시험 대상은 단일 thread다. Rust의 일반적인 shared atomic 지원이나 다중 thread 계측을
검증한 결과로 확장하지 않는다.

### artifact checksum 시점

처음 두 실행의 probe.log는 외부 tee가 로그를 쓰는 중에 해시를 계산해 마지막 summary가 빠졌다.
원본 SHA256SUMS.txt와 원본 로그를 그대로 보존했고, 실제 불일치를 archive-validation.json에 기록했다.
각 보존본에는 별도 ARCHIVE-SHA256SUMS.txt를 생성했다.
최종 실행은 모든 writer와 provenance 복사가 끝난 뒤 봉인하여 전체 검증을 통과했다.

## 6. 보존 자료와 재현

- [첫 실패 포함 전체 artifact](f001-evidence/39774887636/)
- [첫 전체 PASS artifact](f001-evidence/39775718563/)
- [최종 전체 PASS artifact](f001-evidence/39776073689/)
- 각 방식별 setup/build/probe 로그, stdout/stderr, result.json, 환경, lock, binary checksum 포함.
- GitHub artifact 만료와 관계없이 이 저장소에서 검토할 수 있다.
- Cargo.lock과 Go dependency checksum을 소스에 고정했다. Ubuntu 패키지는 실제 설치 버전을 기록했다.
- 사후 보존 커밋은 문서·증거만 추가한다. 실제 시험 source SHA는 위 고정값이다.

재실행은 수동 workflow를 사용한다:

```sh
gh workflow run framework-compat.yml --repo HeaInSeo/ebpf-agent-perf-poc --ref main
```

커널 로드·계측은 disposable GitHub-hosted runner에서 실행한다.
결과 검토 후 이전 결과를 덮어쓰지 않고 새 run ID로 보존해야 한다.

## 7. 판정 범위와 남은 가능성 검증

확보한 근거는 bpftrace 이외에도 C/libbpf, Go/cilium, Rust/Aya, Python/BCC를 이용해
Actions에서 작은 계측기를 빌드·로드·연결하고 정확한 결과를 회수할 수 있다는 것이다.
향후 에이전트와 연계할 수집기 구현 경로의 실행 가능성이 확인됐다.

다음 항목은 이번 PASS에 포함되지 않는다:

- kprobe, fentry/fexit, uprobe, XDP, CO-RE relocation의 실제 지원 범위.
- syscall 지연, 스케줄링, 페이지 폴트 등의 정확한 원인 귀속.
- streamed ring-buffer 이벤트 누락률과 동시·다중 thread 수집 정확도.
- 언어·라이브러리별 오버헤드 우열 또는 성능 개선.
- 컨텍스트 부합성 판단, 에이전트 의사결정 개선, 자동 코드 수정.
- 현재 기록에 없는 runner image/kernel/toolchain 조합의 호환성.

E005에서 추가적인 구현 선택 개선이 입증되지 않았다는 기존 결론은 그대로 유지한다.
