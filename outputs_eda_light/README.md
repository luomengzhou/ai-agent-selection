# Mini EDA (120min / 11:30 tag)

- Data: `Mini_20261006_2158-120min-1130` (70 agents)
- Session: **Mon–Fri 11:35–13:30**
- Mirrors the same EDA skeleton across Mini / Nasdaq 120 / Nasdaq 90.

## Layout (human + raw)

Each theme folder:
- **Root**: `README.md` + small one-screen tables / notes
- **`figs/`**: PNGs for humans
- **`raw/`**: wide/long CSVs (do not eyeball; for code re-analysis)

## Themes

| folder | look first |
|--------|------------|
| `features/` | `figs/` + `feature_cross_section_session_readme.md` + `top_bottom_sharpe_session.csv` |
| `time/` | `figs/` + small hour/weekday tables |
| `trades/` | `figs/` + `summary.txt` |
| `sharpe_dd/` | `figs/` + `summary.txt` |
| `hold_spell_vs_market/` | `hold_spell_summary.csv`（对齐后 gap≡0） |

### Mini-only (optional)
- `underlying/` — Yahoo fingerprint (ES/NQ)
- `sharpe_dd_active_days/` — same as `sharpe_dd/` but drop idle days

`inventory.csv` at root lists all agents.

Algorithm notes: [`docs/METHODOLOGY.md`](../docs/METHODOLOGY.md)
