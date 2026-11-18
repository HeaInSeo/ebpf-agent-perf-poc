## CPU별 eBPF 재현 확인 — PASS

허용된 모든 CPU에서 raw 경로의 실제 커널 메시지 수신을 반복 확인하고 typed 대조 결과를 보존함.

- 허용된 CPU: `[0, 1, 2, 3]`
- 실행 코드: `c6eb3d9723d04587cd4ff4552b7402b8495ef683`
- raw 검증: **8 / 8 통과**
- typed 대조: **4 / 4 기록 검증 완료**

| 경로 | CPU | 회차 | 메시지 수 | 출력 CPU | 판정 |
| --- | ---: | ---: | ---: | --- | --- |
| raw | 0 | 1 | 1 | 0 | PASS |
| raw | 0 | 2 | 1 | 0 | PASS |
| typed | 0 | 1 | 1 | 0 | PASS |
| raw | 1 | 1 | 1 | 1 | PASS |
| raw | 1 | 2 | 1 | 1 | PASS |
| typed | 1 | 1 | 0 | — | 0건 관측 (대조) |
| raw | 2 | 1 | 1 | 2 | PASS |
| raw | 2 | 2 | 1 | 2 | PASS |
| typed | 2 | 1 | 0 | — | 0건 관측 (대조) |
| raw | 3 | 1 | 1 | 3 | PASS |
| raw | 3 | 2 | 1 | 3 | PASS |
| typed | 3 | 1 | 0 | — | 0건 관측 (대조) |

raw 경로는 CPU마다 2회 실행하며, 매번 지정한 CPU의 실제 커널 메시지 1건과 정상 종료·연결 해제가 모두 필요함.

typed 경로는 기존 syscall tracepoint의 대조 실험임. 정상 연결·대상 실행·정리 후 메시지만 0건인 경우를 미수신 관측으로 보존함. 다른 오류는 전체 검증 실패로 처리함.

시도별 원본 메시지, 실행 환경, PID·cookie, stdout·stderr는 `cpu-checks/{raw,typed}/cpu-번호/round-회차/`에 보관함.
