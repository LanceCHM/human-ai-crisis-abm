# Data dictionary and unit of analysis

All data are synthetic. `seed` identifies a simulated team, not a human participant. `arm` identifies one of five copies of that team's initial state. Use seed-matched comparisons, not independent-arm tests.

## Run files

* `runs/<seed>.json`: links arm/mode combinations to cached evaluation blocks; records mean completion and hashes of the log and snapshot. Identical states reuse evaluation blocks, so the number of logged test blocks is not necessarily the number of arm/mode combinations.
* `runs/<seed>.jsonl.gz`: one JSON object per event. `kind` separates initial events, training, and evaluation. Training includes `arm`, `learning` (`open` or `frozen`) and `episode`. Test `ref` links to the team JSON. `completion` is completed evacuees / 60; `completed` is the corresponding count. `trace` contains action, message and public-movement records; `venue_pairs`, `new_cases`, and `forecast_audit` support the experience analysis.
* `runs/<seed>.pkl.gz`: trusted Python snapshots containing the shared `initial` state and final `states` for all arms. The included model module is needed to deserialize these classes.

## Results files

| File | Unit | Relevant columns |
|---|---|---|
| 团队前后表现.csv | team × arm | `pre`, `post`: proportions averaged across 40 tasks; `gain_pp`: 100 × (post − pre) |
| 全部十项主要比较.csv | contrast | `mean`, `lower`, `upper`: percentage points; `p`: paired t test; `holm_p`: adjustment across ten contrasts; positive/zero/negative team counts |
| 记忆干预逐团队.csv | team × arm × reset | `reset`: venue or command; `effect_pp`: full − reset, **opposite to manuscript Table 4**; `plan_change`, `route_change`: task proportions |
| 记忆干预汇总.csv | arm × reset | same positive full-minus-reset convention; individual bootstrap intervals; separate six-test Holm family |
| 测试调用与早期误差.csv | team × arm | `early_brier`: earliest probability mean-squared error, averaged over exits/tasks; `early_venue_use`: task proportion with any earliest venue-memory use; `any_venue_use`: use by release; `command_use`: command-memory use |
| 描述性统计.csv | arm | means of pre/post performance, training costs and retrieval indicators; percentages explicitly named `_percent` |
| 场地案例覆盖.csv | team × arm × exit | retained case counts and label/digital-reading distributions |
| 训练成本与核验分配.csv | team × arm | mean training completion, release tick, operations, messages, field actions and verification allocation |

## Experience accumulation

`growth/逐团队经验形成.csv` contains one row per team and arm. `total_at60` counts all newly formed observation pairs over 60 training events. `age1_at60` counts the lag-1 subset. `retained_age1_exit0/1` count lag-1 cases still retained at the end. Cumulative formation is not retained stock. `first_both_round` can be blank when both exits never acquire the relevant experience; it must not be interpreted as zero.

`逐轮累计经验.csv` contains team × arm × training round trajectories. The quick manuscript reproduction uses the per-team file, while the raw audit re-extracts that file directly from logs and snapshots. The full historical trajectory CSV is retained for provenance but is not used by the manuscript figures.

`reference_figure4.csv` is the historical numerical plotting input used only as an independent reproduction target. It is not an input to the recalculation of Figure 4.

## Output conventions

Tables 2–4 are generated as CSV with unrounded floating-point values. Apply a consistent display rounding rule in the manuscript. Table 4 uses reset − full, negates the archived effect, and reverses interval endpoints. Figure 3 uses first-named minus second-named learning gains. Table 1 is a workflow specification transcribed from the manuscript, not a frequency estimated from execution logs. The CSVs are UTF-8 with BOM for spreadsheet compatibility.
