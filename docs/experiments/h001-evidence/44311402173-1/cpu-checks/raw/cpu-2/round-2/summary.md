# eBPF Hello World — PASS

테스트 프로세스의 execve에서 나온 Hello World를 1건 받고 정상 종료함.

## 커널에서 받은 메시지

```text
            true-2766    [002] ...3.    69.284044: bpf_trace_printk: Hello World! pid=2766 cookie=2548141379138587330
```

## 확인 결과

| 항목 | 결과 |
| --- | --- |
| eBPF 연결 완료 | ✅ |
| 대상 메시지 수 | 1 / 기대 1건 |
| 테스트 프로그램 종료 코드 | 0 |
| 로더 종료 코드 | 0 |
| eBPF 연결 정리 확인 | ✅ |
| 대상 PID | `2766` |
| 지정한 대상 CPU | 2 |
| 대상 CPU affinity | `[2]` |
| 실행 식별값 | `2548141379138587330` |
| 커널 | `7.0.0-1017-azure` |
| 실행한 코드 | `c6eb3d9723d04587cd4ff4552b7402b8495ef683` |

메시지 전달 경로: `execve` 이벤트 → eBPF의 `bpf_printk()` → `trace_pipe` 수집 → 이 화면.

메시지는 커널 추적 스트림에서 읽은 원문임. PID와 이번 실행의 식별값이 모두 일치해야 집계함.

이 실험은 기능 확인용임. 성능 측정이나 기존 PoC 가설에 대한 판정은 포함하지 않음.

자세한 과정은 **Hello World 실행 및 커널 메시지 확인** 로그, 원본 파일은 아래 Artifact에서 확인할 수 있음.

[이 실행 열기](https://github.com/HeaInSeo/ebpf-agent-perf-poc/actions/runs/44311402173)
