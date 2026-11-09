# Session-only feature cross-section (scheme C) — CURRENT

- Session: **Mon-Fri 14:35-16:00** (18 bars/day).
- `session_bars_per_year` ≈ **4697.9**.
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
| `from_first_bar_pnl_mean` | 0.0784 | 0.06936 | 0.009688 – 0.1596 | 0.09547 | 0.04375 |
| `from_first_bar_pnl_std` | 9.474 | 10 | 3.236 – 14.66 | 10.59 | 7.201 |
| `from_first_bar_pnl_skew` | -0.6678 | -0.5977 | -7.787 – 5.099 | -1.032 | 0.07038 |
| `from_first_bar_pnl_kurtosis_excess` | 804.9 | 482.2 | 232.7 – 1492 | 567.4 | 1287 |
| `from_first_sharpe` | 0.5348 | 0.5853 | 0.1045 – 0.8443 | 0.6148 | 0.3725 |
| `from_first_frac_bars_zero` | 0.958 | 0.9648 | 0.917 – 0.9918 | 0.9439 | 0.9864 |
| `from_first_n_active` | 2503 | 1997 | 358 – 5633 | 3376 | 730.3 |
| `final_cum_ot_pnl` | 4063 | 3700 | 537.2 – 8400 | 4926 | 2311 |
| `full_grid_bar_pnl_mean` | 0.04164 | 0.03793 | 0.005506 – 0.0861 | 0.05049 | 0.02369 |
| `full_grid_sharpe` | 0.3934 | 0.4273 | 0.09007 – 0.6723 | 0.4553 | 0.2676 |
