"""
Agent daily PnL correlation/covariance on session calendar (scheme C).

Session window (CLI) → sum bar_pnl per day → Pearson corr / cov.
Same calendar for all agents (inactive days = 0). Not from_first-truncated.

Outputs under outputs_eda_light/features/:
  raw/agent_daily_pnl_corr_session.csv
  raw/agent_daily_pnl_cov_session.csv
  figs/fig_agent_corr_session_daily.png
  CORR_README.md
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
DATA = ROOT / "data"
OUT = ROOT / "outputs_eda_light" / "features"
FNAME_RE = re.compile(
    r"pnl_[^_]+_\d+_\d+_([0-9A-Fa-f]+)_(long|short)\.parquet"
)


def parse_hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DATA)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--session-start", required=True, help="HH:MM inclusive (supplied by the data owner)")
    ap.add_argument("--session-end", required=True, help="HH:MM inclusive (supplied by the data owner)")
    args = ap.parse_args()
    out: Path = args.out_dir
    figs, raw = out / "figs", out / "raw"
    for d in (out, figs, raw):
        d.mkdir(parents=True, exist_ok=True)
    session_start = parse_hhmm(args.session_start)
    session_end = parse_hhmm(args.session_end)
    session_label = (
        f"Mon-Fri {session_start // 60:02d}:{session_start % 60:02d}"
        f"-{session_end // 60:02d}:{session_end % 60:02d}"
    )

    paths = sorted(args.data_dir.glob("*.parquet"))
    if not paths:
        raise SystemExit(f"No parquet files in {args.data_dir}")
    daily: dict[str, pd.Series] = {}
    sides: dict[str, str] = {}
    for fp in paths:
        m = FNAME_RE.match(fp.name)
        assert m, fp.name
        aid, side = m.group(1), m.group(2)
        sides[aid] = side
        df = pd.read_parquet(fp, columns=["timestamp", "cum_ot_pnl"])
        if "timestamp" not in df.columns:
            df = df.reset_index()
            if df.columns[0] != "timestamp":
                df = df.rename(columns={df.columns[0]: "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        tod = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
        mask = (df["timestamp"].dt.dayofweek < 5) & (tod >= session_start) & (tod <= session_end)
        s = df.loc[mask].copy()
        s["date"] = s["timestamp"].dt.floor("D")
        s["bar_pnl"] = s.groupby("date", sort=False)["cum_ot_pnl"].diff().fillna(0.0)
        daily[aid] = s.groupby("date", sort=True)["bar_pnl"].sum()

    M = pd.DataFrame(daily).sort_index().fillna(0.0)
    corr = M.corr()
    cov = M.cov()
    corr.to_csv(raw / "agent_daily_pnl_corr_session.csv")
    cov.to_csv(raw / "agent_daily_pnl_cov_session.csv")

    ids = list(corr.columns)
    L = [a for a in ids if sides[a] == "long"]
    S = [a for a in ids if sides[a] == "short"]
    mask = ~np.eye(len(corr), dtype=bool)
    vals = corr.values[mask]

    def block_ll(A: list[str]) -> float:
        sub = corr.loc[A, A].values
        n = len(A)
        if n < 2:
            return float("nan")
        return float(sub[~np.eye(n, dtype=bool)].mean())

    ll, ss = block_ll(L), block_ll(S)
    ls = float(corr.loc[L, S].values.mean()) if L and S else float("nan")
    order = L + S
    C = corr.loc[order, order]
    fig, ax = plt.subplots(figsize=(9, 8))
    im = ax.imshow(C.values, vmin=-0.5, vmax=1.0, cmap="RdBu_r", aspect="auto")
    ax.set_title(
        f"Daily session PnL correlation ({session_label})\nordered: long then short"
    )
    if L:
        ax.axhline(len(L) - 0.5, color="k", lw=0.8)
        ax.axvline(len(L) - 0.5, color="k", lw=0.8)
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(figs / "fig_agent_corr_session_daily.png", dpi=130)
    plt.close()

    (out / "CORR_README.md").write_text(
        "\n".join(
            [
                "# Agent PnL correlation (session daily)",
                "",
                f"**口径**: session `{session_label}` → 按日加总 → Pearson 相关。全员同一日历（未出手日=0）。",
                "",
                f"| pairwise mean | {vals.mean():.3f} |",
                f"| median | {np.median(vals):.3f} |",
                f"| long–long | {ll:.3f} |",
                f"| short–short | {ss:.3f} |",
                f"| long–short | {ls:.3f} |",
                "",
                "Human: `figs/fig_agent_corr_session_daily.png`",
                "Raw: `raw/agent_daily_pnl_corr_session.csv`, `raw/agent_daily_pnl_cov_session.csv`",
                "",
                "Re-run: `.venv/bin/python eda_agent_corr_session.py --data-dir ... --out-dir ...`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"corr mean={vals.mean():.3f} LL={ll:.3f} SS={ss:.3f} LS={ls:.3f}")
    print(f"wrote under {out}")


if __name__ == "__main__":
    main()
