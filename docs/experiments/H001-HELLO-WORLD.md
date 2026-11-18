# H001 — Actions 화면에서 eBPF Hello World 확인

**현재 상태: 첫 실행 대기. 아래는 실행 전에 정한 기준이며, 아직 PASS를 주장하지 않는다.**

[쉽게 따라 하는 안내](../../experiments/hello-world/README.md) · [수동 실행 workflow](../../.github/workflows/hello-world.yml)

## 연구 질문 / 범위

**가설:** GitHub-hosted `ubuntu-24.04` 러너에서 C/libbpf Hello World를 적재·연결한 뒤 대상 프로세스의 `execve()`를 발생시키면, eBPF가 기록한 메시지 한 건을 Actions 로그와 Summary에 표시할 수 있다.

대상 저장소는 `HeaInSeo/ebpf-agent-perf-poc`이며, 작업 시작 시 `main`은 `2e53f8efae138b61dbb952f898e6bb68a6a7ca94`다. 실행에 사용한 실제 코드 SHA는 시도별 기록에 남긴다.

예제의 출처는 `HeaInSeo/ebpf-study` 커밋 `9b9da7308f13828f557ec5c05e5aff663da4e7b4`의 [hello.bpf.c](https://github.com/HeaInSeo/ebpf-study/blob/9b9da7308f13828f557ec5c05e5aff663da4e7b4/c-libbpf/src/hello.bpf.c)와 [hello.c](https://github.com/HeaInSeo/ebpf-study/blob/9b9da7308f13828f557ec5c05e5aff663da4e7b4/c-libbpf/src/hello.c)다. 원본의 tracepoint·`bpf_printk()`·libbpf 로더 구조를 바탕으로 PID 구분, 실행별 cookie, 자동 종료와 증거 수집을 추가한다.

이번 범위는 컴파일, 커널 적재·연결, 테스트 이벤트 발생, 실제 커널 출력 수신, 결과 표시와 연결 해제다. 프로그램 성능, Cilium 데이터 경로, 다른 eBPF hook 또는 모든 커널에서의 호환성을 평가하지 않는다.

### 사전 판정 기준

| 판정 | 기준 |
| --- | --- |
| **PASS** | 빌드·적재·연결 성공 후 대상 프로세스의 `execve()`를 발생시키고, PID와 cookie가 일치하는 커널 메시지를 정확히 한 건 수신한다. 대상 프로세스와 로더가 정상 종료하고 로더의 연결 해제 기록을 확인한다. |
| **FAIL** | 필요한 환경을 갖춘 실행에서 빌드·적재·연결 오류, 제한 시간 내 메시지 미수신, 메시지 수 불일치, 비정상 종료 또는 정리 실패가 발생한다. |
| **BLOCKED** | 필수 도구·권한·tracefs·tracepoint 등 실행 전제 조건이 없어 실험을 수행할 수 없다. 통과로 취급하지 않는다. |

이 기능 시험의 실행기는 `PASS`, `FAIL`, `BLOCKED`를 사용한다. `BLOCKED`도 Actions 작업을 실패로 끝낸다. 작업 취소나 증거 누락으로 완료되지 않은 실행은 성공으로 해석하지 않는다.

셸 명령의 정상 종료나 로더의 준비 메시지만으로 PASS를 부여하지 않는다. 수집기는 `trace_pipe`에서 읽은 메시지를 검증한다.

## 재현 환경과 입력

- Workflow: `eBPF Hello World (manual)`, `workflow_dispatch` 전용.
- 러너: GitHub-hosted `ubuntu-24.04`. 실행별 이미지·커널·아키텍처·도구 버전과 코드 SHA를 결과에 남긴다.
- 권한: workflow 토큰은 `contents: read`. 커널 적재와 추적 버퍼 읽기는 일회성 러너에서 `sudo`로 수행한다.
- 입력: 대기 중인 테스트 프로세스 한 개. 로더의 `READY`를 확인한 뒤 `/usr/bin/true`로 `execve()` 한 번을 발생시킨다.
- 구분 값: 대상 PID와 실행별 무작위 cookie. 실제 값은 원시 로그·결과에 보관한다.
- 수집: `/sys/kernel/tracing/trace_pipe`. 대상 PID와 cookie가 모두 일치하는 메시지만 이번 실험의 증거로 사용한다.
- 종료: 수신 대기 한도는 8초다. 로더에 종료 신호를 보내고 `DETACHED` 및 종료 코드를 확인한다. 로더에도 별도의 30초 제한이 있다.
- 계측 조건: 기능 검증용 1회 실행이며 성능 수치를 계산하지 않는다. `bpf_printk()`와 로그 수집의 비용을 벤치마크에 섞지 않는다.

## 재현 절차

1. [Actions workflow](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/workflows/hello-world.yml)에서 **Run workflow → main → Run workflow**를 선택한다.
2. 빌드 단계의 `make -C experiments/hello-world` 결과를 확인한다.
3. **커널에서 Hello World 확인** 작업의 **Hello World 실행 및 커널 메시지 확인** 단계에서 실제 수신 메시지와 판정을 확인한다.
4. Summary와 `hello-world-실행번호-시도번호` Artifact를 함께 확인한다.

빌드 후 별도로 재현할 때 저장소 최상위에서 실행하는 명령은 다음과 같다.

```bash
mkdir -p results/hello-world
git rev-parse HEAD > results/hello-world/source-sha.txt
sudo python3 -u experiments/hello-world/run.py --output results/hello-world
```

`run.py`는 출력 폴더의 `source-sha.txt`를 읽어 실행 코드를 식별한다. Git의 저장소 소유권 검사로 인한 `sudo` 실행 오류를 피하도록 일반 사용자로 SHA를 먼저 기록한다. Actions workflow는 이 파일을 자동으로 준비한다.

실제 실행 명령과 옵션의 정본은 해당 실행 SHA의 [workflow](../../.github/workflows/hello-world.yml)다. 로그에는 명령과 오류를 보존한다. `run.py`가 요약을 만들고, workflow의 후속 단계가 `GITHUB_STEP_SUMMARY`에 게시한다.

## 작업 및 시도별 기록

| 시도 | 코드 SHA | 실행 링크 | 측정·오류 근거 | 판정 |
| --- | --- | --- | --- | --- |
| 1 | 실행 후 기록 | 실행 후 기록 | 실행 후 기록 | 실행 대기 |

실행 후 이 표에 실제 SHA·run URL·job 결과·Artifact ID와 해시를 기록한다. 실패가 발생하면 해당 행을 남기고, 수정 후 실행은 새 행으로 추가한다.

### 보관할 증거

`results/hello-world/`에 다음 파일을 모아 Artifact로 업로드한다.

- `environment.json`: 실행 환경과 재현 정보.
- `source-sha.txt`: 일반 사용자 권한으로 기록한 실행 코드 SHA.
- `result.json`: 판정, 대상 PID·cookie, 수신 결과와 종료 상태.
- `kernel-events.log`: 이번 실험에 대응하는 커널 메시지 원문.
- `loader.stdout.log`, `loader.stderr.log`: 연결 준비·해제 기록과 오류.
- `setup.log`, `build.log`, `probe.log`: 준비·빌드·실행 과정.
- `summary.md`: Actions Summary에 표시한 한국어 요약.
- `SHA256SUMS.txt`: 결과 파일의 무결성 확인용 해시.

Artifact는 30일간 보관한다. 보존 기간 이후에도 검토할 수 있도록, 첫 완료 실행의 검토된 최소 원시 증거와 run 메타데이터를 이 문서와 함께 보존한다. 실제 영구 보존 경로와 Artifact 해시는 실행 후 기록한다.

## 분석 및 독립 검토

현재는 실행 전이므로 관찰 결과와 최종 판정이 없다.

검토자는 실행 SHA의 소스와 workflow, 수신된 커널 원문, PID·cookie, 로더의 준비·해제 기록을 대조할 수 있다. 같은 workflow를 다시 실행하면 새 PID·cookie로 재현할 수 있다. 메시지가 없거나 다른 PID·cookie인 경우 성공으로 통과하지 않는지는 [검증 테스트](../../experiments/hello-world/test_run.py)에서 확인한다.

로더 정상 종료와 `DETACHED` 확인은 이 예제가 생성한 연결의 정리 절차를 검증한다. 시스템 전체의 모든 eBPF 객체가 없어졌다고 주장하지 않는다.

이번 실험의 성공은 해당 실행 환경에서 관측·출력 경로가 작동함을 뜻한다. 성능 개선이나 기존 PoC의 구현 선택 가설에 대한 결론을 바꾸지 않는다.
