# Brown AI Research Map

Who works on what in AI and machine learning at Brown University, built from every paper Brown AI faculty published from January 2024 to September 2026.

**Draft, compiled from public data by a Brown CS ScM student.** There will be errors and gaps; corrections are welcome (open an issue).

## View the map

**Live: https://mogsa.github.io/brown-ai-map/** (or open `map/index.html` locally; all data is embedded). It has four views:

- **Map of the research:** every paper placed by what its abstract says (SPECTER embeddings + UMAP), coloured by area; faculty shown at the centre of their papers. Zoom, search to highlight a topic, filter by year.
- **Who publishes together:** faculty joined by co-authored papers (computed from author lists) and by co-advised students (confirmed on lab pages).
- **Nine research areas:** papers per sub-direction.
- **Search the papers:** filter by area, faculty and year; every paper links to its source record.

## What's in the numbers

| | |
|---|---|
| Faculty | 35 (30 core + 5 added Sept 2026), from department faculty pages |
| AI/ML papers | 803 (2024 onwards, by publication date) |
| Faculty pairs who co-author | 24 |
| Students/postdocs confirmed current | 76 (plus 45 listed on lab pages but not re-confirmed) |
| Accuracy (50-paper hand audit) | all authorships correct; about 6% area labels wrong or debatable; duplicates reduced to about 2% |

## Method

See **[METHODOLOGY.md](METHODOLOGY.md)**. For every step it gives the source, the rule, whether it was **computed** by a script, **judged** by a language model, or decided by a **person**, how it was checked, and its limits. In short:

- **Computed** (re-runnable exactly): paper collection, citations, authorship checks, co-author links, map positions, the area coherence test, collaborator counts.
- **Judged by a language model**, then audited: which area each paper belongs to, which records are duplicate versions, and whether a paper is substantially AI/ML.
- **Never inferred**: student–advisor links come only from lab pages, re-checked against a second source on 30 Sep 2026.

## Files

| File | What it is |
|---|---|
| `papers_final.jsonl` | Every collected paper (AI and non-AI, with `is_ai`), authors, citations, area label and how it was assigned |
| `roster.csv` | Faculty, departments, profile links and OpenAlex IDs |
| `people.csv` | Students and postdocs shown on the map, with source page, second source and date checked |
| `collaborators.json` | Per faculty: frequent co-authors not known to be at Brown, institutions, companies |
| `label_vocab.md` | The 9 areas and their sub-directions |
| `labels/` | Every per-paper area judgement and duplicate judgement, with a short reason |
| `area_coherence.csv` | Independent test of the areas against the text embeddings |
| `audit_report.md`, `audit_results.jsonl` | The 50-paper hand audit |
| `clean_log.csv`, `finalize_log.csv` | Every automated change (merges, removals, fixes) |
| `supplement.tsv` | Papers added from Google Scholar that OpenAlex missed |
| `map/` | The map page (`template.html` + embedded data → `index.html`) |

## Rebuild

```
pip install -r requirements.txt
python3 collect.py && python3 clean.py        # needs network; OpenAlex + Semantic Scholar
# per-paper labels and duplicate judgements live in labels/ (language-model step)
python3 merge_labels.py && python3 finalize.py && python3 integrate_new.py
python3 embed.py && python3 collaborators.py && python3 build_map_data.py
```

Optional: set `OPENALEX_API_KEY` for a higher OpenAlex rate limit.

## Known limits

Workshop papers and very new preprints are most likely to be missing; the five faculty added in September 2026 have not had the Google Scholar completeness check; recent papers have had little time to be cited; affiliations exist for only about 57% of papers; lab pages go stale. The nine areas are one tested, reasonable division of the field, not the only one. There is no comparison with the wider field yet.
