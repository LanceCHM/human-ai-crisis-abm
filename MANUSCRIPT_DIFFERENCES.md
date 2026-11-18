# Manuscript reconciliation required

1. Table 4: the per-team data yield a G2 **full-minus-reset** mean of +3.325 percentage points, hence a **reset-minus-full** mean of -3.325. The manuscript states -3.330. This is not the three-decimal rounding of the stored value. Do not change the data to obtain the manuscript number.
2. Table 4: the manuscript interval endpoints contain inconsistent signs/order. For reset-minus-full effects, `reproduce.py` bootstraps the negative per-team differences and outputs ordered signed bounds. G2 is approximately [-3.606, -3.042]; S3 is approximately [-7.353, -6.348]. Retain full precision CSVs and choose a consistent display rule for the paper.
3. S3 reset-minus-full is -6.880625, which rounds to -6.881 at three decimals, whereas the manuscript displays -6.880. Plan-change rates and some other reported numbers also depend on the chosen rounding precision.
4. G1 retains routine observation and conditional verification. Statements saying it has no practical interaction at all are broader than the implemented design.
5. Figure 4 describes early retrieval under a specific retrieval rule; zero early use is not proof of zero use at every later decision stage. Brier score is not a binary error rate.

The manuscript itself was not edited by this packaging task. Table 1 is transcribed as a design table, not presented as an automatically inferred execution-frequency table. Archived results include additional arms and diagnostic contrasts to avoid concealing results not selected for the manuscript.
