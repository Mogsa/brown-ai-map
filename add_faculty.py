"""Incrementally add faculty to papers_final.jsonl without re-labelling existing papers.

For each named person: fetch their 2024+ OpenAlex works, enrich from Semantic Scholar,
then either tag an existing paper (same normalised title) or create a new record with a
fresh pid (>= 10000). New records go to papers_new.jsonl for labelling and dedupe.
Run: python3 add_faculty.py "Name" ["Name" ...]
"""
import csv
import json
import re
import sys

from clean import backfill, check_authors
from collect import EXCLUDED_TITLE, EXCLUDED_TYPES, author_works, enrich_from_s2, norm_title, to_record

FINAL, NEW = "papers_final.jsonl", "papers_new.jsonl"
FIRST_NEW_PID = 10000


def main(names: list[str]) -> None:
    roster = {r["name"]: r for r in csv.DictReader(open("roster.csv"))}
    papers = [json.loads(l) for l in open(FINAL)]
    by_title = {norm_title(p["title"]): p for p in papers}
    for t in (m for p in papers for m in p.get("merged_titles", [])):
        by_title.setdefault(norm_title(t), None)
    new: dict[str, dict] = {}
    tagged = 0
    for name in names:
        r = roster[name]
        ids = [r["openalex_author_id"]] + [x for x in re.split(r"[;|, ]+", r["openalex_alternates"]) if x]
        for aid in ids:
            for w in author_works(aid):
                rec = to_record(w)
                if not rec["title"] or rec["type"] in EXCLUDED_TYPES or EXCLUDED_TITLE.match(rec["title"]):
                    continue
                key = norm_title(rec["title"])
                if key in by_title:
                    existing = by_title[key]
                    if existing is not None and name not in existing["brown_faculty"]:
                        existing["brown_faculty"].append(name)
                        tagged += 1
                    continue
                target = new.setdefault(key, rec)
                if name not in target["brown_faculty"]:
                    target["brown_faculty"].append(name)
    records = {k: v for k, v in new.items()}
    enrich_from_s2(records)
    log: list = []
    out = []
    for i, p in enumerate(records.values()):
        backfill(p, log) if not p["abstract"] else None
        check_authors(p, log)
        if p["brown_faculty"]:
            p["pid"] = FIRST_NEW_PID + i
            out.append(p)
    with open(FINAL, "w") as fh:
        for p in papers:
            fh.write(json.dumps(p) + "\n")
    with open(NEW, "w") as fh:
        for p in out:
            fh.write(json.dumps(p) + "\n")
    print(f"tagged {tagged} existing papers; {len(out)} new papers -> {NEW}; "
          f"{sum(1 for p in out if p['abstract'])} with abstracts")


if __name__ == "__main__":
    main(sys.argv[1:])
