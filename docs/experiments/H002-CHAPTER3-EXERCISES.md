# H002 — Chapter 3: eBPF 프로그램 구조 실습

## 목적

『Learning eBPF』 3장의 4개 Exercise를 GitHub-hosted Ubuntu 러너에서 직접 검증함.
원본 학습자료: https://github.com/lizrice/learning-ebpf (chapter2, chapter3).
학습 범위는 H001과 별개이며, 기존 성능 PoC의 가설·판정을 변경하지 않음.

## 실행

1. GitHub Actions의 `Chapter 3 eBPF Exercises (isolated)`를 실행함.
2. 같은 저장소의 PR에서 변경된 실험 코드도 자동 검증함(같은 저장소 PR만 허용).
3. Summary에서 4개 실습 PASS/FAIL과 관측값을 확인함.
4. Artifact에서 커널 프로그램 메타데이터, xlated/JIT, XDP 네트워크 로그, 해시를 확인함.

## 연습문제 및 판정

| ID | 내용 | 반드시 확인할 사항 |
|---|---|---|
| EX01 | XDP_PASS attach/detach | 가상 veth에 연결 전·후 ping 성공, 프로그래밍 연결 및 해제 확인 |
| EX02 | hello-map.py 방식 BCC 검사 | 살아 있는 kprobe의 이름·ID·Map 확인, xlated/JIT 덤프, execve 실측 증가 |
| EX03 | hello-tail.py 방식 검사 | raw_tracepoint 진입 프로그램과 3개 tail callee를 개별 식별, Map 카운터 증가 |
| EX04 | XDP_ABORTED 반환 0 | 격리된 veth에서만 ping 차단을 관측하고 detach 후 통신 복원 |

## 안전 경계

- XDP 연결 대상은 두 개의 일회성 network namespace 내부 veth에 한정함.
- 호스트 `eth0`, 원격 개발 서버, Kubernetes 노드 인터페이스에는 절대 attach하지 않음.
- XDP 실험은 GitHub-hosted Actions 러너일 때만 실행 허용함.
- EXIT 트랩으로 XDP detach 및 양쪽 namespace를 삭제함.
- XDP_ABORTED 차단은 성공 조건이 아니라 복원까지 확인되어야 PASS임.
- BCC 프로그램은 종료 시 프로세스 핸들을 해제하고 bpftool에서 ID 소멸을 검사함.
- 코드 컴파일만으로 PASS 금지. 실제 커널 로드, bpftool 관측, 테스트 패킷/시스템콜을 요구함.
- JIT 비지원이면 실제 관측값을 그대로 기록함. 존재하지 않는 머신코드 덤프를 만들지 않음.

## 재현 범위

Ubuntu 24.04 GitHub-hosted x86_64 runner, BCC, bpftool, clang, iproute2 사용.
커널·Ubuntu 이미지·패키지 버전은 실행별 로그에 저장함.
XDP 드라이버 지원 및 BCC의 커널 기능 때문에 다른 러너에서는 결과가 달라질 수 있음.

## 기록 방식

원본 `ex01.json` ~ `ex04.json`, stdout 로그, bpftool 덤프, checksum을 보존함.
실행하지 못한 항목은 PASS가 아닌 FAIL/NOT_RUN으로 표시함.
