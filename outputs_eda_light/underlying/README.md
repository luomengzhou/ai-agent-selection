# Underlying identification

Method: local daily last 5m `price` vs Yahoo continuous futures close (`yfinance`).
Yahoo window: 2015-01-01 → 2026-10-10.

## Verdict
- **Mini** (`Mini_20261006_2158-120min-1130`) → **CME E-mini S&P 500 (ES)** (vs `ES=F`, level_corr=0.999938, return_corr=0.8508, median local/ref=1.0001, confidence=high)
- **Nasdaq** (`Nasdaq_20261019_1548_120min_1130`) → **CME E-mini Nasdaq-100 (NQ)** (vs `NQ=F`, level_corr=0.999943, return_corr=0.8623, median local/ref=1.0002, confidence=high)

## Caveats
- Local series is last 5-minute bar of the calendar day, not exchange official settle.
- Yahoo `ES=F` / `NQ=F` are continuous contracts; small level gaps vs a single front month are expected.
- Not single-name equities: all agents in a folder share one identical `price` path.

## Re-run
```bash
.venv/bin/python eda_underlying_fingerprint.py
```

## Files
- `yahoo_align_summary.csv` — human one-screen
- `raw/local_price_fingerprint.csv`
- `raw/yahoo_align_recent_days.csv`
