# Agent selection rules — full export (2026-11-03)

Snapshot of `agent_selection_rules.py` walk-forward outputs (main 70-agent cut; session window supplied locally).

Note: the `raw/` CSVs listed below (daily and per-agent paths) are kept local and are **not** committed to this repository; only the aggregate tables and figures are.

| File | Content |
|------|---------|
| `concat_path_stats.csv` | Concatenated OOS path totals (PnL, Sharpe, maxDD, Calmar, years beat b2) |
| `yearly_table.csv` | Per-year pool/kept counts and path PnL/Sharpe |
| `summary.txt` | Same stats as text + frozen D parameters |
| `raw/oos_daily_paths.csv` | Daily OOS PnL for rules / b1 / b2 + market close |
| `raw/oos_daily_paths_with_single_rules.csv` | Same + R1…R6 single-rule ablation paths |
| `single_rule_path_stats.csv` | Concat stats for combined / benchmarks / each single rule |
| `raw/selection_by_year.csv` | Every candidate agent × year: features, scores, cluster, kept |
| `raw/yearly_excess_vs_market.csv` | Yearly rules−b2 excess joined to market return / maxDD / vol (local only) |
| `figs/fig_oos_cum_paths.png` | Cum PnL: combined rules, two benchmarks, R1…R6 only (dashed) |
| `figs/fig_yearly_excess_vs_b2.png` | Yearly rules − b2 excess |

Single-rule definitions (same walk-forward years): R1–R4 = top 20%/side by that feature then R6 de-clone; **R5 only** = top 20% by track length `n_days` then de-clone; **R6 only** = de-clone the whole in-pool set (no score rank; tie-break `n_days`).

The yearly excess-vs-market notes (which tabulate the underlying's annual returns) are kept local and not committed.

Narrative write-up: [`../rules_results_2026-11-03.md`](../rules_results_2026-11-03.md).  
Live rerun default dir: `outputs_rules_light/` (same schema).
