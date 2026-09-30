# Audit report: papers_labeled.jsonl (2026-09-30)

Sample: 53 records (50 random = 40 abstract-labelled + 10 title-only; 3 flagged). Each record was checked against arXiv, OpenAlex, PubMed, OpenReview, publisher pages and patents. Per-pid results are in `audit_results.jsonl`.
Counting rules: `label_ok` counts only "wrong" as an error; "acceptable" is reported separately. `duplicate` is an error if another record in papers_labeled.jsonl is the same work.

## Error rates (50 random papers)

| Check | All 50 | Abstract (40) | Title-only (10) |
|---|---|---|---|
| exists | 0/50 (1 unverified) | 0/40 | 0/10 (1 unverified) |
| faculty_ok | 0/50 | 0/40 | 0/10 |
| year_ok | 1/50 | 1/40 | 0/10 |
| duplicate | **7/50** | 3/40 | **4/10** |
| is_ai_ok | 2/50 | 2/40 | 0/10 |
| label_ok = wrong | 3/50 | 3/40 | 0/10 |
| label_ok = acceptable (a better code exists) | 5/50 | 3/40 | 2/10 |
| any error | 11/50 (22%) | 7/40 (18%) | 4/10 (40%) |

Main finding: **duplicates are the dominant error** (14%, and 40% of title-only records). Title-only records mostly come from supplement/Scholar sources, and many are preprint, workshop or talk twins of papers already in the set. Attribution and existence are clean. Labels are strong: 42/50 correct, 5 acceptable, 3 wrong. All 3 wrong labels are "not AI but coded as AI" boundary cases.

## Flagged papers (attribution_ok=false)

| pid | Verdict |
|---|---|
| 41 (Pavlick, AI content in pre-clerkship med ed) | **Flag is wrong: keep.** OpenAlex lists Pavlick as Brown Dept. of Computer Science, with Brown co-authors. Label 9x is fine. |
| 811 (Serre, perilesional neuromodulation for SCI, Nat BME 2026) | **Flag is wrong: keep.** Serre is affiliated with Brown CLPS/Carney (PubMed 41813803), and a Serre-lab member (Govindarajan) is a co-author. The abstract says stimulation parameters were found "by leveraging modern deep learning methods", so is_ai should be true (borderline) and the code 9f (alt. 8e), not 0x. |
| 909 (Crawford, "Unbiased sorting and sequencing … randomized gating") | **Correct author, but exclude.** The flag is wrong: it is the real Lorin Crawford. But this is a Microsoft patent application (US20230160824A1, published 2023-05-25), not a paper, and it is pre-2024. It is the patent twin of a 2022 Protein Science paper. |

All 3 misattribution flags were false positives. The attribution heuristic is too aggressive for off-topic but genuine collaborations.

## Every error found

**Duplicates**
- 591 = 884: 884 is the ICLR'25 workshop title ("Stress-testing offline reward-free RL…") of arXiv 2502.14819.
- 747 = 890: 890 is the NeurIPS'24 SSL workshop version of the same anomaly-detection paper.
- 40 = 913 = 923: 913 and 923 are supplement records (no DOI) of arXiv 2510.06049 / JFM 2026.
- 927 = 88 = 926: 927 is the SSRN preprint and 926 the arXiv 2405.12380 v1 title of the CMAME 2025 paper.
- 929 = 265: 929 is the OSF preprint of the FAccT'26 paper.
- 849 = 339: 849 is the ICRA'25 workshop summary. Its real year is 2025 (record has null). Its label 5a should match 339's 5b.
- 866 ≈ 437: 866 is an APS DFD 2024 talk abstract on the same downwash study as the RSS'25 paper (overlaps 357 too).

**Year**
- 334 (Spiking Neural Operators): CiCP 2026, but arXiv 2205.10130 was posted May 2022. It fails a strict "first posted ≥2024" rule and passes a "published" rule. Decide on one rule.
- (flagged) 909: 2023 patent.

**is_ai / label wrong**
- 362 (DDM time-averaged drift, J Math Psych): a statistical inconsistency proof with no ML. It should be 0x, not 8d (borderline if cognitive-model inference counts as in scope).
- 391 (Multiscale super-resolution without image priors): Fourier/least-squares inversion with no learning. It should be is_ai=false, 0x (was 3f).
- 230 (latent variable proximal point): is_ai=false is right, but sub=7d contradicts it and should be 0x. The labelling pipeline allows is_ai=false with a non-0x code. Check this globally.

**Labels acceptable but a better code exists**
- 786: 2d, better 8f (biological plasticity rules).
- 518: 9e, better 9x (CNN image profiling of motor neurons, not omics).
- 701: 2c, better 2f (counterfactual explanations).
- 823: 5g, better 5h (perception of pointing for object search).
- 849: 5a, better 5b (also a duplicate).

**Unverified / scope / metadata (not counted as errors)**
- 911 (GPU spectral-element phase-field flow boiling, Karniadakis): no trace found on the web, Crossref or the group page. Its only source is supplement.tsv. Treat it as unverified.
- 869 (Raghavan, Efficient Serialization): a 2024 Stanford PhD thesis written before Brown. Arguably not Brown work.
- 866 and 904 are conference talk/meeting abstracts, not papers. Decide whether abstracts are in scope.
- Missing years found: 849→2025, 866→2024, 869→2024, 887→2024 (NeurIPS'24 SSL workshop), 904→2024, 909→2023.
- 252 venue is empty (NeurIPS 2025). 758 venue "HAL" is doubtful (white paper on the author's site). 701 co-author Ritambhara Singh is Brown faculty but is missing from the roster.

## Recommended fixes
1. Run a global dedup pass: fuzzy titles plus author overlap, especially for supplement/no-DOI and workshop records.
2. Enforce is_ai=false ⇒ sub=0x.
3. Clear the 3 attribution flags. Recode 811 to is_ai=true, 9f. Drop 909.
4. Choose a rule for pre-2024 preprints (334) and for non-paper items (theses, patents, talk abstracts).
