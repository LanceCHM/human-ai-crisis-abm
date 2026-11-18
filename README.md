# Reproduction package for the human–AI collaboration simulation study

This package contains the final agent-based simulation used for the manuscript, the original 200-team simulation records, and scripts connecting those records to Tables 1–4 and empirical Figures 3–4. It follows the current JCCM anonymous manuscript and is arranged for anonymous review. Figures 1–2 are explicitly excluded at the authors’ request. No API key, language-model service, network connection, or personal participant data is required to run the model. The AI component is a programmed information aggregation and recommendation module, not a generative language model.

## Quick start

Use Python 3.12 (the original execution version). From this directory:

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/verify_manifest.py
python -m pytest tests -q
python scripts/reproduce.py
```

The last command produces CSV tables and English Figures 3–4 in `outputs/reproduced`. Figures 1–2 are outside the scope of this package. No simulation is needed for this quick reproduction. The script recalculates paired statistics from team-level data rather than copying the published summary tables. Tables 2–4 and Figure 4 are checked against the original archived results, including when reproducing a newly simulated run. See DATA_DICTIONARY.md for units, fields, and sign conventions.

For the exact tested dependency versions, install `requirements-tested.txt` instead of the version ranges in `requirements.txt`. The operating-system/Python environment itself is not a container image. Run the entry points under `scripts/`; files in `archive/` preserve historical code and may reference historical layouts when run directly.

The original freeze lists a historical `s3_model.py` copy. It is preserved under `archive/frozen_sources` solely so every frozen source checksum can be verified; the active engine is `src/stage2_abm/model.py`. The manifest verifier checks both the release inventory and all ten original frozen source entries. The original model tests have not been rewritten.

## Directory structure

```text
src/stage2_abm/             Final simulation model, unchanged from the frozen study
tests/                     40 original model checks plus 4 packaging regression tests
archive/                   Original runner, analysis, growth extraction, frozen protocol
data/published/runs/        200 teams: compressed logs, memory snapshots, JSON summaries
data/published/results/     Original team-level and summary CSV files
data/published/growth/      Experience accumulation extracted from the same training logs
assets/                    Empirical manuscript images and table text for provenance
scripts/simulate.py         Portable entry point for new simulation runs
scripts/audit_raw.py        Recompute statistics and growth measures from full logs
scripts/reproduce.py        Assemble Tables 1–4 and regenerate empirical Figures 3–4
scripts/plot_figure3.py      Paired-difference plotting logic
scripts/plot_figure4.py      Experience matrix plotting logic
outputs/                   Generated results; not the original study inputs
MANIFEST.sha256             Checksums of packaged source and input files
VALIDATION.md               Checks performed when preparing this package
MANUSCRIPT_DIFFERENCES.md   Numerical/presentation discrepancies requiring author review
```

Chinese filenames in the archived datasets are retained to preserve their lineage. All public entry points and this guide are in English. Raw records occupy approximately 531 MiB; allow several GB of free disk space for new runs and extracted outputs.

## What experiment is included

The final independent confirmation uses seeds **970000–970199**, with 200 matched teams across five arms. Each team contains site (`venue`), rescue, medical, and command roles. The same seed supplies the same initial state and task sequence across arms; do not treat the five arms or the 40 evaluation tasks as independent sample units.

* G1: routine AI workflow, without the added dedicated practical-verification stage. Routine observation and condition-triggered verification remain possible.
* G2: dedicated verification of Exit 0.
* S3: dedicated verification of the exit with greater estimated uncertainty, based on available information and experience.
* R: random selection of one verification target using a separate named random stream.
* ALT: target alternation by task index.

There are 12 common initial events, 60 training events under learning-enabled and learning-frozen conditions, and 40 common held-out tasks tested without AI. Tests release the plan at tick 6 and do not update memory. Site-memory interventions restore the initial site memory while preserving other trained roles. The archive also retains all five site-memory interventions and the S3 command-memory intervention, even though Table 4 selects three arms.

Default configuration and actual decision rules are in `src/stage2_abm/model.py`; arm overrides are in `archive/run.py:config`. In particular, the model has 60 evacuees, including 12 requiring special assistance, three zones, two exits, per-role operation budget 6, deadline 6, memory capacity 100, and up to five retrieved neighbors. See the code rather than inferring additional behavior from the conceptual diagrams. Historical exploratory variants and human-survey projects are outside this package.

The protocol was internally frozen, not externally preregistered. These are synthetic simulation data, not measured human behavior.

## Traceability from manuscript to outputs

| Item | Source and extraction | Output |
|---|---|---|
| Table 1 | Workflow/design specification; transcribed from manuscript, not estimated from outcomes. Check against `Config`, arm overrides, and target-selection rules. | `Table_1.csv` |
| Table 2 | `团队前后表现.csv`: mean pre-test and post-test completion across teams; gains in percentage points. | `Table_2.csv` |
| Table 3 | Paired team gain differences; 10,000 paired-team bootstrap draws, RNG seed 261026; two-sided paired t tests; Holm adjustment over all 10 contrasts. | `Table_3.csv` |
| Table 4 | `记忆干预逐团队.csv`: mean reset-minus-full completion and plan-change proportions; select G1, G2, S3 site-memory resets. | `Table_4.csv` |
| Figure 3 | Team-level gain differences; 200 points per contrast; fixed jitter RNG seed 20261102. | PNG/PDF/SVG and underlying CSV |
| Figure 4 | Per-team growth records plus `测试调用与早期误差.csv`; average across the 200 teams in each arm. | PNG/PDF/SVG and `Figure_4_data.csv` |

Bootstrap intervals have individual, not simultaneous, coverage. Pairing is preserved across comparisons. Frozen-learning changes are zero, so the learning gain reduces to the learning-enabled post-minus-pre change.

For Figure 4, new pairs are cumulative training additions, while retained cases are the memory contents at training end. Lag 1 means a one-step interval between digital and on-site readings, not the age of a stored memory. Early use means at least one exit retrieves memory at the earliest judgment. Brier score is mean squared probability error, not the fraction of incorrect decisions. Colors use separate within-column scales.

## Recompute from the archived raw logs

```sh
python scripts/audit_raw.py
python scripts/reproduce.py --data outputs/raw_audit --output outputs/from_raw
```

The first command verifies log/snapshot hashes, checks action budgets, delays, public movement, fixed test timing and policy rules, then recomputes team-level statistics and experience measures. It uses original numerical analysis logic but omits legacy Chinese plots and reports unrelated to this manuscript. Use a fresh audit output directory. Input logs are linked or copied to the output directory; input files are not modified. Only load the bundled trusted pickle snapshots; Python pickle is not a safe format for untrusted downloaded files.

## Run the simulation again

Smoke test (one team; not the paper's statistical sample):

```sh
python scripts/simulate.py --teams 1 --workers 1 --output outputs/smoke_new
```

Full reproduction:

```sh
python scripts/simulate.py --teams 200 --workers 4 --output outputs/new_run
python scripts/audit_raw.py --run outputs/new_run --output outputs/new_run_audit
python scripts/reproduce.py --data outputs/new_run_audit --output outputs/new_run_figures
```

Use a fresh simulation output directory: the runner refuses to mix old and new runs. Original execution recorded roughly 256 seconds using six workers on the original machine; this is historical timing, not a performance guarantee. The final model and original simulation worker are unchanged. The new wrapper makes output paths portable, permits a one-team smoke test, and removes dependence on a separate historical exploratory checkout used only for cross-version regression. It does not rerun that historical three-team compatibility test; the packaged model tests and new-run checks are reported separately.

## Scope, corrections, and release

Read `MANUSCRIPT_DIFFERENCES.md` before submission. The package reports calculated values faithfully rather than altering them to match manuscript transcription or rounding mistakes. It does not establish that accumulated experience is always useful, that S3 is superior to R/ALT, or that the full long-term embodied-knowledge erosion mechanism has been demonstrated.

No open-source license is imposed by this packaging operation. The authors should choose an appropriate code/data license and repository when preparing a public release. Remove identifying repository links during anonymous review. No author biographies, emails, credentials, local virtual environments, or manuscript DOCX files are included.

For upload, run `python scripts/build_release.py`. It checks file integrity and creates `Final_Code_Anonymous.zip` alongside this directory, using only the release manifest. This excludes Python caches, local environments, and the large new-run validation outputs. Prefer this clean archive to zipping the entire working directory after running simulations. Cross-platform execution has not been independently tested; packaging validation was performed on Windows with Python 3.12.
