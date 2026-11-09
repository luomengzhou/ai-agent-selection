# Phase 1 EDA — aggregate results

Only pool-level, non-identifying statistics from the Phase 1 EDA are kept in this
repository. Agent-level tables, per-agent cumulative-PnL figures, launch dates,
trade-frequency statistics, the session window and the identified underlying are
derived from Sauma Capital's live trading pool and are **not redistributed**; the
scripts (`eda_*.py`) regenerate them locally from the raw parquet files.

Main cut: 70 agents (45 long / 25 short), 5-minute cumulative-PnL paths, 2006-01 to 2026-10.
Daily session PnL = sum of 5-minute `bar_pnl` inside the fixed daily session window;
Sharpe = mean / std of daily session PnL x sqrt(252), idle days kept as 0.

## Data-grid sanity checks

- All 70 files share an identical timestamp index (SHA-256 of the int64 array matches) and an
  identical `price` path, so the agents trade one common underlying on one common clock.
- Median bar spacing 300 s; 1,082 gaps longer than 5 minutes, all of them weekend / holiday breaks.
- Every holding spell starts and ends inside the session window; no position carries PnL outside it.

## Year-over-year Sharpe rank persistence (Spearman, year t vs t+1)

| year | n_agents | spearman_next_year |
|-----:|---------:|-------------------:|
| 2014 | 11 | -0.11 |
| 2015 | 18 | -0.09 |
| 2016 | 24 |  0.05 |
| 2017 | 29 | -0.06 |
| 2018 | 41 | -0.37 |
| 2019 | 48 |  0.17 |
| 2020 | 44 | -0.03 |
| 2021 | 45 | -0.44 |
| 2022 | 59 | -0.37 |
| 2023 | 53 |  0.49 |
| 2024 | 54 |  0.12 |
| 2025 | 63 |  0.11 |

**mean Spearman = -0.04.** Own yearly-Sharpe lag-1 autocorrelation (agents with >= 5 years):
median -0.15, positive for 14 of 53 agents.

## Naive walk-forward: top-10 trailing Sharpe vs equal-weight eligible pool

Per-agent average PnL over the following year; selection uses only prior data.

| year | n_eligible | top10_pnl | all_pnl | top10_sharpe | all_sharpe |
|-----:|-----------:|----------:|--------:|-------------:|-----------:|
| 2017 | 31 |  21.5 |  21.9 |  1.11 | 1.33 |
| 2018 | 39 | 120.7 | 126.6 |  2.52 | 3.47 |
| 2019 | 44 |  -8.4 |  39.5 | -0.29 | 1.62 |
| 2020 | 50 | 162.8 | 163.8 |  3.75 | 4.29 |
| 2021 | 56 |  63.9 |  80.8 |  1.37 | 2.69 |
| 2022 | 57 |  13.3 | 108.4 |  0.15 | 1.71 |
| 2023 | 62 | 283.8 | 198.4 |  3.25 | 3.58 |
| 2024 | 66 | 205.5 | 128.6 |  2.43 | 2.65 |
| 2025 | 67 | 357.7 | 219.2 |  3.12 | 2.25 |
| 2026 | 69 | 241.2 | 104.2 |  2.11 | 1.76 |

Top-10 beats the equal-weight pool in 4 of 10 years; mean Sharpe 1.95 vs 2.53.

## Cross-sectional co-movement (daily session PnL, 70 x 70 Pearson)

| statistic | value |
|---|---:|
| pairwise correlation, mean | 0.049 |
| pairwise correlation, median | 0.000 |
| mean long-long | 0.095 |
| mean short-short | 0.161 |
| mean long-short | -0.022 |

Spearman(Sharpe, max drawdown) across agents = -0.68 (idle days kept) / -0.82 (active days only).

## Same-side dead-hold check

Because every agent holds a fixed-size position for essentially the whole session, in-spell PnL
is identical to a same-direction passive hold over the same bars (gap = 0 for all 70 agents).
This is an alignment sanity check, not a selection signal.
