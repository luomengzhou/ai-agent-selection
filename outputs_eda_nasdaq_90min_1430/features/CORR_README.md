# Agent PnL correlation (session daily)

**口径**: session `Mon-Fri 14:35-16:00` → 按日加总 → Pearson 相关。全员同一日历（未出手日=0）。

| pairwise mean | 0.032 |
| median | -0.000 |
| long–long | 0.080 |
| short–short | 0.072 |
| long–short | -0.025 |

Human: `figs/fig_agent_corr_session_daily.png`
Raw: `raw/agent_daily_pnl_corr_session.csv`, `raw/agent_daily_pnl_cov_session.csv`

Re-run: `.venv/bin/python eda_agent_corr_session.py --data-dir ... --out-dir ...`
