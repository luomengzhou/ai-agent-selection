# Agent selection rules (R1-R6) walk-forward

Implements docs/agent_selection_rules_zh.md sections 1-4. Each year Y, features use data up to the last session day before Y (`feature_asof`); the kept agents' daily PnL over Y is the OOS path.

- `raw/oos_daily_paths.csv`: daily OOS PnL of rules and benchmarks b1/b2, plus market close.
- `raw/selection_by_year.csv`: one row per candidate agent per year with all features, scores, selection and cluster flags.
- `yearly_table.csv`: per-year pool/kept counts, PnL and Sharpe of each path, excess vs b2.
- `concat_path_stats.csv`: concatenated-path total PnL / Sharpe / maxDD / Calmar.
- `summary.txt`: concatenated-path stats, yearly table, D parameters.
- `figs/fig_oos_cum_paths.png`, `figs/fig_yearly_excess_vs_b2.png`.

Dated snapshot of this primary run: `docs/rules_results_2026-11-03/`. The `raw/` CSVs (daily and per-agent paths) are local only and git-ignored.

Rerun: `.venv/bin/python agent_selection_rules.py [--data-dir DIR --out-dir DIR --session-start HH:MM --session-end HH:MM]`

## Diagnostics
`.venv/bin/python agent_selection_diagnostics.py` → `diagnostics.txt`: single-rule ablation and a random
same-size-selection null (300 draws from the same point-in-time pool).
