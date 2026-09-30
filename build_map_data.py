"""Build map/map_data.json for the public Brown AI map (neutral facts only).

Includes: AI/ML papers (is_ai, attribution_ok), faculty nodes, co-authorship edges,
co-advising edges from lab-page-confirmed students only, and the area/sub-direction tree.
Excludes: personal rankings, momentum labels, inferred student links, judgements.
Writes map/map_data.json and map/index.html (from map/template.html, data embedded).
Run: python3 build_map_data.py
"""
import csv
import json
import os
import re
from collections import Counter, defaultdict
from itertools import combinations

OUT_DIR = "map"
AREA_NAMES = {
    "1": "Language & multimodal model science",
    "2": "Self-supervised learning, world models & learning theory",
    "3": "Visual computing: video, 3D & generative models",
    "4": "Computational design & fabrication",
    "5": "Robotics, RL, planning & multi-agent systems",
    "6": "Human-centered AI: alignment, accountability & governance",
    "7": "Scientific machine learning",
    "8": "NeuroAI & computational cognition",
    "9": "ML for biology & health",
}


EMBED = json.load(open("map/embedding.json")) if os.path.exists("map/embedding.json") else {}


def coherence_rows() -> list[dict]:
    if not os.path.exists("area_coherence.csv"):
        return []
    return [{k: (float(v) if k != "area" else v) for k, v in r.items()} for r in csv.DictReader(open("area_coherence.csv"))]


def load_papers() -> list[dict]:
    papers = [json.loads(l) for l in open("papers_final.jsonl")]
    return [p for p in papers if p["is_ai"] and p["attribution_ok"]]


def roster() -> dict[str, dict]:
    return {r["name"]: r for r in csv.DictReader(open("roster.csv")) if r["status"].strip() == "current"}


def paper_record(p: dict) -> dict:
    return {
        "id": p["pid"], "t": p["title"], "y": p["year"], "v": p["venue"] or "",
        "f": p["brown_faculty"], "s": p["sub"], "s2": p.get("sub2"),
        "c": p["cited_by"], "cpm": p["cites_per_month"],
        "a": ", ".join(a["name"] for a in p["authors"][:8]) + (" …" if len(p["authors"]) > 8 else ""),
        "ab": p["abstract"] or "", "doi": p["doi"] or "", "tb": p["label_basis"] == "title",
        "xy": EMBED.get(str(p["pid"])),
        "oa": p.get("openalex_id") or "", "why": p.get("label_why", ""),
    }


def faculty_nodes(papers: list[dict], people: dict[str, dict]) -> list[dict]:
    by_fac = defaultdict(list)
    for p in papers:
        for f in p["brown_faculty"]:
            by_fac[f].append(p)
    nodes = []
    for name, info in people.items():
        ps = by_fac.get(name, [])
        areas = Counter(p["area"] for p in ps)
        nodes.append({
            "id": name, "dept": info["dept"], "url": info.get("personal_or_lab_url", ""),
            "affiliate": info.get("affiliation_type") == "affiliate",
            "n": len(ps), "area": areas.most_common(1)[0][0] if areas else None,
            "areas": dict(areas), "cites": sum(p["cited_by"] for p in ps),
        })
    return nodes


def coauthor_edges(papers: list[dict]) -> list[dict]:
    """Computed: one edge per faculty pair, listing the papers they co-authored."""
    pairs = defaultdict(list)
    for p in papers:
        for a, b in combinations(sorted(set(p["brown_faculty"])), 2):
            pairs[(a, b)].append(p["pid"])
    return [{"s": a, "t": b, "papers": len(v), "ids": v} for (a, b), v in pairs.items()]


SHOWN_STATUS = {"current": "confirmed", "unclear": "listed"}


def coadvising_edges(people: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """Students listed on a lab page (never inferred from co-authorship).

    status current  -> "confirmed": lab page + an independent source, checked on the date given
    status unclear  -> "listed": on a lab page, not re-confirmed
    graduated / left / unchecked are not shown. Co-advising edges use confirmed students only.
    """
    pairs, students = defaultdict(list), []
    for r in csv.DictReader(open("people.csv")):
        if r["confidence"] != "confirmed" or r.get("status") not in SHOWN_STATUS:
            continue
        advisors = [a.strip() for a in r["advisors"].split(";") if a.strip() in people]
        if not advisors:
            continue
        level = SHOWN_STATUS[r["status"]]
        src = r["source"].split(" ")[0]
        students.append({"name": r["person"], "role": r["role"], "advisors": advisors, "level": level,
                         "src": src, "ev": r.get("evidence_url", ""), "ev2": r.get("second_url", ""),
                         "checked": r.get("checked", "")})
        if level == "confirmed":
            for a, b in combinations(sorted(advisors), 2):
                pairs[(a, b)].append(r["person"])
    return [{"s": a, "t": b, "students": v} for (a, b), v in pairs.items()], students


def subdirections() -> dict[str, str]:
    codes = {}
    for line in open("label_vocab.md"):
        m = re.match(r"\s+(\d[a-z])\s+(.+)", line)
        if m and m.group(1)[0] != "0":
            codes[m.group(1)] = m.group(2).strip()
    return codes


def main() -> None:
    papers, people = load_papers(), roster()
    co_edges, students = coadvising_edges(people)
    data = {
        "built": "2026-09-30",
        "areas": AREA_NAMES, "subs": subdirections(),
        "faculty": faculty_nodes(papers, people),
        "coauthor": coauthor_edges(papers), "coadvise": co_edges,
        "students": students,
        "coherence": coherence_rows(),
        "collab": json.load(open("collaborators.json")) if os.path.exists("collaborators.json") else {},
        "colors": json.load(open("map/area_colors.json")) if os.path.exists("map/area_colors.json") else {},
        "papers": [paper_record(p) for p in sorted(papers, key=lambda p: -p["cites_per_month"])],
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "map_data.json"), "w") as fh:
        json.dump(data, fh, separators=(",", ":"))
    # Embed the data in the page itself so it works without fetching a second file.
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    page = open(os.path.join(OUT_DIR, "template.html")).read().replace("__MAP_DATA__", blob)
    # artifact.html: body-only page for the Claude artifact viewer (it adds its own document skeleton).
    # index.html: standalone document for GitHub Pages or opening the file directly.
    with open(os.path.join(OUT_DIR, "artifact.html"), "w") as fh:
        fh.write(page)
    head = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')
    title_end = page.index("</title>") + len("</title>")
    standalone = head + page[:title_end] + "\n" + page[title_end:].replace("<style>", "<style>\nbody { margin: 0; }", 1)
    standalone = standalone.replace("<div class=\"wrap\">", "</head>\n<body>\n<div class=\"wrap\">", 1) + "\n</body>\n</html>\n"
    with open(os.path.join(OUT_DIR, "index.html"), "w") as fh:
        fh.write(standalone)
    size = os.path.getsize(os.path.join(OUT_DIR, "map_data.json")) / 1e6
    print(f"{len(data['papers'])} papers, {len(data['faculty'])} faculty, "
          f"{len(data['coauthor'])} co-author pairs, {len(co_edges)} co-advising pairs, "
          f"{sum(s['level'] == 'confirmed' for s in students)} confirmed + "
          f"{sum(s['level'] == 'listed' for s in students)} listed students; {size:.1f} MB")


if __name__ == "__main__":
    main()
