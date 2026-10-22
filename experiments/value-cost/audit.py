#!/usr/bin/env python3
"""Post-run independent arithmetic/raw-text audit; does not rerun acquisition."""
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

def audit(root):
    manifest=(root/"SHA256SUMS.txt").read_text().splitlines()
    for entry in manifest:
        expected,rel=entry.split("  ",1)
        assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==expected,rel
    summary=json.loads((root/"summary.json").read_text())
    records=[]
    for phase,expected_count in (("acquire",144),("holdout",48)):
        data=[json.loads(s) for s in (root/phase/"raw.jsonl").read_text().splitlines()]
        assert len(data)==expected_count
        for row in data:
            folder=root/phase/row["folder"]
            on_disk=json.loads((folder/"result.json").read_text())
            assert all(on_disk[k]==row[k] for k in on_disk)
            target=[json.loads(s) for s in (folder/"target.stdout").read_text().splitlines()]
            assert target[0]["ready"] and target[1]==row["result"]
            assert row["result"]["bytes"]==row["size"]*row["copies"]
            assert row["correct"] and not (folder/"target.stderr").read_text().strip()
        records.extend(data)
    traced=0
    for folder in sorted((root/"acquire").iterdir()):
        if not folder.is_dir() or not (folder/"collector.stdout").exists():continue
        result=json.loads((folder/"result.json").read_text())
        text=(folder/"collector.stdout").read_text()
        parsed={}
        for name,key,value in re.findall(r"^@(\w+)\[(\d+)\]:\s*(\d+)\s*$",text,re.M):
            assert (name,key) not in parsed,"duplicate map snapshot"
            parsed[(name,key)]=int(value)
        reads=result["copies"]*((result["size"]+result["chunk"]-1)//result["chunk"]+1)
        writes=result["copies"]*((result["size"]+result["chunk"]-1)//result["chunk"])
        for name,key,expected in (("calls","0",reads),("calls","1",writes),
             ("bytes","0",result["size"]*result["copies"]),("bytes","1",result["size"]*result["copies"]),
             ("errors","0",0),("errors","1",0)):
            assert parsed.get((name,key),0)==expected,(folder,name,key,expected,parsed)
        assert not (folder/"collector.stderr").read_text().strip()
        assert result["collector_resource"]["exit"]==0
        traced+=1
    assert traced==50
    for case in ("small","large"):
        for chunk in (32768,65536):
            bymode={m:sorted([r for r in records if r["case"]==case and r["chunk"]==chunk and r["mode"]==m],key=lambda r:r["round"])
                    for m in ("native","go","go-ebpf")}
            for rs in bymode.values():assert [r["round"] for r in rs]==list(range(12))
            ratios=[e["result"]["duration_ns"]/g["result"]["duration_ns"] for e,g in zip(bymode["go-ebpf"],bymode["go"])]
            assert abs(statistics.median(ratios)-summary["cases"][case][str(chunk)]["ebpf_over_go_hot_ratio"]["median"])<1e-12
    seal=json.loads((root/"sealed-go-choice.json").read_text())
    holdout_env=json.loads((root/"holdout/environment.json").read_text())
    assert seal["epoch"]<holdout_env["started_epoch"]
    cpu_samples={}
    for path in root.glob("*-go-profiles/cpu-top.txt"):
        match=re.search(r"Total samples = ([^\n]+)",path.read_text())
        assert match
        cpu_samples[path.parent.name]=match.group(1)
    return {"run":root.name,"manifest_files_verified":len(manifest),"timed_trials":len(records),
            "traced_timed_trials":48,"traced_controls":2,"seal_precedes_holdout":True,
            "go_cpu_profile_aggregate_samples":cpu_samples,"status":"PASS"}

if __name__=="__main__":
    print(json.dumps([audit(Path(s)) for s in sys.argv[1:]],indent=2,sort_keys=True))
