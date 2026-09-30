# Brown AI Research Map: methodology

**Question.** Who works on what in AI and machine learning at Brown, and how are they connected?
**Scope.** Current Brown faculty whose research is mainly AI/ML, and everything they published from 1 January 2024 to 29 September 2026.
**Principle.** Every fact on the map points to a public source. Where a step needs judgement, it says so, says who or what made the judgement, and says how the judgement was checked.

## Who decides what

| Kind of step | Decided by | Can be re-run exactly? |
|---|---|---|
| **Computed** | A script applying a fixed rule to source data | Yes |
| **Judged (LLM)** | A language model reading text, with a written instruction and a fixed list of choices; checked by sampling | Mostly: the same inputs give similar but not identical outputs |
| **Human** | Morgan (the compiler) | Recorded as a decision, with its reason |

## Pipeline

| # | Step | Source | Rule | Decided by | Checked by | Output |
|---|---|---|---|---|---|---|
| 1 | **Faculty list** | Faculty pages of CS, CoPsy, Applied Math, Engineering, Biostatistics, DSI, CCMB; csrankings | Current Brown faculty whose research is mainly AI/ML; occasional ML users excluded | LLM proposed; **human** confirmed each inclusion/exclusion | Second independent crawl (roster-check.md) found no missing core AI faculty | `roster.csv` (35 people; 1 marked affiliate) |
| 2 | **Paper collection** | OpenAlex author works (all of a person's author IDs) | Works dated 2024-01-01 or later; peer reviews, errata, editorials, front matter removed | **Computed** | Compared with each person's Google Scholar list: 75–80% recall before, missing papers then added | `collect.py` → `papers.jsonl` |
| 3 | **Completeness** | Google Scholar profiles | Scholar-listed 2024+ papers missing from OpenAlex were looked up by title on Semantic Scholar; pre-2024 papers mis-dated by Scholar rejected | LLM compared lists; **computed** lookup, title-match check and year filter | Title must match; year from Semantic Scholar | `supplement.tsv` (≈165 papers) |
| 4 | **Name disambiguation** | OpenAlex / Semantic Scholar author lists | Two faculty with common names (Chen Sun, Yu Cheng) were collected by name + Brown affiliation, not author ID; a faculty tag is kept only if that surname appears in the author list | **Computed** | Audit: 0 of 50 sampled papers had a wrong faculty member | `clean.py` |
| 5 | **Citations** | OpenAlex and Semantic Scholar | Higher of the two counts (OpenAlex undercounts CS papers by splitting preprint/conference versions); citations per month = citations ÷ months since publication | **Computed** | Spot-checks, e.g. one paper 12 (OpenAlex) vs 113 (Semantic Scholar) | fields `cited_by`, `cites_per_month` |
| 6 | **Year rule** | Record dates | A paper counts if its version of record is dated 2024 or later, even if first posted earlier | **Human** decision | n/a | — |
| 7 | **Duplicates** | Titles, authors, abstracts | Near-identical titles merged automatically; other candidate pairs (same faculty, shared title words) judged "same work?" | **Computed** candidates; **LLM** judged 800 pairs; one merge added by hand from the audit | Audit: duplicates fell from 14% to ≈2% | `labels/dups_*.jsonl`, `finalize.py` |
| 8 | **Areas and sub-directions** | Faculty research summaries (from abstracts), then all papers | 9 areas proposed from summaries; each paper then assigned one sub-direction from a fixed list; sub-directions added where ≥3 papers fitted nothing | **LLM** judged, from each abstract (title only for ≈13%, marked) | (a) audit: ≈6% of labels wrong or debatable; (b) independent text test, step 10 | `label_vocab.md`, `labels/` |
| 9 | **Is it AI/ML?** | Abstracts | Papers without substantial AI/ML content (pure numerics, clinical studies) excluded from the map | **LLM** judged | Audit: 2 of 50 flags wrong, both corrected | field `is_ai` |
| 10 | **Area test and content map** | Titles + abstracts | Papers embedded with SPECTER (a model trained on scientific papers); 2D layout by UMAP; for each paper, share of its 10 nearest papers with the same area, compared with chance | **Computed**, fixed seed | All 9 areas cluster 5–14× above chance | `embed.py`, `area_coherence.csv` |
| 11 | **Faculty connections** | Author lists | A line joins two faculty for each paper they co-authored | **Computed** | Each line lists its papers | `build_map_data.py` |
| 12 | **Students and co-advising** | Lab web pages; student homepages | Students listed on a lab page, re-checked on the date shown for graduation or moves; co-advising only where a page lists both advisors | Agent read pages; **no inference from co-authorship** on the public map | Re-checked 30 Sep 2026 against the lab page plus an independent source (Brown CS/CLPS directories, own site): 76 confirmed current, 14 graduated or left (removed), 45 not re-confirmed (shown as "listed on lab page"). Co-advising lines use confirmed students only | `people.csv` (status, evidence_url, second_url, checked) |
| 13 | **Collaborators outside Brown** | Author lists and OpenAlex affiliations | Co-authors not known to be at Brown (not Brown-affiliated on the paper, not on the faculty or student lists), counted by paper; institutions shown only where affiliation data exists; companies are institutions OpenAlex types as "company" | **Computed** | Coverage reported: affiliations exist for ≈56% of papers | `collaborators.py` |

## Accuracy audit (step 7–9 checks)

50 papers drawn at random (seed 20260930) plus 3 flagged records were checked against arXiv, publisher, PubMed and OpenReview pages by an independent reviewer:

| Check | Result |
|---|---|
| Paper exists | 50/50 (1 not findable, removed) |
| Listed Brown faculty is a real author | 50/50 |
| Duplicate of another record | 7/50 before second pass; estimated ≈2% after |
| AI/ML flag wrong | 2/50 (fixed) |
| Area label wrong / debatable | 3/50 wrong, 5/50 debatable |

Full report: `audit_report.md`. All changes: `clean_log.csv`, `finalize_log.csv`.

## Known limits

- **Missing papers.** Workshop papers and very new preprints are the most likely to be missing. The five faculty added in September 2026 have not yet had the Google Scholar completeness check.
- **Citations favour older papers.** 2026 papers have had little time to be cited; citations per month partly corrects for this.
- **Areas are one reasonable division, not the only one.** They are tested (step 10) but were proposed by a model from faculty summaries, which partly mirrors who works together.
- **Affiliations are incomplete.** Preprints often list none, so "not known to be at Brown" is not the same as "external", and institution lists undercount.
- **Lab pages go stale.** Student status is as checked on the date shown. Several lab pages still list people who have graduated or left; 45 people could not be re-confirmed because the web-search budget ran out (29 of them in one group whose page is undated).
- **Five faculty added late.** Rubenstein, Darbon, Çetintemel, Garwood and Han were added on 30 Sep 2026 via `add_faculty.py` / `integrate_new.py`. Only 24 of their 73 new papers are AI/ML (most of their recent work is chemistry, applied mathematics or biostatistics), so they appear with small footprints; Garwood has no AI/ML paper in the window.
- **No comparison with the wider field yet.** A like-for-like comparison would put Brown's papers and a sample of global papers through the same classifier (e.g. OpenAlex topics or shared embedding clusters). Keyword counts were tried and rejected as too subjective.

## Reproduce

```
python3 collect.py            # OpenAlex + supplements + Semantic Scholar citations
python3 clean.py              # backfill, author check, near-identical merges
# labels/: LLM labelling per label_vocab.md, then:
python3 merge_labels.py
# labels/dups_*.jsonl: LLM duplicate judgements, then:
python3 finalize.py
python3 add_faculty.py "Name" …   # optional: incremental additions, then label + dedupe papers_new
python3 integrate_new.py
python3 embed.py              # content map + area test
python3 collaborators.py
python3 build_map_data.py     # writes map/index.html with data embedded
```

Corrections: open an issue or contact the compiler. Every correction is logged with its source.
