# Validation performed on 18 November 2026

- 44 tests passed: 40 unchanged original model tests and 4 packaging regression tests.
- Original simulation model SHA-256 matches the internally frozen record: 63979400c9214c1f479a2b91161da99d96ed75adf6fde1ca0c20c356aa9cfc4e.
- Fresh simulation of seed 970000: all summary rows and event count exactly match archived seed 970000.
- All 200 archived teams were audited from raw logs, including snapshot/log hashes and simulation invariants; 218400 event records recomputed.
- Growth measures were re-extracted from all 200 teams.
- Six original per-team/summary result files checked numerically against the original study files (tolerance 1e-10).
- All 10 recalculated paired effects, bootstrap intervals, p values and Holm adjustments match archived results.
- All Figure 4 numerical inputs match the historical plotting CSV (tolerance 1e-12).
- English Figures 3–4 generated successfully. Figures 1–2 and their alternative drawing code were subsequently excluded at the authors’ request.
- During self-review, a complete new 200-team simulation was run (325.04 seconds, six workers). All per-team result rows and event counts matched the archive. The supported raw-audit entry point then audited all 218,400 new event records, re-extracted growth measures, and successfully regenerated Tables 1–4 and Figures 3–4. Tables 2–4 and Figure 4 matched the original archived reference values within 1e-10 tolerance.
- Tested dependency versions are in environment_tested.json. Portable entry points contain no user-specific paths or API credentials.

The package creation process copied the original inputs. Its initial raw audit refreshed the packaged derived CSVs; the final audit entry point writes to a separate output directory. Original study files outside this package were not modified.

Self-review also verified all ten historical frozen source hashes and found no author identifiers or original local absolute paths in packaged text inputs/source. See SELF_REVIEW.md for repaired issues and remaining boundaries.
