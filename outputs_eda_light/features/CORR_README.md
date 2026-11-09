# Agent PnL correlation (session daily)

**口径**: Mon–Fri 11:35–13:30 session bars → **按日加总** `bar_pnl` → 70×70 Pearson 相关 / 协方差。  
全员同一日历（日频），未按各自 from_first 截断（未出手日=0）。

| 统计 | 值 |
|------|-----|
| pairwise corr mean | 0.049 |
| median | -0.000 |
| mean long–long | 0.095 |
| mean short–short | 0.161 |
| mean long–short | -0.022 |

Human: `figs/fig_agent_corr_session_daily.png`
Raw: `raw/agent_daily_pnl_corr_session.csv`, `raw/agent_daily_pnl_cov_session.csv`  
Script: inline in chat → will save as `eda_agent_corr_session.py` if needed.
