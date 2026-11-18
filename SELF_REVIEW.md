# Reproducibility and logic review

Review scope: the current anonymous JCCM manuscript, the final simulation, Tables 1–4, and empirical Figures 3–4. Conceptual Figures 1–2 are excluded by instruction. The manuscript and original study files were not edited.

## Problems identified and repaired

1. **Audit output contamination.** Existing audit directories could silently retain logs from a previous run. Audits now require a fresh output directory, validate the sample size before copying/linking inputs, and check the exact seed list.
2. **Incomplete input checks.** A row-count check alone could accept a duplicate team replacing a missing team. The reproduction script now requires the complete unique 200-team × five-arm matrix for performance, venue intervention, growth, and retrieval inputs. Learning gains are also checked against pre/post completion.
3. **Circular comparison.** Comparing a new run only with its own regenerated summaries does not establish reproduction of published findings. Tables 2–4 and Figure 4 now compare with archived reference values. Table 3 checks the number of contrasts before comparison, avoiding silent truncation by `zip`.
4. **Incomplete source provenance.** A historical auxiliary `s3_model.py` listed in the original freeze was absent. It is now archived solely for provenance; the runtime model is unchanged. All ten original frozen source checksums can be verified.
5. **Partial code fingerprinting.** New-run fingerprints now cover the original simulation worker and the portable runner as well as the model files.
6. **Documentation gaps.** A data dictionary, exact tested dependency pins, and explicit distinction between historical archive scripts and supported entry points have been added. Table 4 sign reversal, paired units, cached test blocks, and synthetic-data status are documented.
7. **Submission hygiene.** The manifest-based release builder excludes generated runs, caches, and virtual environments. A text scan found no author identities, emails, grant identifiers, or original local absolute paths in source/input text files.

## Evidence and remaining boundaries

The test suite contains 40 original model tests and four packaging regression tests. The original tests and active simulation engine remain unchanged. A new complete 200-team run reproduced all archived per-team summary rows and event counts (218,400 events). See VALIDATION.md for the final end-to-end audit and figure reproduction result.

The code supports the stated simulation comparisons, not a claim that the full embodied-knowledge erosion mechanism has been empirically established. G1 still permits routine observation and conditional verification. Equality of experience totals does not identify the causal effect of matching by itself, and non-significant S3–R/ALT contrasts do not establish equivalence.

Unresolved **manuscript** issues remain in MANUSCRIPT_DIFFERENCES.md: Table 4 transcription/rounding/sign inconsistencies, broad descriptions of G1, and overly broad interpretation of early retrieval/Brier measures. These require author review; the package does not alter numerical results to fit the prose.

Validation was performed on Windows/Python 3.12 with the recorded installed dependencies, not in a newly provisioned Linux/macOS environment or a container. No cross-platform pixel identity is promised. A public-repository location and code/data license remain author decisions rather than missing computational steps.
