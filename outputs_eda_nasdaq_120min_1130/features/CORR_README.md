# Agent PnL correlation (session daily)

**口径**: session `Mon-Fri 11:35-13:30` → 按日加总 → Pearson 相关。全员同一日历（未出手日=0）。

| pairwise mean | 0.054 |
| median | 0.017 |
| long–long | 0.086 |
| short–short | 0.181 |
| long–short | -0.019 |

Human: `figs/fig_agent_corr_session_daily.png`
Raw: `raw/agent_daily_pnl_corr_session.csv`, `raw/agent_daily_pnl_cov_session.csv`

Re-run: `.venv/bin/python eda_agent_corr_session.py --data-dir ... --out-dir ...`
