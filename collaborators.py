"""Collaborators per faculty, counted directly from paper author records (no LLM).

Co-authors: every author on the faculty member's papers who is not known to be at Brown.
"Known to be at Brown" = tagged with a Brown affiliation on that paper, or listed in
roster.csv (faculty) or people.csv (students/postdocs, incl. alumni). Everyone else is
reported as "not known to be at Brown", since preprints often carry no affiliations.
Institutions: from OpenAlex affiliations where present (coverage is reported); an
institution counts as a company when OpenAlex types it "company".
Writes collaborators.json. Run: python3 collaborators.py
"""
import csv
import glob
import json
import re
from collections import Counter, defaultdict

TOP = 8
NOT_A_PERSON = re.compile(r"society|conference|proceedings|consortium|committee|workshop|group\b|team\b|\d{4}", re.I)


def key(name: str) -> str:
    """First initial + surname, tolerant of 'Surname, First' and punctuation."""
    name = name or ""
    if "," in name:
        last, first = name.split(",", 1)
    else:
        parts = name.split()
        last, first = (parts[-1], parts[0]) if parts else ("", "")
    clean = lambda s: re.sub(r"[^a-z]", "", s.lower())
    return f"{clean(first)[:1]}{clean(last)}"


def brown_people() -> set[str]:
    names = {r["name"] for r in csv.DictReader(open("roster.csv"))}
    names |= {r["person"] for r in csv.DictReader(open("people.csv"))}
    return {key(n) for n in names}


def institution_types() -> dict[str, str]:
    types = {}
    for f in glob.glob("cache/openalex*/*.json"):
        for w in json.load(open(f)):
            for a in w.get("authorships", []):
                for i in a.get("institutions", []):
                    if i.get("display_name"):
                        types[i["display_name"]] = i.get("type") or ""
    return types


def load() -> list[dict]:
    papers = []
    for path in ("papers_final.jsonl", "papers_new.jsonl"):
        try:
            papers += [json.loads(l) for l in open(path)]
        except FileNotFoundError:
            pass
    return [p for p in papers if p.get("is_ai", True) and p.get("attribution_ok", True)]


def main() -> None:
    papers, brown, types = load(), brown_people(), institution_types()
    people, insts, companies = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    total, with_aff = Counter(), Counter()
    spellings = defaultdict(Counter)  # key -> spelling counts, to show the most common form
    for p in papers:
        has_aff = any(a["institutions"] for a in p["authors"])
        paper_insts = set()
        for a in p["authors"]:
            if a["brown"] or key(a["name"]) in brown or NOT_A_PERSON.search(a["name"] or ""):
                continue
            spellings[key(a["name"])][a["name"]] += 1
            for f in p["brown_faculty"]:
                people[f][key(a["name"])] += 1
            paper_insts |= {i for i in a["institutions"] if i and "Brown University" not in i}
        for f in p["brown_faculty"]:
            total[f] += 1
            with_aff[f] += has_aff
            for i in paper_insts:
                insts[f][i] += 1
                if types.get(i) == "company":
                    companies[f][i] += 1
    out = {
        f: {
            "papers": total[f],
            "papers_with_affiliations": with_aff[f],
            "top_coauthors_not_known_at_brown": [
                (spellings[k].most_common(1)[0][0], n) for k, n in people[f].most_common(TOP)],
            "top_institutions": insts[f].most_common(TOP),
            "companies": companies[f].most_common(TOP),
        }
        for f in sorted(total)
    }
    json.dump(out, open("collaborators.json", "w"), indent=1, ensure_ascii=False)
    print(f"{len(out)} faculty; affiliations on {sum(with_aff.values())}/{sum(total.values())} faculty-paper links")


if __name__ == "__main__":
    main()
