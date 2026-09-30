"""Clean papers.jsonl -> papers_clean.jsonl (run after collect.py).

1. Backfill: Semantic Scholar title match for papers missing an abstract, authors or S2 citations.
2. Author check: drop a faculty tag when the paper's author list doesn't contain that surname.
3. Fuzzy dedupe: merge preprint/journal versions whose titles differ slightly.
4. Flag stubs: records with neither authors nor abstract are kept but marked unverified.
Every change is logged to clean_log.csv. Run: python3 clean.py
"""
import csv
import difflib
import json
import os
import re

from collect import S2_CACHE, months_since, norm_title, s2_match

IN, OUT, LOG = "papers.jsonl", "papers_clean.jsonl", "clean_log.csv"
TITLE_SIMILARITY = 0.90      # near-identical titles are the same work
SAME_AUTHOR_SIMILARITY = 0.88  # slightly looser when first author and faculty also match
NAME_SIMILARITY = 0.7         # tolerate misspelled author names ("Balliestro")
MIN_AUTHORS_TO_CHECK = 2      # single-author records are usually truncated lists


def surname(name: str) -> str:
    """Last name, handling "Surname, First" order."""
    name = name or ""
    if "," in name:
        name = name.split(",")[0]
        parts = re.sub(r"[^a-zA-Z\s-]", " ", name).split()
        return parts[-1].lower() if parts else ""
    parts = re.sub(r"[^a-zA-Z\s-]", " ", name).split()
    return parts[-1].lower() if parts else ""


def is_author(faculty: str, authors: list[dict]) -> bool:
    """Loose match: surname inside a (possibly space-less) name, or a close spelling."""
    target = surname(faculty)
    for a in authors:
        squashed = re.sub(r"[^a-z]", "", (a["name"] or "").lower())
        if target in squashed:
            return True
        if difflib.SequenceMatcher(None, target, surname(a["name"])).ratio() >= NAME_SIMILARITY:
            return True
    return False


def needs_backfill(p: dict) -> bool:
    return not p["abstract"] or not p["authors"] or "cited_by_s2" not in p


def backfill(p: dict, log: list) -> None:
    s = s2_match(p["title"])
    if not s:
        return
    if not p["abstract"] and s.get("abstract"):
        p["abstract"], p["abstract_source"] = s["abstract"], "semanticscholar"
        log.append(("abstract_added", p["title"], ""))
    if not p["authors"] and s.get("authors"):
        p["authors"] = [{"name": a.get("name"), "openalex_id": "", "position": "", "index": i,
                         "institutions": [], "brown": False, "industry": False}
                        for i, a in enumerate(s["authors"])]
        log.append(("authors_added", p["title"], str(len(p["authors"]))))
    if "cited_by_s2" not in p and s.get("citationCount") is not None:
        p["cited_by_s2"] = s["citationCount"]
        p["cited_by"] = max(p["cited_by"], p["cited_by_s2"])
        p["cites_per_month"] = round(p["cited_by"] / months_since(p["date"]), 3)


def check_authors(p: dict, log: list) -> None:
    """Keep a faculty tag only if that surname appears among the authors (when authors are known)."""
    if len(p["authors"]) < MIN_AUTHORS_TO_CHECK:
        return
    kept = []
    for f in p["brown_faculty"]:
        if is_author(f, p["authors"]):
            kept.append(f)
        else:
            log.append(("faculty_dropped", p["title"], f))
    p["brown_faculty"] = kept


def same_work(a: dict, b: dict) -> bool:
    ratio = difflib.SequenceMatcher(None, norm_title(a["title"]), norm_title(b["title"])).ratio()
    if ratio >= TITLE_SIMILARITY:
        return True
    first = lambda p: surname(p["authors"][0]["name"]) if p["authors"] else None
    shared_fac = set(a["brown_faculty"]) & set(b["brown_faculty"])
    return bool(ratio >= SAME_AUTHOR_SIMILARITY and first(a) and first(a) == first(b) and shared_fac)


def merge(keep: dict, drop: dict) -> None:
    """Fold drop into keep: richest record wins, citations take the max, faculty tags union."""
    for field in ("abstract", "venue", "doi"):
        if not keep.get(field) and drop.get(field):
            keep[field] = drop[field]
    if len(drop["authors"]) > len(keep["authors"]):
        keep["authors"] = drop["authors"]
    keep["top_venue"] = keep["top_venue"] or drop["top_venue"]
    keep["cited_by"] = max(keep["cited_by"], drop["cited_by"])
    keep["cites_per_month"] = max(keep["cites_per_month"], drop["cites_per_month"])
    keep["brown_faculty"] = sorted(set(keep["brown_faculty"]) | set(drop["brown_faculty"]))
    keep.setdefault("merged_titles", []).append(drop["title"])


def richness(p: dict) -> tuple:
    return (bool(p["abstract"]), p["type"] != "preprint", len(p["authors"]), p["cited_by"])


def dedupe(papers: list[dict], log: list) -> list[dict]:
    papers = sorted(papers, key=richness, reverse=True)
    kept: list[dict] = []
    for p in papers:
        twin = next((k for k in kept if same_work(k, p)), None)
        if twin:
            merge(twin, p)
            log.append(("merged", p["title"], twin["title"]))
        else:
            kept.append(p)
    return kept


def main() -> None:
    os.makedirs(S2_CACHE, exist_ok=True)
    papers = [json.loads(line) for line in open(IN)]
    log: list[tuple] = []
    todo = [p for p in papers if needs_backfill(p)]
    print(f"backfilling {len(todo)} papers via Semantic Scholar…", flush=True)
    for i, p in enumerate(todo, 1):
        backfill(p, log)
        if i % 50 == 0:
            print(f"  {i}/{len(todo)}", flush=True)
    for p in papers:
        check_authors(p, log)
    papers = [p for p in papers if p["brown_faculty"]]
    papers = dedupe(papers, log)
    for p in papers:
        p["unverified"] = not p["authors"] and not p["abstract"]
    with open(OUT, "w") as fh:
        for p in papers:
            fh.write(json.dumps(p) + "\n")
    with open(LOG, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["action", "title", "detail"])
        w.writerows(log)
    kinds = {k: sum(1 for x in log if x[0] == k) for k in {x[0] for x in log}}
    n_abs = sum(1 for p in papers if p["abstract"])
    print(f"{len(papers)} papers after cleaning; {n_abs} with abstracts ({n_abs / len(papers):.0%}); "
          f"{sum(p['unverified'] for p in papers)} unverified stubs; changes: {kinds}")


if __name__ == "__main__":
    main()
