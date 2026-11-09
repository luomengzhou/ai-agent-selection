"""
Round-trips from position = round(ΔPnL / Δprice), only on bars where price moved.

A flat-price bar cannot show a position change. Carrying the last position
forward makes a flatten during a frozen price look like an overnight hold:
the next tick (often the Sunday 18:05 reopen) gaps, but ΔPnL on that bar is 0.

A spell is a run of price-move bars with position ±4.
  entry        first such bar
  last_held    last such bar (still in the position while price was ticking)
  flat_seen    next price-move bar, where position is observed at 0
  gap_dpnl     PnL change on flat_seen. 0 means the gap did not hit a position.

Outputs under outputs_eda_light/trades/.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "Mini_20261006_2158-120min-1130"
OUT = ROOT / "outputs_eda_light" / "trades"
FNAME_RE = re.compile(
    r"pnl_(?:Mini|Nasdaq)_\d+_\d+_([0-9A-Fa-f]+)_(long|short)\.parquet"
)


def parse_hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def spells_for(
    df: pd.DataFrame, agent: str, side: str, session_lo: int, session_hi: int
) -> list[dict]:
    dpx = df["price"].astype(float).diff()
    dpnl = df["cum_ot_pnl"].astype(float).diff()
    moved = dpx.ne(0) & dpx.notna()
    pos = (dpnl[moved] / dpx[moved]).round(6)
    on = pos.ne(0).to_numpy()
    idx = pos.index
    dpx_m = dpx.loc[idx].to_numpy()
    dpnl_m = dpnl.loc[idx].to_numpy()
    tod = idx.hour * 60 + idx.minute

    rows = []
    n = len(on)
    i = 0
    while i < n:
        if not on[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and on[j + 1]:
            j += 1
        flat = j + 1 if j + 1 < n else None
        entry, last = idx[i], idx[j]
        outside = int(((tod[i : j + 1] < session_lo) | (tod[i : j + 1] > session_hi)).sum())
        rows.append(
            dict(
                agent=agent,
                side=side,
                entry=entry,
                last_held=last,
                flat_seen=idx[flat] if flat is not None else pd.NaT,
                hold_min=(last - entry).total_seconds() / 60,
                reveal_delay_min=((idx[flat] - last).total_seconds() / 60) if flat is not None else np.nan,
                n_price_bars=j - i + 1,
                outside_session_bars=outside,
                gap_dpx=float(dpx_m[flat]) if flat is not None else np.nan,
                gap_dpnl=float(dpnl_m[flat]) if flat is not None else np.nan,
                entry_min=int(entry.hour * 60 + entry.minute),
                last_min=int(last.hour * 60 + last.minute),
            )
        )
        i = j + 1
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DATA)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--session-start", default="11:35")
    ap.add_argument("--session-end", default="13:30")
    args = ap.parse_args()
    out: Path = args.out_dir
    figs, raw = out / "figs", out / "raw"
    for d in (out, figs, raw):
        d.mkdir(parents=True, exist_ok=True)
    session_lo = parse_hhmm(args.session_start)
    session_hi = parse_hhmm(args.session_end)
    session_span = session_hi - session_lo
    sess_lab = (
        f"{session_lo // 60:02d}:{session_lo % 60:02d}"
        f"-{session_hi // 60:02d}:{session_hi % 60:02d}"
    )

    rows: list[dict] = []
    for fp in sorted(args.data_dir.glob("*.parquet")):
        m = FNAME_RE.match(fp.name)
        assert m, fp.name
        df = pd.read_parquet(fp)
        if "timestamp" not in df.columns:
            df = df.reset_index()
            if df.columns[0] != "timestamp":
                df = df.rename(columns={df.columns[0]: "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp").sort_index()
        rows.extend(spells_for(df, m.group(1)[:6], m.group(2), session_lo, session_hi))

    T = pd.DataFrame(rows)
    same_day = T["flat_seen"].dt.date.eq(T["entry"].dt.date)
    delayed = T["reveal_delay_min"].gt(120)
    T["flat_same_day"] = same_day.fillna(False)
    T["delayed_reveal"] = delayed.fillna(False)
    T.to_csv(raw / "trade_spells.csv", index=False)
    T.loc[T["delayed_reveal"]].to_csv(raw / "delayed_flat_reveals.csv", index=False)

    gap_hit = T.loc[T["delayed_reveal"], "gap_dpnl"].abs().gt(1e-9)
    outside = int(T["outside_session_bars"].sum())
    entry_at_start = int((T.entry_min == session_lo).sum())
    summary = [
        f"spells={len(T)}  agents={T['agent'].nunique()}",
        f"entry at {session_lo // 60:02d}:{session_lo % 60:02d}: "
        f"{entry_at_start} ({(T.entry_min == session_lo).mean():.1%})",
        f"last in-position bar inside {sess_lab}: "
        f"{int(((T.last_min >= session_lo) & (T.last_min <= session_hi)).sum())}",
        f"price-move bars with position on, outside that window: {outside}",
        f"hold minutes (entry → last bar still on): median {T.hold_min.median():.0f}  "
        f"p10 {T.hold_min.quantile(.1):.0f}  p90 {T.hold_min.quantile(.9):.0f}",
        f"flat observed same calendar day: {int(T.flat_same_day.sum())}",
        f"flat observed >2h later (price had frozen): {int(T.delayed_reveal.sum())}",
        f"of those, gap bar with nonzero PnL: {int(gap_hit.sum())}",
        f"median |gap| points on delayed reveals: {T.loc[T.delayed_reveal, 'gap_dpx'].abs().median():.2f}",
    ]
    (out / "summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))

    def clock(mins: pd.Series) -> pd.Series:
        return mins.map(lambda m: f"{int(m) // 60:02d}:{int(m) % 60:02d}")

    entry_h = T["entry_min"].value_counts().sort_index()
    axes[0, 0].bar(clock(entry_h.index), entry_h.values, color="tab:blue")
    axes[0, 0].set_title(f"Entry time  (n={len(T)})")
    axes[0, 0].set_ylabel("trades")

    axes[0, 1].hist(T["hold_min"], bins=40, color="tab:blue")
    axes[0, 1].axvline(session_span, color="k", lw=0.8, ls="--")
    axes[0, 1].set_title("Minutes from entry to last bar still in position")
    axes[0, 1].set_xlabel(f"minutes (dashed = {session_span}, full session span)")

    last_h = T["last_min"].value_counts().sort_index()
    axes[1, 0].bar(clock(last_h.index), last_h.values, color="tab:blue")
    axes[1, 0].tick_params(axis="x", labelrotation=60, labelsize=7)
    axes[1, 0].set_title("Clock time of last in-position price bar")

    d = T.loc[T["delayed_reveal"]]
    axes[1, 1].scatter(d["gap_dpx"], d["gap_dpnl"], s=18, c="tab:red")
    axes[1, 1].axhline(0, color="k", lw=0.6)
    axes[1, 1].set_title(f"Delayed flat reveal (n={len(d)}): gap vs PnL")
    axes[1, 1].set_xlabel("price change on the bar we first see flat")
    axes[1, 1].set_ylabel("PnL change on that bar")

    fig.suptitle("Position only counted when the underlying price moved")
    fig.tight_layout()
    fig.savefig(figs / "fig_trade_distribution.png", dpi=130)
    plt.close()
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
