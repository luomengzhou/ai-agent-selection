# sharpe_dd

**Mode:** INCL. IDLE DAYS — session days with PnL==0 kept as 0

Sharpe = mean/std of daily session PnL × √252 (idle days after first trade stay as 0 and dilute mean/std)

Session window: Mon–Fri **11:35–13:30** → one daily PnL = sum of 5-min `bar_pnl` in that window.
Stats / plots start at each agent’s first nonzero day (`from_first`).

## Layout

- Human: `figs/`, `summary.txt`, `cum_pnl_cohort_batches.csv`
- Raw (agent-level / long tables): `raw/`

## Figures

- **`figs/fig_cum_pnl_all70.png`** — small-grid cum session PnL (no market), ordered by Sharpe.
- **`figs/fig_cum_pnl_all70_stacked.png`** — one wide row per agent + market twin axis, stacked by Sharpe. Left=cum PnL, right=market, orange dots=entries. INCL. IDLE DAYS — session days with PnL==0 kept as 0.
- **`figs/fig_sharpe_vs_dd_freq.png`** — Sharpe vs max DD / entries/year. Sharpe = mean/std of daily session PnL × √252 (idle days after first trade stay as 0 and dilute mean/std)
- **`cum_pnl_cohort_batches.csv`** — start-date cohort membership (small).

## Raw / text

- **`raw/agent_sharpe_dd.csv`** — primary ranking table (one row per agent).
- **`summary.txt`** — Top/bottom, Spearman, YoY, walk-forward blurb.
- **`raw/sharpe_persistence_yoy.csv`**, **`raw/sharpe_autocorr_by_agent.csv`**, **`raw/walkforward_topk_sharpe.csv`**.

## Re-run
```bash
.venv/bin/python eda_sharpe_dd_persistence.py
```

## Contrast
For the version that **deletes** idle (PnL=0) days, run with `--drop-zero-days` → `outputs_eda_light/sharpe_dd_active_days/`.
