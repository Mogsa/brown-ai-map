"""Phase 1: collect 2024+ papers for every current roster member into papers.jsonl.

Source: OpenAlex (all of a person's IDs, main + alternates). Missing abstracts are
backfilled from Semantic Scholar by DOI. Run: python3 collect.py  (or --2023 for the impact-anchor year)
"""
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date

ROSTER = "roster.csv"
# Papers found on Google Scholar but missing from OpenAlex (faculty<TAB>title).
SUPPLEMENT = "supplement.tsv"
S2_CACHE = "cache/s2_match"
# Main run: 2024+ papers for the taxonomy. "--2023": 2023 papers, used only as an
# impact anchor (they have had ~3 years to collect citations), never read into the taxonomy.
PERIODS = {
    "main": {"out": "papers.jsonl", "cache": "cache/openalex",
             "dates": "from_publication_date:2024-01-01"},
    "2023": {"out": "papers_2023.jsonl", "cache": "cache/openalex_2023",
             "dates": "from_publication_date:2023-01-01,to_publication_date:2023-12-31"},
}
PERIOD = PERIODS["2023" if "--2023" in sys.argv else "main"]
OUT, CACHE, DATES = PERIOD["out"], PERIOD["cache"], PERIOD["dates"]
TODAY = date(2026, 9, 29)
BROWN = "I27804330"
# OpenAlex merges these people with namesakes, so their author IDs are unusable.
# Instead, find works where an author with exactly this name is affiliated with Brown.
CONFLATED = {"Yu Cheng", "Chen Sun"}
# Records that are not research outputs (eLife reviewer assessments, corrections, front matter).
EXCLUDED_TYPES = {"peer-review", "erratum", "paratext", "editorial"}
EXCLUDED_TITLE = re.compile(r"^(elife assessment|author response|reviewer #|decision letter)", re.I)
# Code/data releases: kept as a "released code" signal, but not counted as papers.
RELEASE_TYPES = {"software", "dataset"}
# Flagged by the Phase 3 readers as another person's work (faculty, title prefix).
MISATTRIBUTED = [
    ("George Karniadakis", "agents' last exam"),
    ("George Karniadakis", "a mathematical model for predicting complex dynamic systems"),
    ("Thomas Serre", "a lightweight dual-stage framework for personalized speech"),
    ("Thomas Serre", "contrastive knowledge distillation for embedding refinement"),
    ("Chen Sun", "loger"),  # author is Cheng Sun
]
TOP_VENUES = re.compile(
    r"neurips|neural information processing|icml|international conference on machine learning|"
    r"iclr|learning representations|acl|association for computational linguistics|emnlp|naacl|"
    r"cvpr|computer vision and pattern|iccv|eccv|corl|robot learning|rss|robotics: science|"
    r"icra|iros|aaai|ijcai|chi conference|facct|siggraph|transactions on graphics|nature|science\b|"
    r"pnas|proceedings of the national academy",
    re.I,
)


def get_json(url, headers=None, data=None):
    key = os.environ.get("OPENALEX_API_KEY")
    if key and "api.openalex.org" in url:
        url += ("&" if "?" in url else "?") + f"api_key={key}"
    req = urllib.request.Request(url, headers=headers or {}, data=data)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise
        except (TimeoutError, urllib.error.URLError, ConnectionError) as e:
            print(f"  retry {attempt + 1}: {e}", flush=True)
        time.sleep(2 ** attempt * 3)
    raise RuntimeError(f"gave up on {url}")


def rebuild_abstract(inv):
    if not inv:
        return ""
    words = sorted((pos, w) for w, ps in inv.items() for pos in ps)
    return " ".join(w for _, w in words)


def author_works(author_id):
    cache = os.path.join(CACHE, f"{author_id}.json")
    if os.path.exists(cache):
        return json.load(open(cache))
    cursor, works = "*", []
    while cursor:
        q = urllib.parse.urlencode({
            "filter": f"authorships.author.id:{author_id},{DATES}",
            "per-page": 200, "cursor": cursor,
        })
        page = get_json(f"https://api.openalex.org/works?{q}")
        works += page["results"]
        cursor = page["meta"].get("next_cursor")
        if not page["results"]:
            break
    json.dump(works, open(cache, "w"))
    return works


def brown_name_works(name):
    q = urllib.parse.urlencode({
        "filter": f'raw_author_name.search:"{name}",institutions.id:{BROWN},{DATES}',
        "per-page": 200,
    })
    works = get_json(f"https://api.openalex.org/works?{q}")["results"]

    def is_brown_self(a):
        same = (a.get("raw_author_name") or "").lower().replace("-", " ") == name.lower()
        return same and any(BROWN in (i.get("id") or "") for i in a["institutions"])

    return [w for w in works if any(is_brown_self(a) for a in w["authorships"])]


def months_since(pub_date):
    d = date.fromisoformat(pub_date)
    return max(1, (TODAY.year - d.year) * 12 + TODAY.month - d.month)


def to_record(w):
    authors = []
    for i, a in enumerate(w.get("authorships", [])):
        authors.append({
            "name": a["author"].get("display_name"),
            "openalex_id": (a["author"].get("id") or "").rsplit("/", 1)[-1],
            "position": a.get("author_position"),
            "index": i,
            "institutions": [inst.get("display_name") for inst in a.get("institutions", [])],
            "brown": any(BROWN in (inst.get("id") or "") for inst in a.get("institutions", [])),
            "industry": any(inst.get("type") == "company" for inst in a.get("institutions", [])),
        })
    src = ((w.get("primary_location") or {}).get("source") or {})
    venue = src.get("display_name") or ""
    abstract = rebuild_abstract(w.get("abstract_inverted_index"))
    cites = w.get("cited_by_count", 0)
    pub = w.get("publication_date") or f"{w.get('publication_year')}-01-01"
    return {
        "openalex_id": w["id"].rsplit("/", 1)[-1],
        "doi": (w.get("doi") or "").replace("https://doi.org/", "").lower(),
        "title": w.get("title") or "",
        "year": w.get("publication_year"),
        "date": pub,
        "type": w.get("type"),
        "venue": venue,
        "top_venue": bool(TOP_VENUES.search(venue)),
        "abstract": abstract,
        "abstract_source": "openalex" if abstract else "",
        "authors": authors,
        "cited_by": cites,
        "cites_per_month": round(cites / months_since(pub), 3),
        "industry_coauthor": any(a["industry"] for a in authors),
        "code_mention": bool(re.search(r"github\.com|code (is )?(publicly )?available", abstract, re.I)),
        "is_release": w.get("type") in RELEASE_TYPES or (w.get("title") or "").lower().startswith("source code for"),
        "brown_faculty": [],
    }


def s2_match(title):
    """Semantic Scholar title match, cached on disk; {} if no confident match."""
    path = os.path.join(S2_CACHE, hashlib.sha1(title.lower().encode()).hexdigest() + ".json")
    if os.path.exists(path):
        return json.load(open(path))
    q = urllib.parse.urlencode({
        "query": title,
        "fields": "title,year,venue,citationCount,publicationDate,externalIds,abstract,authors",
    })
    try:
        p = get_json(f"https://api.semanticscholar.org/graph/v1/paper/search/match?{q}")["data"][0]
    except (urllib.error.HTTPError, KeyError, IndexError):
        p = {}
    except RuntimeError:  # rate-limited after all retries: skip without caching, so a rerun retries it
        time.sleep(30)
        return {}
    time.sleep(4)
    # /search/match returns the closest title even when it's a different paper.
    if p and norm_title(p.get("title"))[:30] != norm_title(title)[:30]:
        p = {}
    json.dump(p, open(path, "w"))
    return p


def supplement_record(faculty, title):
    """Resolve a title via Semantic Scholar; fall back to a title-only record."""
    p = s2_match(title)
    pub = p.get("publicationDate") or f"{p.get('year') or TODAY.year}-01-01"
    cites = p.get("citationCount") or 0
    venue = p.get("venue") or ""
    abstract = p.get("abstract") or ""
    return {
        "openalex_id": "", "doi": ((p.get("externalIds") or {}).get("DOI") or "").lower(),
        "title": p.get("title") or title, "year": p.get("year"), "date": pub, "type": "supplement",
        "venue": venue, "top_venue": bool(TOP_VENUES.search(venue)),
        "abstract": abstract, "abstract_source": "semanticscholar" if abstract else "",
        "authors": [{"name": a.get("name"), "openalex_id": "", "position": "", "index": i,
                     "institutions": [], "brown": False, "industry": False}
                    for i, a in enumerate(p.get("authors") or [])],
        "cited_by": cites, "cites_per_month": round(cites / months_since(pub), 3),
        "industry_coauthor": False, "code_mention": False, "is_release": False,
        "brown_faculty": [faculty],
    }


def add_supplements(records):
    if not os.path.exists(SUPPLEMENT):
        return
    for row in csv.DictReader(open(SUPPLEMENT), delimiter="\t"):
        if any(f == row["faculty"] and row["title"].lower().startswith(t) for f, t in MISATTRIBUTED):
            continue
        key = norm_title(row["title"])
        if key in records:
            if row["faculty"] not in records[key]["brown_faculty"]:
                records[key]["brown_faculty"].append(row["faculty"])
            continue
        rec = supplement_record(row["faculty"], row["title"])
        # Scholar sometimes re-dates older papers; trust Semantic Scholar's year.
        if rec["year"] and rec["year"] < 2024:
            print(f"  supplement skipped (pre-2024): {row['title'][:60]}", flush=True)
            continue
        records[key] = rec
        print(f"  supplement: {row['faculty']}: {row['title'][:60]}", flush=True)


def norm_title(t):
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())[:120]


def s2_id(doi):
    """Semantic Scholar resolves arXiv papers by arXiv ID more reliably than by their DataCite DOI."""
    m = re.match(r"10\.48550/arxiv\.(.+)", doi)
    return f"ARXIV:{m.group(1)}" if m else f"DOI:{doi}"


def enrich_from_s2(records):
    """Backfill missing abstracts and take Semantic Scholar citation counts.

    OpenAlex splits citations between preprint and conference versions and misses
    arXiv citations, so it undercounts CS papers roughly 10x relative to journals.
    Semantic Scholar merges versions; we keep both counts and rank on the larger.
    """
    with_doi = [r for r in records.values() if r["doi"]]
    for i in range(0, len(with_doi), 400):
        chunk = with_doi[i:i + 400]
        body = json.dumps({"ids": [s2_id(r["doi"]) for r in chunk]}).encode()
        res = get_json(
            "https://api.semanticscholar.org/graph/v1/paper/batch?fields=abstract,citationCount",
            headers={"Content-Type": "application/json"}, data=body,
        )
        for r, s in zip(chunk, res):
            if not s:
                continue
            if not r["abstract"] and s.get("abstract"):
                r["abstract"], r["abstract_source"] = s["abstract"], "semanticscholar"
            r["cited_by_s2"] = s.get("citationCount") or 0
        time.sleep(3)
    for r in records.values():
        r["cited_by_openalex"] = r["cited_by"]
        r["cited_by"] = max(r["cited_by"], r.get("cited_by_s2", 0))
        r["cites_per_month"] = round(r["cited_by"] / months_since(r["date"]), 3)


def main():
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(S2_CACHE, exist_ok=True)
    roster = [r for r in csv.DictReader(open(ROSTER)) if r["status"].strip() == "current"]
    records = {}  # norm_title -> record (dedupe across split profiles / DOIs)
    for person in roster:
        ids = [person["openalex_author_id"]] + [
            x.strip() for x in re.split(r"[;|, ]+", person["openalex_alternates"]) if x.strip()
        ]
        ids = [i for i in ids if i.startswith("A")]
        if person["name"] in CONFLATED:
            works = brown_name_works(person["name"])
        else:
            works = [w for aid in ids for w in author_works(aid)]
        kept = 0
        for w in works:
            rec = to_record(w)
            if not rec["title"] or rec["type"] in EXCLUDED_TYPES or EXCLUDED_TITLE.match(rec["title"]):
                continue
            if any(f == person["name"] and rec["title"].lower().startswith(t) for f, t in MISATTRIBUTED):
                continue
            rec = records.setdefault(norm_title(rec["title"]), rec)
            if person["name"] not in rec["brown_faculty"]:
                rec["brown_faculty"].append(person["name"])
                kept += 1
        print(f"{person['name']:28s} {kept:4d} papers from {len(ids)} id(s)", flush=True)
    if PERIOD is PERIODS["main"]:
        add_supplements(records)
    enrich_from_s2(records)
    with open(OUT, "w") as f:
        for r in records.values():
            f.write(json.dumps(r) + "\n")
    n = len(records)
    with_abs = sum(1 for r in records.values() if r["abstract"])
    print(f"\n{n} unique papers, {with_abs} with abstracts ({with_abs / n:.0%})")


if __name__ == "__main__":
    main()
