"""
Identify Mini / Nasdaq parquet underlyings by aligning local daily last prices
to Yahoo continuous futures (ES=F, NQ=F).

Outputs under outputs_eda_light/underlying/.
Requires: yfinance (installed on first run if missing).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs_eda_light" / "underlying"
YAHOO_START, YAHOO_END = "2015-01-01", "2026-10-10"

FOLDERS = {
    "Mini": ROOT / "Mini_20261006_2158-120min-1130",
    "Nasdaq": ROOT / "Nasdaq_20261019_1548_120min_1130",
}
REFS = ("ES=F", "NQ=F")


def _ensure_yfinance():
    try:
        import yfinance as yf  # noqa: F401
    except ImportError:
        import subprocess
        import sys

        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "yfinance"])
    import yfinance as yf

    return yf


def load_local_daily(folder: Path) -> pd.Series:
    fp = next(folder.glob("*.parquet"))
    df = pd.read_parquet(fp)
    if "timestamp" not in df.columns:
        df = df.reset_index()
        if df.columns[0] != "timestamp":
            df = df.rename(columns={df.columns[0]: "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()
    daily = df["price"].astype(float).groupby(df.index.normalize()).last()
    daily.index = pd.to_datetime(daily.index).tz_localize(None)
    return daily.rename(folder.name)


def yahoo_close(yf, symbol: str) -> pd.Series:
    raw = yf.download(symbol, start=YAHOO_START, end=YAHOO_END, progress=False, auto_adjust=True)
    if isinstance(raw.columns, pd.MultiIndex):
        s = raw["Close"].iloc[:, 0] if raw["Close"].ndim > 1 else raw["Close"]
    else:
        s = raw["Close"]
    s = s.astype(float).dropna()
    s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
    return s.rename(symbol)


def pair_stats(local: pd.Series, ref: pd.Series) -> dict:
    both = pd.concat([local.rename("local"), ref.rename("ref")], axis=1, join="inner").dropna()
    both = both[both.index.dayofweek < 5]
    if len(both) < 50:
        return dict(n_overlap=len(both))
    abs_err = (both["local"] - both["ref"]).abs()
    return dict(
        n_overlap=int(len(both)),
        overlap_start=str(both.index.min().date()),
        overlap_end=str(both.index.max().date()),
        level_corr=float(both["local"].corr(both["ref"])),
        return_corr=float(both["local"].pct_change().corr(both["ref"].pct_change())),
        median_local_over_ref=float((both["local"] / both["ref"]).median()),
        median_abs_diff=float(abs_err.median()),
        p90_abs_diff=float(abs_err.quantile(0.9)),
        local_last=float(both["local"].iloc[-1]),
        ref_last=float(both["ref"].iloc[-1]),
    )


def folder_fingerprint(folder: Path) -> dict:
    fps = sorted(folder.glob("*.parquet"))
    a = pd.read_parquet(fps[0])
    b = pd.read_parquet(fps[1]) if len(fps) > 1 else a
    pa = a["price"].astype(float).to_numpy()
    pb = b["price"].astype(float).to_numpy()
    dpx = pd.Series(pa).diff().abs()
    dpx = dpx[dpx > 0]
    return dict(
        folder=folder.name,
        n_files=len(fps),
        n_rows=len(a),
        price_min=float(np.min(pa)),
        price_median=float(np.median(pa)),
        price_max=float(np.max(pa)),
        price_last=float(pa[-1]),
        median_abs_tick=float(dpx.median()) if len(dpx) else np.nan,
        agents_share_identical_price=bool(len(pa) == len(pb) and np.array_equal(pa, pb)),
    )


def main() -> None:
    raw = OUT / "raw"
    for d in (OUT, raw):
        d.mkdir(parents=True, exist_ok=True)
    yf = _ensure_yfinance()

    prints = [folder_fingerprint(p) for p in FOLDERS.values() if p.is_dir()]
    pd.DataFrame(prints).to_csv(raw / "local_price_fingerprint.csv", index=False)

    locals_ = {k: load_local_daily(p) for k, p in FOLDERS.items() if p.is_dir()}
    refs = {s: yahoo_close(yf, s) for s in REFS}

    rows = []
    for label, local in locals_.items():
        for sym, ref in refs.items():
            st = pair_stats(local, ref)
            rows.append(dict(local_label=label, yahoo=sym, **st))
    S = pd.DataFrame(rows)
    S.to_csv(OUT / "yahoo_align_summary.csv", index=False)

    # recent side-by-side for the winning pairs
    pieces = []
    for label, yahoo in (("Mini", "ES=F"), ("Nasdaq", "NQ=F")):
        if label not in locals_:
            continue
        both = pd.concat(
            [locals_[label].rename(f"{label}_local"), refs[yahoo].rename(yahoo)],
            axis=1,
            join="inner",
        ).dropna()
        both = both[both.index.dayofweek < 5].tail(10)
        both.insert(0, "pair", f"{label}_vs_{yahoo}")
        both.index.name = "date"
        pieces.append(both.reset_index())
    if pieces:
        pd.concat(pieces, ignore_index=True).to_csv(raw / "yahoo_align_recent_days.csv", index=False)

    # verdict from max level_corr with median ratio near 1
    verdict_lines = [
        "# Underlying identification",
        "",
        "Method: local daily last 5m `price` vs Yahoo continuous futures close (`yfinance`).",
        f"Yahoo window: {YAHOO_START} → {YAHOO_END}.",
        "",
        "## Verdict",
    ]
    for label in locals_:
        sub = S.loc[S["local_label"] == label].sort_values("level_corr", ascending=False)
        best = sub.iloc[0]
        ratio_ok = abs(best.get("median_local_over_ref", 0) - 1.0) < 0.02
        conf = "high" if best.get("level_corr", 0) > 0.999 and ratio_ok else "medium"
        product = {"ES=F": "CME E-mini S&P 500 (ES)", "NQ=F": "CME E-mini Nasdaq-100 (NQ)"}.get(
            best["yahoo"], best["yahoo"]
        )
        verdict_lines.append(
            f"- **{label}** (`{FOLDERS[label].name}`) → **{product}** "
            f"(vs `{best['yahoo']}`, level_corr={best['level_corr']:.6f}, "
            f"return_corr={best['return_corr']:.4f}, median local/ref={best['median_local_over_ref']:.4f}, "
            f"confidence={conf})"
        )
    verdict_lines += [
        "",
        "## Caveats",
        "- Local series is last 5-minute bar of the calendar day, not exchange official settle.",
        "- Yahoo `ES=F` / `NQ=F` are continuous contracts; small level gaps vs a single front month are expected.",
        "- Not single-name equities: all agents in a folder share one identical `price` path.",
        "",
        "## Re-run",
        "```bash",
        '.venv/bin/python eda_underlying_fingerprint.py',
        "```",
        "",
        "## Files",
        "- `yahoo_align_summary.csv` — human one-screen",
        "- `raw/local_price_fingerprint.csv`",
        "- `raw/yahoo_align_recent_days.csv`",
        "",
    ]
    (OUT / "README.md").write_text("\n".join(verdict_lines), encoding="utf-8")
    print("\n".join(verdict_lines))
    print(S.to_string(index=False))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
