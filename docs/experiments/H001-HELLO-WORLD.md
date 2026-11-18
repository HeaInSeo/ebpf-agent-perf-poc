# H001 — Actions 화면에서 eBPF Hello World 확인

**현재 상태: 2차 실행 PASS. 대상 커널 메시지 1건 수신, 정상 종료·연결 해제, 로그·Summary·Artifact 게시를 확인했음. 1차 FAIL 기록은 보존함.**

[성공한 실행·Summary](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44295526471) · [쉽게 따라 하는 안내](../../experiments/hello-world/README.md) · [수동 실행 workflow](../../.github/workflows/hello-world.yml)

## 연구 질문 / 범위

**가설:** GitHub-hosted `ubuntu-24.04` 러너에서 C/libbpf Hello World를 적재·연결한 뒤 대상 프로세스의 `execve()`를 발생시키면, eBPF가 기록한 메시지 한 건을 Actions 로그와 Summary에 표시할 수 있음.

대상 저장소는 `HeaInSeo/ebpf-agent-perf-poc`이며, 작업 시작 시 `main`은 `2e53f8efae138b61dbb952f898e6bb68a6a7ca94`임. 실행에 사용한 실제 코드 SHA는 시도별 기록에 남김.

예제의 출처는 `HeaInSeo/ebpf-study` 커밋 `9b9da7308f13828f557ec5c05e5aff663da4e7b4`의 [hello.bpf.c](https://github.com/HeaInSeo/ebpf-study/blob/9b9da7308f13828f557ec5c05e5aff663da4e7b4/c-libbpf/src/hello.bpf.c)와 [hello.c](https://github.com/HeaInSeo/ebpf-study/blob/9b9da7308f13828f557ec5c05e5aff663da4e7b4/c-libbpf/src/hello.c)임. 원본의 tracepoint·`bpf_printk()`·libbpf 로더 구조를 바탕으로 PID 구분, 실행별 cookie, 자동 종료와 증거 수집을 추가함.

이번 범위는 컴파일, 커널 적재·연결, 테스트 이벤트 발생, 실제 커널 출력 수신, 결과 표시와 연결 해제임. 프로그램 성능, Cilium 데이터 경로, 다른 eBPF hook 또는 모든 커널에서의 호환성을 평가하지 않음.

### 사전 판정 기준

| 판정 | 기준 |
| --- | --- |
| **PASS** | 빌드·적재·연결 성공 후 대상 프로세스의 `execve()`를 발생시키고, PID와 cookie가 일치하는 커널 메시지를 정확히 한 건 수신함. 대상 프로세스와 로더가 정상 종료하고 로더의 연결 해제 기록을 확인함. |
| **FAIL** | 필요한 환경을 갖춘 실행에서 빌드·적재·연결 오류, 제한 시간 내 메시지 미수신, 메시지 수 불일치, 비정상 종료 또는 정리 실패가 발생함. |
| **BLOCKED** | 필수 도구·권한·tracefs·tracepoint 등 실행 전제 조건이 없어 실험을 수행할 수 없음. 통과로 취급하지 않음. |

이 기능 시험의 실행기는 `PASS`, `FAIL`, `BLOCKED`를 사용함. `BLOCKED`도 Actions 작업을 실패로 끝냄. 작업 취소나 증거 누락으로 완료되지 않은 실행은 성공으로 해석하지 않음.

셸 명령의 정상 종료나 로더의 준비 메시지만으로 PASS를 부여하지 않음. 수집기는 `trace_pipe`에서 읽은 메시지를 검증함.

## 재현 환경과 입력

- Workflow: `eBPF Hello World (manual)`, `workflow_dispatch` 전용.
- 러너: GitHub-hosted `ubuntu-24.04`. 실행별 이미지·커널·아키텍처·도구 버전과 코드 SHA를 결과에 남김.
- 권한: workflow 토큰은 `contents: read`. 커널 적재와 추적 버퍼 읽기는 일회성 러너에서 `sudo`로 수행함.
- 입력: 대기 중인 테스트 프로세스 한 개. 로더의 `READY`를 확인한 뒤 `/usr/bin/true`로 `execve()` 한 번을 발생시킴. 2차 보정에서는 이벤트 발생 전에 추적 설정 활성화도 확인함.
- 구분 값: 대상 PID와 실행별 무작위 cookie. 실제 값은 원시 로그·결과에 보관함.
- 수집: `/sys/kernel/tracing/trace_pipe`. 대상 PID와 cookie가 모두 일치하는 메시지만 이번 실험의 증거로 사용함.
- 종료: 수신 대기 한도는 8초임. 로더에 종료 신호를 보내고 `DETACHED` 및 종료 코드를 확인함. 로더에도 별도의 30초 제한이 있음.
- 계측 조건: 기능 검증용 1회 실행이며 성능 수치를 계산하지 않음. `bpf_printk()`와 로그 수집의 비용을 벤치마크에 섞지 않음.

## 재현 절차

1. [Actions workflow](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/workflows/hello-world.yml)에서 **Run workflow → main → Run workflow**를 선택함.
2. 빌드 단계의 `make -C experiments/hello-world` 결과를 확인함.
3. **커널에서 Hello World 확인** 작업의 **Hello World 실행 및 커널 메시지 확인** 단계에서 실제 수신 메시지와 판정을 확인함.
4. Summary와 `hello-world-실행번호-시도번호` Artifact를 함께 확인함.

빌드 후 별도로 재현할 때 저장소 최상위에서 실행하는 명령은 다음과 같음.

```bash
mkdir -p results/hello-world
git rev-parse HEAD > results/hello-world/source-sha.txt
sudo python3 -u experiments/hello-world/run.py --output results/hello-world
```

`run.py`는 출력 폴더의 `source-sha.txt`를 읽어 실행 코드를 식별함. Git의 저장소 소유권 검사로 인한 `sudo` 실행 오류를 피하도록 일반 사용자로 SHA를 먼저 기록함. Actions workflow는 이 파일을 자동으로 준비함.

실제 실행 명령과 옵션의 정본은 해당 실행 SHA의 [workflow](../../.github/workflows/hello-world.yml)임. 로그에는 명령과 오류를 보존함. `run.py`가 요약을 만들고, workflow의 후속 단계가 `GITHUB_STEP_SUMMARY`에 게시함.

## 작업 및 시도별 기록

| 시도 | 코드 SHA | 실행 링크 | 측정·오류 근거 | 판정 |
| --- | --- | --- | --- | --- |
| 1 | [`005dd51233a46ac9a3cad28ede679b6731368d7d`](https://github.com/HeaInSeo/ebpf-agent-perf-poc/commit/005dd51233a46ac9a3cad28ede679b6731368d7d) | [44294538610](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44294538610) | 연결 성공, 대상·로더 정상 종료, 일치 메시지 0건 | **FAIL** |
| 2 | [`71d492b88a38c9504aedd48f98e22edfc6ab54b6`](https://github.com/HeaInSeo/ebpf-agent-perf-poc/commit/71d492b88a38c9504aedd48f98e22edfc6ab54b6) | [44295526471](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44295526471) | 대상 메시지 1건, 대상·로더 정상 종료, 연결 해제, 결과 게시 성공 | **PASS** |

### 1차 실행 — 메시지 수신 0건으로 실패

- 실행 시각: `2026-11-18T11:26:37.680789+00:00` (UTC).
- Job: [`134768010011`](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44294538610/job/134768010011).
- 환경: Ubuntu 이미지 `ubuntu24 / 20261111.127.1`, 커널 `7.0.0-1014-aws`, x86_64, 4 CPU, 실행 UID 0.
- 도구: Clang `18.1.3`, GCC `13.3.0`, libbpf `1.3.0`, Python `3.12.3`.
- 빌드와 검증 테스트 4개는 통과했음. eBPF 연결도 성공했음.
- 대상 PID는 `2753`, cookie는 `5797601167314965267`이었음.
- 대상 프로세스와 로더의 종료 코드는 모두 `0`이며, `DETACHED`를 확인했음.
- PID·cookie가 일치하는 커널 메시지는 **0건**이었음. 사전 기준인 정확히 1건을 충족하지 못해 **FAIL**로 판정했음.

원시 결과의 오류는 `대상 커널 메시지가 정확히 1건이어야 해: 실제 0건`임. 연결 성공과 정상 종료만으로 테스트를 통과시키지 않은 기록임.

증거:

- [영구 보존한 원시 파일](h001-evidence/44294538610-1/), [result.json](h001-evidence/44294538610-1/result.json), [environment.json](h001-evidence/44294538610-1/environment.json), [로더 출력](h001-evidence/44294538610-1/loader.stdout.log).
- [Artifact `14422053876`](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44294538610/artifacts/14422053876).
- 다운로드한 Artifact ZIP의 SHA-256: `fbc11ead70357ee6b0b160f6f48c906647915e8486bef12b9ed9e7c31b7feab4`.
- 다운로드 무결성을 확인한 뒤 원시 파일을 보존했음. 파일별 해시는 [SHA256SUMS.txt](h001-evidence/44294538610-1/SHA256SUMS.txt)에 있음.

### 2차 실행에 적용한 보정

**1차 실패의 원인은 확정되지 않았음.** 1차 실행에는 추적 설정과 읽기 동작을 구분할 진단 기록이 없어, 출력 활성화 시점이나 수집 방식 중 무엇이 원인이었는지 판단할 수 없음.

커널의 [`bpf_trace.c`](https://github.com/torvalds/linux/blob/master/kernel/trace/bpf_trace.c)는 `bpf_trace_printk` 이벤트 활성화를 `schedule_work()`로 예약함. 이는 연결 직후의 설정을 명시적으로 확인할 근거이며, 해당 러너에서 실제로 그 지연이 실패를 일으켰다는 증거는 아님.

다음 보정으로 재실행했음.

1. 로더의 `READY` 이후 `tracing_on`과 `events/bpf_trace/bpf_trace_printk/enable`이 `1`인지 동기적으로 확인하고, 필요한 설정 변경은 종료 시 원래 값으로 복원함.
2. 수집기는 비차단 읽기를 먼저 시도하고, `EAGAIN`일 때 대기함. 준비 알림이 없더라도 직접 읽을 데이터가 있는 경우를 다룸.
3. `trace-settings.json`과 `reader.json`을 추가해 추적 설정 및 수신 동작을 보존함.
4. 준비 알림 없이 직접 읽는 경우를 검증하는 다섯 번째 단위 테스트를 추가함.

첫 실패의 코드·결과·원시 증거는 그대로 유지했음.

### 2차 실행 — 실제 커널 메시지 1건 수신으로 성공

- 실행 시각: `2026-11-18T11:33:37.599475+00:00` (UTC), 한국 시간 `2026-11-18 20:33:37`.
- Job: [`134771451816`](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44295526471/job/134771451816), 결론 `success`.
- 환경: Ubuntu 이미지 `ubuntu24 / 20261111.127.1`, 커널 `7.0.0-1014-aws`, x86_64, 4 CPU, UID 0. Clang `18.1.3`, GCC `13.3.0`, libbpf `1.3.0`, Python `3.12.3`.
- 빌드와 검증 테스트 **5개**가 통과했음. eBPF 연결과 실제 메시지 수신, Summary 게시, Artifact 업로드도 성공했음.
- 대상 PID는 `2752`, cookie는 `9099829962833102368`임.
- 일치하는 커널 메시지는 **정확히 1건**임. 대상·로더 종료 코드는 모두 `0`, `DETACHED` 확인은 `true`임.

실제 수신 원문:

```text
         python3-2752    [000] ...31   265.976548: bpf_trace_printk: Hello World! pid=2752 cookie=9099829962833102368
```

추가 진단에서 관찰한 사실:

- `bpf_trace_printk/enable`은 `before_attach`에서 `0`, `before_output_ready`와 `output_ready`에서 `1`이었음.
- `tracing_on`은 세 시점 모두 `1`, `buffer_percent`는 모두 `50`이었음.
- 수집기는 **118바이트, 완성된 한 줄**을 읽었고 남은 부분 데이터는 `0`바이트였음.
- 설정 확인 이전인 `before_output_ready`에도 이벤트가 이미 활성화돼 있었음. 이번 성공을 활성화 보정 하나의 효과로 단정할 수 없음.

증거:

- [영구 보존한 원시 파일](h001-evidence/44295526471-1/), [result.json](h001-evidence/44295526471-1/result.json), [environment.json](h001-evidence/44295526471-1/environment.json), [실제 Summary](h001-evidence/44295526471-1/summary.md).
- [trace-settings.json](h001-evidence/44295526471-1/trace-settings.json), [reader.json](h001-evidence/44295526471-1/reader.json), [로더 출력](h001-evidence/44295526471-1/loader.stdout.log).
- [Artifact `14423148780`](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44295526471/artifacts/14423148780), 이름 `hello-world-44295526471-1`.
- Artifact ZIP SHA-256: `923bf5593a8b857c8ffb69d64c927a3d8172696a3313865728ef921a15006154`.
- 다운로드한 ZIP의 해시와 내부 파일 **14개**의 해시를 확인했음. [Artifact 메타데이터](h001-evidence/44295526471-1/artifact.json)와 [SHA256SUMS.txt](h001-evidence/44295526471-1/SHA256SUMS.txt)를 함께 보존함.

이 실행은 사전 PASS 기준을 충족했음. 다만 1차 실행에는 관련 진단이 없고 여러 보정을 함께 적용했으므로, **1차 실패 원인은 여전히 미확정**임.

### 보관할 증거

`results/hello-world/`에 다음 파일을 모아 Artifact로 업로드함.

- `environment.json`: 실행 환경과 재현 정보.
- `source-sha.txt`: 일반 사용자 권한으로 기록한 실행 코드 SHA.
- `result.json`: 판정, 대상 PID·cookie, 수신 결과와 종료 상태.
- `kernel-events.log`: 이번 실험에 대응하는 커널 메시지 원문.
- `loader.stdout.log`, `loader.stderr.log`: 연결 준비·해제 기록과 오류.
- `setup.log`, `build.log`, `probe.log`: 준비·빌드·실행 과정.
- `summary.md`: Actions Summary에 표시한 한국어 요약.
- `trace-settings.json`, `reader.json`: 2차 보정부터 수집하는 추적 설정·읽기 진단. 1차 실행에는 존재하지 않음.
- `SHA256SUMS.txt`: 결과 파일의 무결성 확인용 해시.

Artifact는 30일간 보관함. 보존 기간 이후에도 검토할 수 있도록 시도별 원시 증거를 `h001-evidence/`에 보존함. 두 실행의 실제 경로와 Artifact 해시는 위 기록에 연결했음.

## 분석 및 독립 검토

관찰 사실은 **1차 수신 실패와 2차 메시지 1건 수신 성공**임. 2차 실행은 로더 준비, 대상 이벤트, 커널 원문 수집, 정상 종료·연결 해제, GitHub 결과 표시까지 확인했음. 첫 실패의 정확한 원인은 후속 성공만으로 확정할 수 없음.

별도 최종 검토에서도 로더의 `READY`, 커널 원문, `result.json` 사이의 PID·cookie 일치, 실행 코드 SHA, 118바이트·한 줄 수신, 종료 코드 `0/0`과 `DETACHED`, 컴파일과 테스트 5개 통과 근거를 대조해 **PASS**를 확인했음.

검토자는 실행 SHA의 소스와 workflow, 수신된 커널 원문, PID·cookie, 로더의 준비·해제 기록을 대조할 수 있음. 같은 workflow를 다시 실행하면 새 PID·cookie로 재현할 수 있음. 메시지가 없거나 다른 PID·cookie인 경우 성공으로 통과하지 않는지는 [검증 테스트](../../experiments/hello-world/test_run.py)에서 확인함.

로더 정상 종료와 `DETACHED` 확인은 이 예제가 생성한 연결의 정리 절차를 검증함. 시스템 전체의 모든 eBPF 객체가 없어졌다고 주장하지 않음.

이번 실험의 성공은 해당 실행 환경에서 관측·출력 경로가 작동함을 뜻함. 성능 개선이나 기존 PoC의 구현 선택 가설에 대한 결론을 바꾸지 않음.
