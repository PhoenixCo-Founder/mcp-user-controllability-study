# MCP User-Controllability Study (2026)

Reproducibility package for the study published at
https://blog.agentadmit.com/mcp-user-controllability-study-2026/

**Question.** Once a person hands an AI agent a credential for an MCP server, can that person still see, scope, and revoke what the agent holds?

**What was measured.** The READMEs of 1,634 MCP server repositories on the curated [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) list (1,347 fetched July 13, 2026, plus 287 added to the list by September 10, 2026), scored on six dimensions: credential delivery, consent surface, revocability, credential lifetime, scoping, and attribution.

This is static analysis of documentation. It measures what a server documents, not how it behaves at runtime. No third-party server was probed.

## Results

Every figure is a statement about documentation ("the README documents X"). Denominator for credential figures: the 857 servers that document a real credential channel.

| Statement | Full frame | Repeat sample, pass A / pass B |
|---|---|---|
| Credential arrives through an environment variable or config file | 724/857 = 84.5% | 81.4% / 81.1% |
| No approval step documented (of all 1,634) | 1,309/1,634 = 80.1% | 82.0% / 79.5% |
| Documents a way to revoke one grant on its own | 71/857 = 8.3% | 8.8% / 8.5% |
| Documents a credential that expires (72) or a user-chosen lifetime (3) | 75/857 = 8.8% | 16.7% / 17.0% |
| Documents any narrowing of what the agent gets | 290/857 = 33.8% | 33.3% / 31.1% |
| Documents per-user or per-agent attribution | 199/857 = 23.2% | 28.4% / 27.4% |
| Automated delivery and none of the five user controls documented | 436/857 = 50.9% | 52.0% / 48.1% |

The repeat sample is a seeded random 200 repositories (`repeat-sample200-seed20260930.txt`) classified twice by the same instrument. Pass A and pass B show how much a figure moves between two runs. The sample is small, so its level can differ from the full frame (the lifetime row is the clearest case).

Full label distributions: `aggregates-2026-09-30-v2.csv` and `results/label_distributions.txt`.

## Method

- **Input.** Each repository's README, up to its first 30,000 characters, plus top-level file names. 129 of the 1,634 stored READMEs (7.9%) reach that cap, so their tail was not read.
- **Rubric.** `RUBRIC.md`, the exact prompt text, with a definition for every label, a required verbatim evidence quote, and an `insufficient_data` option.
- **Classifier.** A language model (`claude-sonnet-5-5`, one pinned version for every row), one pass, five repositories per call at most (`classify_full_readme.py`). 334 chunks, none failed, no label outside the rubric, no manual overrides.

## How reliable is it

- **Repeatability.** Two passes over the 200-repository sample assigned the same label in 1,029 of 1,200 cells (85.8%): delivery 95.0%, consent 90.0%, attribution 88.5%, lifetime 82.0%, scoping 80.0%, revocability 79.0%. Most flips are between a label and `insufficient_data`. See `results/repeatability_200.txt`.
- **Independent re-read.** A separate reviewer pass (also a language model, blind to the labels) read 20 of the September repositories in full and agreed on 96 of 120 cells (80.0%). Same model family, so this is agreement, not ground truth.
- **Quote check.** For labels that credit a server with a capability, the quoted evidence was found verbatim in the README for 71 of 78 revocation labels, 71 of 77 lifetime labels, 305 of 329 scoping labels, and 224 of 235 attribution labels. See `results/evidence_check.txt`.
- **Row-by-row review of one label.** The 36 rows labelled `agent_reachable_consent` were each re-read individually in a separate pass by a different model from the classifier. 24 document a confirmation step completed inside the agent's own tool call (13 confirm parameter, 5 two-call token, 6 approve or trust tool on the same server); 4 are sign-in flows the agent starts and a person completes; 3 are not approval steps; 2 pair a client dialog with a fallback the agent can satisfy; 1 uses an operator-held approval code; 2 are unclear from the text read. This is not a human audit, and it does not change any label. See `results/agent_operable_review.txt`.

### Numbers we do not report

A first pass in July and September read only the first 3,500 to 4,000 characters of each README and produced starker figures (for example, 57% with "no way to revoke a single agent"). A verification re-read exposed the truncation. On full READMEs those affirmative "worst label" figures fell sharply and moved between repeat passes, because they depend on how readily a classifier infers failure from a silent README. `stats_compute.py` and `headline_band.py` still print them so the comparison is visible. The study reports only what a README documents.

## Files

| File | What it is |
|---|---|
| `RUBRIC.md` | The classification prompt, verbatim |
| `frame-classified-1634.txt` | The 1,634 repositories classified (names only) |
| `frame-additions-2026-09-10.txt` | Which of those were added to the list after July 13 |
| `repeat-sample200-seed20260930.txt` | The seeded repeat sample |
| `aggregates-2026-09-30-v2.csv` | Count of every label on every dimension |
| `results/` | Output of the scripts below on the study's label files |
| `fetch_corpus.py`, `fetch_additions.py` | Fetch README, metadata, and top-level file names through the GitHub API (`gh` CLI) |
| `classify_full_readme.py` | The classification run (uses `rubric_detailed.py`, `classify_workflow.js`, `classify_additions_chunked.py`) |
| `stats_compute.py`, `headline_band.py`, `compare_runs.py`, `evidence_check.py`, `export_aggregates.py`, `arc_review.py` | The scripts that print every figure |

The scripts are published as they were run. They use only the Python standard library.

## Reproducing

1. Fetch each repository in `frame-classified-1634.txt` into `corpus/`, using the record shape in `fetch_additions.py` (point its input file at the full list). READMEs are not redistributed here; they belong to their authors and they change over time.
2. `python3 classify_full_readme.py --tag my-run` classifies the frame with the published rubric. It calls the `claude` CLI; adapt `classify()` to use another model.
3. `python3 stats_compute.py classifications-full-readme-my-run.jsonl` and `python3 evidence_check.py classifications-full-readme-my-run.jsonl` print the distributions and checks.

A fresh run will not match cell for cell. READMEs have changed since the fetch dates, and two passes of the same classifier agree on about 86% of cells. The "documents X" figures are the ones that held steady across passes.

## Data availability

The per-repository label files (labels plus evidence quotes for each of the 1,634 repositories, the repeat pass, the reviewer pass, and the row-by-row review) are not in this repository. The study is about the ecosystem, and we do not want to single out individual servers on the strength of a README read by a language model. Researchers who want the row-level data can ask at christopher@agentadmit.com.

If you maintain a server on the list and want to know how your README was read, ask at the same address.

## License and citation

Code: MIT (see `LICENSE`). Rubric and aggregate data: CC BY 4.0.

Cite as: AgentAdmit, "MCP User-Controllability Study," September 2026, https://blog.agentadmit.com/mcp-user-controllability-study-2026/

Published by [AgentAdmit](https://agentadmit.com).
