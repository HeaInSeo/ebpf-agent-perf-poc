#!/usr/bin/env python3
"""Summarize observed evidence, never synthesize a PASS from expected output."""
import json
import os
from pathlib import Path
import sys

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
experiments = {
    "ex01": "XDP_PASS 연결·해제와 통신 복구",
    "ex02": "실행 중 BCC kprobe와 bpftool xlated/JIT 조사",
    "ex03": "tail call 4개 프로그램과 Map 확인",
    "ex04": "XDP_ABORTED(0)의 격리 패킷 차단·통신 복구",
}
lines = ["# Chapter 3 — eBPF 실습 결과", "",
         "GitHub-hosted Ubuntu 러너에서 생성한 실제 관측값만 표시함.", "",
         "| 연습 | 내용 | 판정 |", "|---|---|---|"]
passed = 0
details = []
for key, label in experiments.items():
    result_path = out / f"{key}.json"
    if result_path.exists():
        data = json.loads(result_path.read_text())
        status = data.get("status", "INVALID")
    else:
        data = {}
        status = "FAIL/NOT_RUN"
    passed += status == "PASS"
    lines.append(f"| {key} | {label} | **{status}** |")
    if data:
        details.extend(["", f"### {key} 관측값", "", "```json",
                        json.dumps(data, ensure_ascii=False, indent=2), "```"])
lines += ["", f"**총 판정: {passed}/4 PASS**", ""] + details + ["",
          "프로그램별 xlated/JIT 덤프, 원본 로그, 환경 정보와 해시는 Artifact에 저장됨.",
          "JIT 코드가 없는 환경은 해당 덤프를 사용 불가로 표시하며 임의 생성하지 않음."]
summary = "\n".join(lines) + "\n"
(out / "summary.md").write_text(summary)
print(summary)
step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
if step_summary:
    with open(step_summary, "a") as file:
        file.write(summary)
sys.exit(0 if passed == 4 else 1)
