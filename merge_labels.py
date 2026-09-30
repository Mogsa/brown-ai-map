"""Merge per-paper labels into papers_clean.jsonl -> papers_labeled.jsonl.

labels/labels_*.jsonl hold the first pass; labels/reassign.jsonl overrides poor fits
with codes from the v2 vocabulary. Area = first character of the sub code.
Run: python3 merge_labels.py
"""
import glob
import json
import re
from collections import Counter

VOCAB = "label_vocab.md"


def vocab() -> dict[str, str]:
    codes = {}
    for line in open(VOCAB):
        m = re.match(r"\s+(\d[a-z])\s+(.+)", line)
        if m:
            codes[m.group(1)] = m.group(2).strip()
    return codes


def load(pattern: str) -> dict[int, dict]:
    return {json.loads(l)["pid"]: json.loads(l) for f in sorted(glob.glob(pattern)) for l in open(f)}


def main() -> None:
    names = vocab()
    first = load("labels/labels_*.jsonl")
    second = load("labels/reassign.jsonl")
    papers = [json.loads(l) for l in open("papers_clean.jsonl")]
    missing = [p["pid"] for p in papers if p["pid"] not in first]
    assert not missing, f"unlabelled pids: {missing[:10]}"
    for p in papers:
        lab = {**first[p["pid"]], **second.get(p["pid"], {})}
        assert lab["sub"] in names, f"unknown code {lab['sub']} for pid {p['pid']}"
        p.update(
            sub=lab["sub"], sub_name=names[lab["sub"]], area=lab["sub"][0],
            sub2=lab.get("sub2"), is_ai=lab.get("is_ai", True) and lab["sub"] != "0x",
            attribution_ok=lab.get("attribution_ok", True),
            label_basis=lab.get("basis", "abstract"), label_fit=lab.get("fit", "good"),
            label_why=lab.get("why", ""),
        )
    with open("papers_labeled.jsonl", "w") as fh:
        for p in papers:
            fh.write(json.dumps(p) + "\n")
    ai = [p for p in papers if p["is_ai"]]
    print(f"{len(papers)} papers; {len(ai)} AI/ML; "
          f"{sum(not p['attribution_ok'] for p in papers)} attribution flags; "
          f"{sum(p['label_fit'] == 'poor' for p in papers)} still poor fits")
    print("by area:", sorted(Counter(p["area"] for p in ai).items()))


if __name__ == "__main__":
    main()
