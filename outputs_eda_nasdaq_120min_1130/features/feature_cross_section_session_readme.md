# Session-only feature cross-section (scheme C) — CURRENT

- Session: **Mon-Fri 11:35-13:30** (24 bars/day).
- `session_bars_per_year` ≈ **6263.8**.
- Column dictionary: `COLUMN_DICTIONARY_session.md`.
- Figure evolution / 口径变更: `FIGURES_AND_DATA_EVOLUTION.md`.
- **Main plots use from_first_*** on session bars.
- Layout: human layer here + `figs/`; agent-level detail in `raw/`.

## Figures (regenerate with `eda_session_features.py`)

| file | 口径 |
|------|------|
| `figs/fig_feature_hist_session_from_first.png` | session + from_first |
| `figs/fig_feature_box_session_from_first.png` | session + from_first |
| `figs/fig_feature_scatters_session_from_first.png` | session + from_first |

| feature | mean | p50 | p10–p90 | mean_long | mean_short |
|---|---:|---:|---:|---:|---:|
| `from_first_bar_pnl_mean` | 0.08302 | 0.072 | 0.01687 – 0.1482 | 0.08602 | 0.07215 |
| `from_first_bar_pnl_std` | 10.4 | 9.945 | 6.038 – 14.38 | 10.31 | 10.72 |
| `from_first_bar_pnl_skew` | -0.4894 | -0.8884 | -2.85 – 2.949 | -0.9218 | 1.078 |
| `from_first_bar_pnl_kurtosis_excess` | 303.3 | 241.2 | 118.1 – 584.2 | 254.2 | 481.4 |
| `from_first_sharpe` | 0.6023 | 0.5941 | 0.2138 – 1.013 | 0.6408 | 0.4628 |
| `from_first_frac_bars_zero` | 0.9458 | 0.9515 | 0.9035 – 0.9832 | 0.9366 | 0.9791 |
| `from_first_n_active` | 3738 | 3292 | 1011 – 7553 | 4401 | 1337 |
| `final_cum_ot_pnl` | 5100 | 5019 | 1442 – 8477 | 5329 | 4272 |
| `full_grid_bar_pnl_mean` | 0.03921 | 0.03858 | 0.01109 – 0.06517 | 0.04097 | 0.03284 |
| `full_grid_sharpe` | 0.4243 | 0.4307 | 0.1607 – 0.6738 | 0.4524 | 0.3221 |
