# sharpe_dd_active_days

**Mode:** ACTIVE DAYS ONLY — session days with PnL==0 removed

Mini-only companion to `sharpe_dd/`. Same layout: human `figs/` + `summary.txt`; detail in `raw/`.

## Human
- `figs/fig_cum_pnl_all70.png` (and other figs if present)
- `figs/fig_sharpe_vs_dd_freq.png`
- `cum_pnl_cohort_batches.csv`

## Raw
- `raw/agent_sharpe_dd.csv`
- `raw/sharpe_persistence_yoy.csv`, `raw/sharpe_autocorr_by_agent.csv`, `raw/walkforward_topk_sharpe.csv`

## Re-run
```bash
.venv/bin/python eda_sharpe_dd_persistence.py --drop-zero-days
```
