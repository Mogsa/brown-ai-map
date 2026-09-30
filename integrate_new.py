"""Fold incrementally added papers (add_faculty.py) into papers_final.jsonl.

Applies labels/labels_new.jsonl to papers_new.jsonl, merges duplicates judged in
labels/dups_new.jsonl, and appends the rest. Pipeline order:
finalize.py -> add_faculty.py <names> -> (label + dedupe papers_new) -> integrate_new.py
Run: python3 integrate_new.py
"""
import json

from clean import merge, richness
from merge_labels import vocab

FINAL, NEW = "papers_final.jsonl", "papers_new.jsonl"


def main() -> None:
    names = vocab()
    final = {p["pid"]: p for p in map(json.loads, open(FINAL))}
    new = {p["pid"]: p for p in map(json.loads, open(NEW))}
    labels = {l["pid"]: l for l in map(json.loads, open("labels/labels_new.jsonl"))}
    for pid, p in new.items():
        lab = labels[pid]
        assert lab["sub"] in names, f"unknown code {lab['sub']}"
        p.update(sub=lab["sub"], sub_name=names[lab["sub"]], area=lab["sub"][0], sub2=lab.get("sub2"),
                 is_ai=lab["is_ai"] and lab["sub"] != "0x", attribution_ok=lab.get("attribution_ok", True),
                 label_basis=lab.get("basis", "abstract"), label_fit=lab.get("fit", "good"),
                 label_why=lab.get("why", ""))
    pool = {**final, **new}
    merged = 0
    for j in map(json.loads, open("labels/dups_new.jsonl")):
        a, b = pool.get(j["a"]), pool.get(j["b"])
        if not (j["same"] and a and b):
            continue
        keep, drop = sorted([a, b], key=richness, reverse=True)
        merge(keep, drop)
        pool.pop(drop["pid"])
        merged += 1
    with open(FINAL, "w") as fh:
        for p in sorted(pool.values(), key=lambda p: p["pid"]):
            fh.write(json.dumps(p) + "\n")
    added = sum(1 for pid in pool if pid in new)
    print(f"added {added} new papers ({sum(1 for pid in pool if pid in new and pool[pid]['is_ai'])} AI/ML); merged {merged} duplicates; total {len(pool)}")


if __name__ == "__main__":
    main()
