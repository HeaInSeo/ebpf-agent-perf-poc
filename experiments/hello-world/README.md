# GitHub Actions에서 eBPF Hello World 보기

**GitHub에서 실행 버튼을 누르면, 리눅스 커널의 eBPF 프로그램이 만든 `Hello World!`를 작업 로그와 실행 요약에서 볼 수 있어.** 직접 서버에 접속하거나 다른 터미널을 열 필요는 없어.

이 예제는 `ebpf-study`의 Hello World를 GitHub Actions에서 자동으로 실행하고 확인하도록 옮긴 학습 실험이야.

## 직접 확인하는 방법

1. [eBPF Hello World (manual) Actions](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/workflows/hello-world.yml)를 열어.
2. **Run workflow**를 누르고, 브랜치가 **main**인지 확인한 뒤 실행해.
3. 새 실행 항목을 열어. 완료되면 **Summary**에서 성공 여부와 수신한 메시지를 확인할 수 있어.
4. 실제 과정을 보려면 **커널에서 Hello World 확인** 작업을 열고 **Hello World 실행 및 커널 메시지 확인** 단계를 펼쳐.
5. 원본 파일이 필요하면 실행 화면의 **Artifacts**에서 `hello-world-실행번호-시도번호`를 내려받아.

`Run workflow` 버튼을 사용하려면 저장소에 실행 권한이 있는 계정으로 로그인해야 해. 이 workflow는 수동 실행용이야.

## 어떤 일이 일어나는 걸까?

테스트는 다음 순서로 진행돼.

1. **컴파일:** C 소스를 eBPF 오브젝트와 사용자 공간 로더로 각각 빌드해.
2. **연결:** 로더가 eBPF 프로그램을 커널에 올리고 `execve()` 이벤트에 연결해.
3. **이벤트 발생:** 연결 완료를 확인한 뒤, 테스트 프로세스가 `/usr/bin/true`를 실행해. 이때 `execve()`가 호출돼.
4. **커널 메시지 수신:** eBPF가 `Hello World!`를 기록하면, 수집기가 커널의 `trace_pipe`에서 읽어 Actions 로그에 표시해.
5. **검증과 종료:** 8초 안에 이번 테스트의 메시지를 정확히 한 건 받았는지 확인하고 로더와 연결을 정리해.

여기서 `execve()`는 **프로세스가 새 프로그램을 실행할 때 사용하는 시스템 호출**이야. `/usr/bin/true`는 정상 종료하는 작은 프로그램이라 이벤트를 만들기 위한 대상으로 사용해.

## 왜 출력 프로그램이 따로 필요할까?

일반 C 프로그램의 `printf()`는 표준 출력으로 글자를 보내. Actions는 이 출력을 로그에 보여줘.

eBPF의 `bpf_printk()`는 **커널의 추적 버퍼에 메시지를 기록해.** 그래서 이 예제에서는 `/sys/kernel/tracing/trace_pipe`를 읽어 표준 출력으로 전달해. 로그에 나타나는 커널 메시지는 그곳에서 실제로 읽은 원문이야.

메시지 형식은 다음과 같아. 숫자는 실행마다 달라져.

```text
Hello World! pid=12345 cookie=67890
```

- **pid:** 이번에 실행한 테스트 프로세스의 번호.
- **cookie:** 이번 실행을 구분하는 무작위 숫자. 인증 정보는 아니야.

eBPF는 지정한 PID만 관찰하고, 수집기는 PID와 cookie가 모두 맞는 메시지를 확인해. 이렇게 해야 러너에서 동시에 실행 중인 다른 프로그램이나 이전 메시지를 잘못 성공으로 판단하지 않아.

## 파일을 읽는 순서

| 파일 | 하는 일 |
| --- | --- |
| [hello.bpf.c](hello.bpf.c) | 커널에서 실행돼. 대상 프로세스의 `execve()`를 확인하고 메시지를 기록해. |
| [hello.c](hello.c) | 사용자 공간에서 실행돼. eBPF 적재, PID·cookie 설정, 이벤트 연결과 해제를 담당해. |
| [run.py](run.py) | 테스트 프로세스와 로더를 실행하고, 커널 메시지를 수집·검증해. |
| [Makefile](Makefile) | eBPF 코드와 일반 C 로더를 각각 컴파일해. |
| [hello-world.yml](../../.github/workflows/hello-world.yml) | GitHub Actions의 준비, 빌드, 실행, 요약과 결과 보관을 연결해. |

빌드는 `make -C experiments/hello-world`로 해. 이 예제는 커널 자료구조의 필드를 읽지 않으므로 생성된 `vmlinux.h`가 필요하지 않아.

빌드 후 별도로 재현할 때는 저장소 최상위에서 다음 명령을 실행해. 커널 실행은 필요한 도구와 권한을 갖춘 실험용 리눅스 환경에서 수행해.

```bash
mkdir -p results/hello-world
git rev-parse HEAD > results/hello-world/source-sha.txt
sudo python3 -u experiments/hello-world/run.py --output results/hello-world
```

`source-sha.txt`에는 어떤 코드로 실행했는지 기록해. `sudo`로 실행한 프로그램이 저장소 소유권 때문에 Git 조회를 거부당하지 않도록, 일반 사용자로 먼저 기록하는 거야. Actions workflow는 이 준비를 자동으로 수행해.

## 결과는 어디에 남을까?

| 위치 | 내용 |
| --- | --- |
| Actions 작업 로그 | 빌드 과정, 연결 상태, 실제 커널 메시지, 최종 판정 |
| Actions Summary | 사람이 바로 읽을 수 있는 한국어 실행 요약 |
| `kernel-events.log` | 이번 PID·cookie에 해당하는 커널 메시지 원문 |
| `loader.stdout.log` / `loader.stderr.log` | 로더의 연결·정리 기록과 오류 |
| `result.json` / `environment.json` | 판정과 재현 환경 |
| `SHA256SUMS.txt` | 보관한 결과 파일의 해시 |

이 파일들은 `results/hello-world/`에 모여 Artifact로 30일간 보관돼. 첫 실행의 실제 링크와 증거는 [H001 실험 기록](../../docs/experiments/H001-HELLO-WORLD.md)에서 확인할 수 있어.

## 이 실험이 확인하는 범위

성공하면 **“이번 러너에서 eBPF를 올리고, 특정 이벤트에 연결하고, 커널이 만든 메시지를 Actions까지 가져왔다”**고 말할 수 있어.

이것은 기능 확인용 실험이야. 출력 비용이 포함되므로 성능 벤치마크와 따로 실행해. 이후 Tail Call이나 BPF Map을 공부할 때도 이 실행·수집 구조를 출발점으로 사용할 수 있어.

## 원본과 공식 참고 자료

원본은 `HeaInSeo/ebpf-study`의 고정 커밋 `9b9da7308f13828f557ec5c05e5aff663da4e7b4`야.

- [원본 eBPF 코드](https://github.com/HeaInSeo/ebpf-study/blob/9b9da7308f13828f557ec5c05e5aff663da4e7b4/c-libbpf/src/hello.bpf.c)
- [원본 로더](https://github.com/HeaInSeo/ebpf-study/blob/9b9da7308f13828f557ec5c05e5aff663da4e7b4/c-libbpf/src/hello.c)

이 저장소의 예제에는 자동 검증을 위한 PID·cookie 구분, 종료 조건, 로그 수집을 추가했어. 원본 `ebpf-study` 저장소는 수정하지 않아.

- [libbpf의 `bpf_trace_printk()` 설명](https://github.com/libbpf/libbpf/blob/master/src/bpf_helper_defs.h)
- [GitHub Actions 로그 보는 방법](https://docs.github.com/en/actions/how-tos/monitor-workflows/use-workflow-run-logs)
- [GitHub Actions 실행 요약 작성](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary)
