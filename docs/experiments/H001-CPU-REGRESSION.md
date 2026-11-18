# H001 후속 — CPU별 메시지 누락 재현 및 raw tracepoint 검증

**현재 상태: PASS. 일반 Hello World 1건 수신 및 raw CPU별 반복 검사 8/8 통과를 확인함. 같은 Azure 러너에서 기존 typed 방식의 CPU 1·2·3 이벤트 누락도 직접 재현했음.**

[기존 H001 결과와 실패 증거](H001-HELLO-WORLD.md) · [Hello World 안내](../../experiments/hello-world/README.md) · [실행 workflow](../../.github/workflows/hello-world.yml)

[성공 실행·Summary](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44311402173/attempts/1) · [실행 전 고정한 사전 계획](https://github.com/HeaInSeo/ebpf-agent-perf-poc/blob/c6eb3d9723d04587cd4ff4552b7402b8495ef683/docs/experiments/H001-CPU-REGRESSION.md)

아래 질문·고정 조건·반복 횟수·판정 기준은 실행 전 계획을 보존한 내용임. 실제 실행의 증거와 환경 한계는 마지막 결과 절에 기록함.

## 질문과 사전 가설

GitHub-hosted `ubuntu-24.04` 러너에서 기존 syscall별 tracepoint에 연결한 eBPF가 CPU에 따라 `execve()` 이벤트를 놓치는지 확인함. 같은 러너의 모든 시험 CPU에서 대체 경로인 `raw_tracepoint/sys_enter`가 대상 메시지를 빠짐없이 전달하는지도 확인함.

**원인 가설:** 기존 `tracepoint/syscalls/sys_enter_execve`는 영향을 받은 커널에서 일부 CPU의 이벤트를 누락하며, 전체 syscall 진입 지점에 직접 연결한 뒤 `execve` 번호를 선택하면 해당 누락 경로를 피할 수 있음.

근거가 된 외부 보고:

- [runner-images #15003](https://github.com/actions/runner-images/issues/15003): Ubuntu 7.0의 잘못된 backport로 `execve` 등 syscall 진입 BPF가 일부 CPU에서 호출되지 않는 회귀 보고임.
- [tinytap #444](https://github.com/shinagawa-web/tinytap/issues/444): `7.0.0-1014-aws`의 `write` 누락 관측이 포함됨. 이 AWS 관측 자체에서 CPU별 고정 대조를 완료한 것은 아님.

외부 보고와 증상의 유사성은 실험의 출발점임. 이번 러너의 `execve`에 대한 인과 판단에는 아래 CPU별 대조 결과가 필요함.

## 비교 대상과 고정 조건

| 항목 | 사전 조건 |
| --- | --- |
| 기존 코드 기준 | `71d492b88a38c9504aedd48f98e22edfc6ab54b6`의 syscall별 tracepoint 연결 방식 |
| 기존 방식 대조 객체 | `hello.bpf.c`를 `HELLO_LEGACY_TYPED`로 빌드한 `build/hello-typed.bpf.o` |
| 수정 객체 | `build/hello.bpf.o`: `raw_tracepoint/sys_enter`에 연결하고 `__NR_execve`와 PID로 선택함 |
| 공통 코드 | PID·cookie 구분, `bpf_printk()` 메시지 본문, 사용자 공간 로더, `trace_pipe` 수집기와 종료 절차를 공유함 |
| 대상 이벤트 | 대기 중인 테스트 프로세스가 `/usr/bin/true`를 실행하며 발생시키는 `execve()` 한 번 |
| 실행 환경 | 같은 GitHub-hosted `ubuntu-24.04` 러너, x86_64. 실제 이미지·커널·도구 버전은 결과에 기록함 |
| 실행 코드 식별 | 일반 사용자로 기록한 `source-sha.txt`와 Actions의 `GITHUB_SHA`가 일치해야 함 |
| CPU 집합 | 실행기의 허용 CPU 전체를 조사함. 허용 CPU가 없거나 8개를 넘으면 검사를 축소하지 않고 중단함 |
| CPU 고정 범위 | 테스트 프로세스만 지정 CPU에 고정함. 로더와 수집기 전체를 CPU 0에 고정하는 우회는 적용하지 않음 |
| 출력 수집 | 기존과 동일한 커널 `trace_pipe`에서 원문을 읽음. CPU별 실행은 순차 처리함 |
| 시간 제한 | 실행당 메시지 대기 최대 8초, 개별 실행기의 외부 제한 45초. 시간 제한과 정리 결과를 기록함 |

같은 소스에서 연결 방식만 바꾼 객체를 빌드하여, 사용자 공간 출력이나 판정 코드의 차이가 비교 결과를 만들지 않도록 함. raw 경로는 전체 syscall 진입을 받지만 `__NR_execve` 검사 이후에만 이번 예제의 메시지를 기록함.

## 실행 순서와 반복 횟수

1. 일반 Hello World 단일 실행에서 실제 메시지 1건과 정상 종료·연결 해제를 확인함.
2. 허용 CPU 집합을 기록하고 각 CPU에 대해 테스트 프로세스를 고정한 뒤 설정을 다시 읽어 확인함.
3. 수정한 raw 방식으로 CPU마다 **2회** 실행함. 각 실행은 새 PID·cookie와 별도 결과 폴더를 사용함.
4. 기존 typed 방식으로 CPU마다 **1회** 실행하여 누락 여부를 대조함.
5. 커널 메시지를 받은 경우 원문에 표시된 CPU가 지정한 CPU와 일치하는지 확인함.
6. 모든 실행 결과, 외부 종료 코드, 개별 로그와 비교 요약을 저장함.

허용 CPU가 4개이면 CPU 대조는 raw 8회와 typed 4회로 총 12회이며, 앞선 일반 Hello World 1회는 별도임. 성공이 나올 때까지 재시도하는 방식은 사용하지 않음. 계획된 반복에서 발생한 실패도 결과에 포함함.

## 사전 판정 기준

### 수정 경로의 필수 성공 기준

모든 raw 실행에서 다음 조건을 만족해야 CPU 회귀 검사를 PASS로 판정함.

- eBPF 적재·연결과 대상 이벤트 발생이 완료되어야 함.
- 지정한 CPU와 확인한 대상 프로세스의 CPU affinity가 일치해야 함.
- 대상 PID·cookie가 일치하는 실제 커널 메시지를 정확히 1건 받아야 함.
- 수신 메시지의 CPU 표시가 지정한 CPU와 일치해야 함.
- 대상 프로세스와 로더의 종료 코드가 모두 `0`이며 `DETACHED`가 확인되어야 함.
- 원시 결과 파일이 존재하고 개별 실행기가 성공으로 종료해야 함.

메시지 0건·중복 수신·CPU 불일치·준비 실패·비정상 종료·정리 실패는 PASS로 처리하지 않음. 일반 Hello World 실행이 성공해도 CPU 회귀 검사가 실패하면 workflow는 실패해야 함.

### 기존 경로 대조의 해석

기존 typed 방식의 메시지 0건은 **정상 적재·연결, 대상 종료 `0`, 로더 종료 `0`, `DETACHED` 확인, 메시지 미수신에 해당하는 실패 사유**가 모두 확인된 경우에만 대조 관측인 `NO_EVENT`로 기록함. 이는 기존 경로의 개별 실행을 성공으로 바꾸는 뜻이 아님. 해당 `result.json`과 실패 로그를 보존함.

기존 방식의 메시지 1건은 CPU·PID·cookie·종료 조건을 동일하게 확인함. 메시지 2건 이상, 준비 대기 실패, 외부 실행 시간 초과, 환경·권한 오류, 정리 실패를 예상된 누락으로 취급하지 않으며 전체 검사를 실패 처리함.

| 관측 | 해석 |
| --- | --- |
| 기존 방식은 CPU 0에서만 수신하고 수정 방식은 모든 시험 CPU에서 수신함 | 해당 러너에서 기존 경로의 CPU별 누락과 대체 경로의 수정 효과를 직접 확인한 근거임 |
| 두 방식 모두 모든 시험 CPU에서 수신함 | 수정 경로의 기능 검증은 가능하나, 해당 실행에서 기존 누락 원인은 재현되지 않은 상태임 |
| 수정 방식이 어느 CPU에서든 필수 기준을 충족하지 못함 | 수정 검증 FAIL임. 성공한 일부 CPU만으로 통과 판정을 내리지 않음 |
| CPU 0이 허용 집합에 없음 | CPU 0과의 대조를 수행했다고 해석할 수 없음. 실제 시험 CPU 범위만 보고함 |

## 재현 명령과 결과 보관

Actions에서는 [workflow](../../.github/workflows/hello-world.yml)의 **CPU별 이벤트 수신 회귀 검사** 단계가 실행함. 필요한 도구와 권한을 갖춘 실험용 리눅스 환경에서 직접 재현하는 명령은 다음과 같음.

```bash
make -C experiments/hello-world regression
mkdir -p results/hello-world
git rev-parse HEAD > results/hello-world/source-sha.txt
sudo python3 -u experiments/hello-world/run.py --output results/hello-world
sudo python3 -u experiments/hello-world/verify_cpus.py --output results/hello-world/cpu-checks
```

`results/hello-world/cpu-checks/`에 CPU별 개별 실행의 환경·소스 SHA·PID·cookie·커널 원문·종료 결과·stdout·stderr를 보관함. 비교 JSON과 `summary.md`는 개별 원시 결과로 연결되며, CPU별 기존 방식·수정 방식 결과를 표로 표시함. workflow는 이 요약을 일반 Hello World Summary에 이어 게시함.

전체 결과를 Artifact로 업로드하고 파일별 `SHA256SUMS.txt`를 생성함. 다운로드한 ZIP 해시와 내부 파일 해시를 확인한 뒤, run ID·attempt·job·실행 소스 SHA와 함께 원시 증거를 보존함. 기존 실행의 재시도는 기존 SHA를 사용하므로 수정 코드는 **Run workflow → main → Run workflow**로 새로 실행함.

## 실행 전 확인된 기록

| 실행 | 코드 SHA | 메시지 | 판정 | 원시 근거 |
| --- | --- | --- | --- | --- |
| 44295526471 / attempt 1 | `71d492b88a38c9504aedd48f98e22edfc6ab54b6` | 1건, CPU `[000]` | PASS | [보존 파일](h001-evidence/44295526471-1/) |
| 44295526471 / attempt 2 | 같은 SHA | 0건·0바이트 | FAIL | [보존 파일](h001-evidence/44295526471-2/) |
| 44295526471 / attempt 3 | 같은 SHA | 0건·0바이트 | FAIL | [보존 파일](h001-evidence/44295526471-3/) |

attempt 2·3도 연결 성공과 대상·로더 정상 종료, `DETACHED`가 확인됨. 실패한 대상의 실제 실행 CPU는 당시 기록에 없어 CPU별 누락 여부를 과거 증거만으로 확정할 수 없음.

## 후속 실행 결과

### 실행 식별과 환경

| 항목 | 실제 값 |
| --- | --- |
| 실행 | [44311402173 / attempt 1](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44311402173/attempts/1) |
| Job | [134826193606](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44311402173/job/134826193606) |
| 소스 SHA | [`c6eb3d9723d04587cd4ff4552b7402b8495ef683`](https://github.com/HeaInSeo/ebpf-agent-perf-poc/commit/c6eb3d9723d04587cd4ff4552b7402b8495ef683) |
| 일반 실행 시각 | `2026-11-18T13:13:09.383506+00:00`, 한국 시간 `2026-11-18 22:13:09` |
| CPU 대조 시작·종료 | `2026-11-18T13:13:09.813238+00:00` ~ `2026-11-18T13:13:37.558558+00:00` |
| 이미지 | `ubuntu24 / 20261111.370.1` |
| 커널 | `7.0.0-1017-azure` |
| 아키텍처·권한 | x86_64, UID `0` |
| CPU 수·허용 집합 | 4개, `[0, 1, 2, 3]` |
| 도구 | Clang `18.1.3`, GCC `13.3.0`, libbpf `1.3.0`, Python `3.12.3` |
| 빌드·단위 테스트 | eBPF 두 객체와 로더 빌드 성공, 테스트 **15개 통과** |

### 일반 Hello World와 CPU별 결과

일반 실행에서 대상 PID `2712`, cookie `5926992076653090457`의 실제 커널 메시지 1건을 받았음. 이 실행에는 CPU 고정을 적용하지 않았으며, 메시지 원문의 CPU는 `[003]`임. 대상·로더 종료 코드 `0/0`과 `DETACHED=true`를 확인했음.

```text
         python3-2712    [003] ...3.    58.529018: bpf_trace_printk: Hello World! pid=2712 cookie=5926992076653090457
```

CPU 대조 결과는 다음과 같음. 각 칸은 해당 시험에서 실제로 받은 메시지 수임.

| CPU | 기존 typed: 1회 | 수정 raw: 1회차 | 수정 raw: 2회차 |
| --- | --- | --- | --- |
| 0 | 1건, PASS | 1건, PASS | 1건, PASS |
| 1 | 0건, `NO_EVENT` | 1건, PASS | 1건, PASS |
| 2 | 0건, `NO_EVENT` | 1건, PASS | 1건, PASS |
| 3 | 0건, `NO_EVENT` | 1건, PASS | 1건, PASS |

수정 raw 방식은 **8/8 통과**이며 모든 수신 원문의 CPU 표시가 지정 CPU와 일치함. 대조를 포함한 12개 실행에서 대상·로더 종료 코드 `0/0`, 정상 적재·연결 및 `DETACHED=true`를 확인했음. 외부 실행 시간 초과는 없었음.

typed CPU 1·2·3의 개별 결과는 **FAIL**, 실행기 종료 코드는 `1`임. 비교 실행기는 정상 준비·실행·정리 뒤 메시지만 0건인 조건을 확인해 이를 `NO_EVENT`로 분류했음. 따라서 `typed_valid=4`는 대조 기록 네 개가 해석 가능한 조건을 충족했다는 의미이며, 기존 경로 네 개가 모두 메시지를 받았다는 뜻이 아님.

### 해석과 환경 한계

**이번 `7.0.0-1017-azure` 러너에서는 기존 typed 연결의 CPU별 누락과 raw 연결의 수정 효과를 직접 확인했음.** 같은 소스의 공통 PID·cookie·출력 코드를 사용하면서 연결 방식에 따라 CPU 1·2·3의 수신 결과가 달라졌음. 이 관측은 [runner-images #15003](https://github.com/actions/runner-images/issues/15003)의 Ubuntu 7.0 회귀 설명과 일치함.

이전 실패 두 건은 `7.0.0-1014-aws`, 이미지 `20261111.127.1`에서 발생했으며 이번 새 실행은 `7.0.0-1017-azure`, 이미지 `20261111.370.1`을 사용함. 따라서 **이전 AWS 환경에서 CPU별 대조까지 직접 완료했다고 해석할 수 없음.** 과거 실패 시 대상 CPU가 기록되지 않았으므로 해당 실패 각각의 원인을 완전히 확정하는 데에는 한계가 있음. 수정 효과의 직접 검증 범위는 위 Azure 환경과 기록된 CPU 집합임.

일반 Hello World와 CPU 회귀 검사가 모두 사전 기준을 충족했으며 workflow의 빌드·실행·요약·Artifact 단계도 성공했으므로, 이번 보정 검증의 최종 판정은 **PASS**임.

### 원시 증거와 무결성

- [보존 증거 전체](h001-evidence/44311402173-1/), [실행 환경](h001-evidence/44311402173-1/environment.json), [일반 결과](h001-evidence/44311402173-1/result.json), [실제 커널 원문](h001-evidence/44311402173-1/kernel-events.log).
- [CPU별 비교 JSON](h001-evidence/44311402173-1/cpu-checks/result.json), [CPU별 Summary](h001-evidence/44311402173-1/cpu-checks/summary.md), [raw 개별 실행](h001-evidence/44311402173-1/cpu-checks/raw/), [typed 개별 실행](h001-evidence/44311402173-1/cpu-checks/typed/).
- [Artifact `14428934541`](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44311402173/artifacts/14428934541), 이름 `hello-world-44311402173-1`.
- 다운로드한 ZIP SHA-256: `df58d202e2935c1ec9de3c43269e76f4b62c37a63801b16bfba303f57b087252`.
- 내부 파일 **174개**를 [SHA256SUMS.txt](h001-evidence/44311402173-1/SHA256SUMS.txt)와 대조해 보존했음. [Artifact 메타데이터](h001-evidence/44311402173-1/artifact.json)에 다운로드와 검증 정보를 기록함.

### 독립 검토

별도 검토에서 ZIP 해시와 내부 원본 175개 파일의 바이트 일치, manifest 대상 174개 해시, 모든 실행의 소스 SHA, 실제 커널 원문·PID·cookie·CPU, 13개 실행의 정상 종료·연결 해제를 대조했음. 일반 Hello World 1건, raw 8/8 성공, typed CPU 0 수신 및 CPU 1·2·3 미수신, 단위 테스트 15개 통과와 job 전체 성공을 독립적으로 확인했음.

이 실험은 해당 러너의 메시지 전달과 연결 정리를 검증함. 성능 수치, 모든 커널의 호환성, 기존 성능 PoC의 구현 선택 가설에 대한 결론은 포함하지 않음.
