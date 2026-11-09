# Session-only feature cross-section (scheme C) — CURRENT

- Session: **Mon–Fri 11:35–13:30** (24 bars/day).
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
| `from_first_bar_pnl_mean` | 0.02172 | 0.01785 | 0.005511 – 0.0441 | 0.02467 | 0.01641 |
| `from_first_bar_pnl_std` | 2.583 | 2.334 | 1.637 – 3.838 | 2.352 | 2.999 |
| `from_first_bar_pnl_skew` | -1.98 | -0.888 | -6.341 – 3.657 | 0.04958 | -5.633 |
| `from_first_bar_pnl_kurtosis_excess` | 670 | 285.9 | 136.2 – 1301 | 354.7 | 1238 |
| `from_first_sharpe` | 0.6609 | 0.6163 | 0.1681 – 1.147 | 0.8054 | 0.4009 |
| `from_first_frac_bars_zero` | 0.9614 | 0.9639 | 0.9355 – 0.9843 | 0.954 | 0.9747 |
| `from_first_n_active` | 2212 | 1982 | 894.8 – 3601 | 2587 | 1537 |
| `final_cum_ot_pnl` | 1118 | 1104 | 265.5 – 1866 | 1276 | 832.4 |
| `full_grid_bar_pnl_mean` | 0.0086 | 0.008491 | 0.002043 – 0.01436 | 0.00982 | 0.006405 |
| `full_grid_sharpe` | 0.419 | 0.4288 | 0.1093 – 0.6866 | 0.5148 | 0.2464 |
