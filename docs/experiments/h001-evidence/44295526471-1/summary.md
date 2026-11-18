# eBPF Hello World — PASS

테스트 프로세스의 execve에서 나온 Hello World를 1건 받고 정상 종료했어.

## 커널에서 받은 메시지

```text
         python3-2752    [000] ...31   265.976548: bpf_trace_printk: Hello World! pid=2752 cookie=9099829962833102368
```

## 확인 결과

| 항목 | 결과 |
| --- | --- |
| eBPF 연결 완료 | ✅ |
| 대상 메시지 수 | 1 / 기대 1건 |
| 테스트 프로그램 종료 코드 | 0 |
| 로더 종료 코드 | 0 |
| eBPF 연결 정리 확인 | ✅ |
| 대상 PID | `2752` |
| 실행 식별값 | `9099829962833102368` |
| 커널 | `7.0.0-1014-aws` |
| 실행한 코드 | `71d492b88a38c9504aedd48f98e22edfc6ab54b6` |

메시지 전달 경로: `execve` 이벤트 → eBPF의 `bpf_printk()` → `trace_pipe` 수집 → 이 화면.

메시지는 커널 추적 스트림에서 읽은 원문이야. PID와 이번 실행의 식별값이 모두 일치해야 집계해.

이 실험은 기능 확인용이야. 성능 측정이나 기존 PoC 가설에 대한 판정은 포함하지 않아.

자세한 과정은 **Hello World 실행 및 커널 메시지 확인** 로그, 원본 파일은 아래 Artifact에서 볼 수 있어.

[이 실행 열기](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44295526471)
