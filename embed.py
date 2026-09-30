"""Content map: embed each AI paper's title + abstract, project to 2D, and test the areas.

Model: SPECTER (allenai), trained so papers that cite each other sit close together.
Layout: UMAP (cosine), fixed seed. Area test: for each paper, the share of its 10 nearest
neighbours (in full embedding space, not the 2D picture) that carry the same area label,
compared with the share expected by chance.
Writes map/embedding.json (pid -> x, y) and area_coherence.csv. Run: python3 embed.py
"""
import csv
import json

import numpy as np
import umap
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors

MODEL = "sentence-transformers/allenai-specter"
NEIGHBOURS = 10
SEED = 7


def load() -> list[dict]:
    papers = [json.loads(l) for l in open("papers_final.jsonl")]
    return [p for p in papers if p["is_ai"] and p["attribution_ok"]]


def texts(papers: list[dict], sep: str) -> list[str]:
    return [f"{p['title']}{sep}{p['abstract'] or ''}" for p in papers]


def coherence(vectors: np.ndarray, areas: list[str]) -> list[dict]:
    nn = NearestNeighbors(n_neighbors=NEIGHBOURS + 1, metric="cosine").fit(vectors)
    _, idx = nn.kneighbors(vectors)
    areas_arr = np.array(areas)
    same = (areas_arr[idx[:, 1:]] == areas_arr[:, None]).mean(axis=1)
    rows = []
    for a in sorted(set(areas)):
        mask = areas_arr == a
        chance = (mask.sum() - 1) / (len(areas) - 1)
        rows.append({"area": a, "papers": int(mask.sum()),
                     "neighbours_same_area": round(float(same[mask].mean()), 3),
                     "chance": round(float(chance), 3)})
    return rows


def main() -> None:
    papers = load()
    model = SentenceTransformer(MODEL)
    vec = model.encode(texts(papers, model.tokenizer.sep_token), batch_size=32,
                       show_progress_bar=True, normalize_embeddings=True)
    xy = umap.UMAP(n_neighbors=15, min_dist=0.08, metric="cosine", random_state=SEED).fit_transform(vec)
    xy = (xy - xy.min(axis=0)) / (xy.max(axis=0) - xy.min(axis=0))
    with open("map/embedding.json", "w") as fh:
        json.dump({str(p["pid"]): [round(float(x), 4), round(float(y), 4)] for p, (x, y) in zip(papers, xy)}, fh)
    rows = coherence(vec, [p["area"] for p in papers])
    with open("area_coherence.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)


if __name__ == "__main__":
    main()
