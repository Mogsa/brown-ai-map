"""Final pass: papers_labeled.jsonl -> papers_final.jsonl.

1. Merge duplicates judged "same" in labels/dups_*.jsonl (union-find; keep the richest record).
2. Apply hand corrections from the 50-paper audit (audit_report.md).
3. Enforce consistency: not AI  <=>  code 0x.
Every change is logged to finalize_log.csv. Run: python3 finalize.py
"""
import csv
import glob
import json

from clean import merge, richness

# From audit_report.md (2026-09-30). pid -> fields to set; None drops the record.
AUDIT_FIXES = {
    362: {"sub": "0x", "is_ai": False},          # statistical proof, no ML
    391: {"sub": "0x", "is_ai": False},          # super-resolution without learning
    811: {"sub": "9f", "is_ai": True},           # deep learning used to tune stimulation
    41: {"attribution_ok": True},                # Pavlick confirmed as author
    909: None,                                   # 2023 patent application, not a paper
    911: None,                                   # not found anywhere online
    786: {"sub": "8f"}, 518: {"sub": "9x"}, 701: {"sub": "2f"}, 823: {"sub": "5h"},
    849: {"sub": "5b", "year": 2025},
}


# Duplicates confirmed online by the audit but missed by the pair judges.
MANUAL_SAME = [(88, 926)]


def find(parent: dict, x: int) -> int:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def merge_duplicates(papers: dict[int, dict], log: list) -> dict[int, dict]:
    parent = {pid: pid for pid in papers}
    for f in glob.glob("labels/dups_*.jsonl"):
        for line in open(f):
            j = json.loads(line)
            if j["same"] and j["a"] in papers and j["b"] in papers:
                parent[find(parent, j["a"])] = find(parent, j["b"])
    for a, b in MANUAL_SAME:
        if a in papers and b in papers:
            parent[find(parent, a)] = find(parent, b)
    groups: dict[int, list] = {}
    for pid in papers:
        groups.setdefault(find(parent, pid), []).append(papers[pid])
    kept = {}
    for members in groups.values():
        members.sort(key=richness, reverse=True)
        head = members[0]
        for other in members[1:]:
            merge(head, other)
            log.append(("merged_duplicate", head["pid"], other["pid"], other["title"][:90]))
        kept[head["pid"]] = head
    return kept


def apply_fixes(papers: dict[int, dict], names: dict[str, str], log: list) -> None:
    for pid, fix in AUDIT_FIXES.items():
        if pid not in papers:
            continue
        if fix is None:
            log.append(("dropped", pid, "", papers.pop(pid)["title"][:90]))
            continue
        papers[pid].update(fix)
        log.append(("audit_fix", pid, json.dumps(fix), papers[pid]["title"][:90]))
    for p in papers.values():
        if not p["is_ai"] and p["sub"] != "0x":
            log.append(("not_ai_to_0x", p["pid"], p["sub"], p["title"][:90]))
            p["sub"] = "0x"
        p["area"] = p["sub"][0]
        p["sub_name"] = names.get(p["sub"], "")


def main() -> None:
    from merge_labels import vocab
    names = vocab()
    papers = {json.loads(l)["pid"]: json.loads(l) for l in open("papers_labeled.jsonl")}
    log: list[tuple] = []
    papers = merge_duplicates(papers, log)
    apply_fixes(papers, names, log)
    with open("papers_final.jsonl", "w") as fh:
        for p in sorted(papers.values(), key=lambda p: p["pid"]):
            fh.write(json.dumps(p) + "\n")
    with open("finalize_log.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["action", "pid", "detail", "title"])
        w.writerows(log)
    ai = sum(1 for p in papers.values() if p["is_ai"])
    kinds = {k: sum(1 for x in log if x[0] == k) for k in {x[0] for x in log}}
    print(f"{len(papers)} papers ({ai} AI/ML); changes: {kinds}")


if __name__ == "__main__":
    main()
