"""
Scheme C: recompute agent features on the daily ~120min session only.

Session (empirical, matches all nonzero bar_pnl across 70 agents):
  Mon–Fri, clock time in [11:35, 13:30] inclusive  → 24 five-minute bars / day
  (= 120 minutes of bars; folder tag 120min-1130)

Two windows (both session-filtered):
  1) from_first: from each agent's first nonzero bar through end (session bars only)
  2) full_grid:  all session bars on the shared calendar (same start/end for everyone)

See docs/METHODOLOGY.md.
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
FEAT = ROOT / "outputs_eda_light" / "features"

FNAME_RE = re.compile(
    r"^pnl_(?:Mini|Nasdaq)_\d+_\d+_([0-9A-Fa-f]+)_(long|short)\.parquet$"
)


def parse_hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def parse_agent(path: Path) -> tuple[str, str]:
    m = FNAME_RE.match(path.name)
    if not m:
        raise ValueError(path.name)
    return m.group(1), m.group(2)


def load(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path, columns=["timestamp", "cum_ot_pnl"])
    if "timestamp" not in df.columns:
        df = pd.read_parquet(path)
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError(path)
        df = df.reset_index()
        if df.columns[0] != "timestamp":
            df = df.rename(columns={df.columns[0]: "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df[["timestamp", "cum_ot_pnl"]]


def bar_pnl(cum: np.ndarray) -> np.ndarray:
    out = np.empty_like(cum, dtype=np.float64)
    out[0] = 0.0
    out[1:] = cum[1:] - cum[:-1]
    return out


def session_mask(ts: pd.Series, session_start: int, session_end: int) -> np.ndarray:
    tod = ts.dt.hour.to_numpy() * 60 + ts.dt.minute.to_numpy()
    wd = ts.dt.dayofweek.to_numpy()
    return (wd < 5) & (tod >= session_start) & (tod <= session_end)


def moments(x: np.ndarray, bars_per_year: float) -> dict:
    x = x[np.isfinite(x)]
    n = x.size
    if n == 0:
        return {
            "n_bars": 0,
            "mean": np.nan,
            "std": np.nan,
            "skew": np.nan,
            "kurtosis_excess": np.nan,
            "sharpe": np.nan,
            "zero_share": np.nan,
            "n_active": 0,
        }
    s = pd.Series(x)
    mean = float(s.mean())
    std = float(s.std(ddof=1)) if n > 1 else np.nan
    skew = float(s.skew()) if n > 2 else np.nan
    kurt = float(s.kurt()) if n > 3 else np.nan
    sharpe = (
        mean / std * np.sqrt(bars_per_year)
        if std and std > 0 and np.isfinite(bars_per_year)
        else np.nan
    )
    n_active = int((x != 0).sum())
    return {
        "n_bars": n,
        "mean": mean,
        "std": std,
        "skew": skew,
        "kurtosis_excess": kurt,
        "sharpe": sharpe,
        "zero_share": float((x == 0).mean()),
        "n_active": n_active,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DATA)
    ap.add_argument("--out-dir", type=Path, default=FEAT)
    ap.add_argument("--session-start", default="11:35", help="HH:MM inclusive")
    ap.add_argument("--session-end", default="13:30", help="HH:MM inclusive")
    args = ap.parse_args()

    data_dir: Path = args.data_dir
    feat: Path = args.out_dir
    feat_figs, feat_raw = feat / "figs", feat / "raw"
    for d in (feat, feat_figs, feat_raw):
        d.mkdir(parents=True, exist_ok=True)
    session_start = parse_hhmm(args.session_start)
    session_end = parse_hhmm(args.session_end)
    session_label = (
        f"Mon-Fri {session_start // 60:02d}:{session_start % 60:02d}"
        f"-{session_end // 60:02d}:{session_end % 60:02d}"
    )

    paths = sorted(data_dir.glob("pnl_*.parquet"))
    if not paths:
        raise SystemExit(f"No parquet files in {data_dir}")
    # baseline session calendar
    base = load(paths[0])
    sm = session_mask(base["timestamp"], session_start, session_end)
    ts_sess = base.loc[sm, "timestamp"]
    span_days = (ts_sess.iloc[-1] - ts_sess.iloc[0]).total_seconds() / 86400.0
    n_sess_full = int(sm.sum())
    bars_per_year = n_sess_full / (span_days / 365.25) if span_days > 1 else np.nan
    bars_per_day = ts_sess.groupby(ts_sess.dt.floor("D")).size()
    print(
        f"session={session_label} | "
        f"n_session_bars={n_sess_full} | typical_bars/day={bars_per_day.mode().iloc[0]} | "
        f"bars_per_year_est={bars_per_year:.2f}"
    )

    rows = []
    for i, p in enumerate(paths):
        agent_id, side = parse_agent(p)
        df = load(p)
        bp = bar_pnl(df["cum_ot_pnl"].to_numpy(dtype=np.float64))
        m = session_mask(df["timestamp"], session_start, session_end)
        bp_s = bp[m]
        ts_s = df["timestamp"].to_numpy()[m]
        active = bp_s != 0
        if active.any():
            first_i = int(np.flatnonzero(active)[0])
            last_i = int(np.flatnonzero(active)[-1])
            first_ts = pd.Timestamp(ts_s[first_i])
            last_ts = pd.Timestamp(ts_s[last_i])
            seg = bp_s[first_i:]
        else:
            first_ts = last_ts = pd.NaT
            first_i = None
            seg = np.array([], dtype=np.float64)

        m_from = moments(seg, bars_per_year)
        m_full = moments(bp_s, bars_per_year)
        final = float(df["cum_ot_pnl"].iloc[-1])

        # Column names: see outputs_eda_light/features/COLUMN_DICTIONARY_session.md
        row = {
            "agent_id": agent_id,
            "side": side,
            "session": session_label,
            "first_nonzero_ts": first_ts,
            "last_nonzero_ts": last_ts,
            "final_cum_ot_pnl": final,
            # constants (same for every agent — shared calendar)
            "session_bars_per_year": bars_per_year,
            "n_session_bars_shared": m_full["n_bars"],
        }
        for prefix, mm in (("from_first", m_from), ("full_grid", m_full)):
            row[f"{prefix}_n_bars"] = mm["n_bars"]
            row[f"{prefix}_n_active"] = mm["n_active"]
            # fraction of bars in this window with bar_pnl == 0
            row[f"{prefix}_frac_bars_zero"] = mm["zero_share"]
            row[f"{prefix}_bar_pnl_mean"] = mm["mean"]
            row[f"{prefix}_bar_pnl_std"] = mm["std"]
            row[f"{prefix}_bar_pnl_skew"] = mm["skew"]
            row[f"{prefix}_bar_pnl_kurtosis_excess"] = mm["kurtosis_excess"]
            row[f"{prefix}_sharpe"] = mm["sharpe"]
        rows.append(row)
        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{len(paths)}]", flush=True)

    out = pd.DataFrame(rows).sort_values("from_first_sharpe", ascending=False)
    out_path = feat_raw / "eda_light_summary_session.csv"
    out.to_csv(out_path, index=False)
    # Human one-screen: top/bottom 5 by from_first_sharpe
    tb_cols = [
        "agent_id",
        "side",
        "from_first_sharpe",
        "final_cum_ot_pnl",
        "from_first_n_active",
    ]
    top = out.head(5)[tb_cols].assign(rank_group="top")
    bot = out.tail(5).sort_values("from_first_sharpe")[tb_cols].assign(rank_group="bottom")
    pd.concat([top, bot], ignore_index=True).to_csv(
        feat / "top_bottom_sharpe_session.csv", index=False
    )

    # cross-section on from_first_* (main C table for viewing)
    feat_cols = [
        "from_first_bar_pnl_mean",
        "from_first_bar_pnl_std",
        "from_first_bar_pnl_skew",
        "from_first_bar_pnl_kurtosis_excess",
        "from_first_sharpe",
        "from_first_frac_bars_zero",
        "from_first_n_active",
        "final_cum_ot_pnl",
        "full_grid_bar_pnl_mean",
        "full_grid_sharpe",
    ]
    cross_rows = []
    for col in feat_cols:
        s = out[col]
        cross_rows.append(
            {
                "feature": col,
                "n": int(s.notna().sum()),
                "mean": float(s.mean()),
                "std": float(s.std(ddof=1)),
                "min": float(s.min()),
                "p10": float(s.quantile(0.10)),
                "p25": float(s.quantile(0.25)),
                "p50": float(s.median()),
                "p75": float(s.quantile(0.75)),
                "p90": float(s.quantile(0.90)),
                "max": float(s.max()),
                "mean_long": float(out.loc[out.side == "long", col].mean()),
                "mean_short": float(out.loc[out.side == "short", col].mean()),
            }
        )
    cross = pd.DataFrame(cross_rows)
    cross.to_csv(feat / "feature_cross_section_session.csv", index=False)

    # Canonical feature plots (scheme C = session + from_first). Filenames include the口径.
    plot_cols = [
        "from_first_bar_pnl_mean",
        "from_first_bar_pnl_std",
        "from_first_bar_pnl_skew",
        "from_first_bar_pnl_kurtosis_excess",
        "from_first_sharpe",
        "from_first_frac_bars_zero",
        "from_first_n_active",
        "final_cum_ot_pnl",
    ]
    # English titles only (matplotlib default font lacks CJK)
    title_c = f"scheme C: session {session_label} + from_first (incl. in-session zeros)"

    fig, axes = plt.subplots(2, 4, figsize=(14, 6.5))
    for ax, col in zip(axes.ravel(), plot_cols):
        for side, color in [("long", "#1d4ed8"), ("short", "#b45309")]:
            ax.hist(
                out.loc[out.side == side, col].dropna(),
                bins=12,
                alpha=0.55,
                color=color,
                label=side,
                edgecolor="white",
            )
        ax.axvline(out[col].mean(), color="#111827", ls="--", lw=1)
        ax.set_title(col, fontsize=9)
        ax.tick_params(labelsize=7)
    axes[0, 0].legend(fontsize=7)
    fig.suptitle(f"Feature hist by side | {title_c}", fontsize=11)
    fig.tight_layout()
    fig.savefig(feat_figs / "fig_feature_hist_session_from_first.png", dpi=130)
    plt.close()

    fig, axes = plt.subplots(2, 4, figsize=(14, 6.5))
    for ax, col in zip(axes.ravel(), plot_cols):
        data = [out.loc[out.side == s, col].dropna() for s in ("long", "short")]
        ax.boxplot(data, tick_labels=["long", "short"], showfliers=True)
        ax.set_title(col, fontsize=9)
        ax.tick_params(labelsize=7)
    fig.suptitle(f"Feature boxplots by side | {title_c}", fontsize=11)
    fig.tight_layout()
    fig.savefig(feat_figs / "fig_feature_box_session_from_first.png", dpi=130)
    plt.close()

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for side, color in [("long", "#1d4ed8"), ("short", "#b45309")]:
        m = out["side"] == side
        axes[0].scatter(
            out.loc[m, "from_first_bar_pnl_mean"],
            out.loc[m, "from_first_bar_pnl_std"],
            c=color,
            s=28,
            alpha=0.8,
            label=side,
        )
        axes[1].scatter(
            out.loc[m, "from_first_sharpe"],
            out.loc[m, "final_cum_ot_pnl"],
            c=color,
            s=28,
            alpha=0.8,
            label=side,
        )
        axes[2].scatter(
            out.loc[m, "from_first_bar_pnl_skew"],
            out.loc[m, "from_first_bar_pnl_kurtosis_excess"],
            c=color,
            s=28,
            alpha=0.8,
            label=side,
        )
    axes[0].set_xlabel("from_first_bar_pnl_mean")
    axes[0].set_ylabel("from_first_bar_pnl_std")
    axes[0].set_title("mean vs std")
    axes[1].set_xlabel("from_first_sharpe")
    axes[1].set_ylabel("final_cum_ot_pnl")
    axes[1].set_title("sharpe vs final PnL")
    axes[2].set_xlabel("from_first_bar_pnl_skew")
    axes[2].set_ylabel("from_first_kurtosis_excess")
    axes[2].set_title("skew vs kurtosis")
    axes[0].legend(fontsize=8)
    fig.suptitle(f"Feature scatters | {title_c}", fontsize=11)
    fig.tight_layout()
    fig.savefig(feat_figs / "fig_feature_scatters_session_from_first.png", dpi=130)
    plt.close()

    # Remove stale generic names that pointed at pre-session 口径 (if present)
    for stale in (
        "fig_feature_hist_by_side.png",
        "fig_feature_box_by_side.png",
        "fig_feature_scatters.png",
        "fig_feature_hist_session.png",  # replaced by *_session_from_first
        "feature_cross_section_readme.md",  # old full-grid cheat sheet
    ):
        p = feat / stale
        if p.exists():
            p.unlink()

    typical_bpd = int(bars_per_day.mode().iloc[0])
    lines = [
        "# Session-only feature cross-section (scheme C) — CURRENT",
        "",
        f"- Session: **{session_label}** ({typical_bpd} bars/day).",
        f"- `session_bars_per_year` ≈ **{bars_per_year:.1f}**.",
        "- Column dictionary: `COLUMN_DICTIONARY_session.md`.",
        "- Figure evolution / 口径变更: `FIGURES_AND_DATA_EVOLUTION.md`.",
        "- **Main plots use from_first_*** on session bars.",
        "- Layout: human layer here + `figs/`; agent-level detail in `raw/`.",
        "",
        "## Figures (regenerate with `eda_session_features.py`)",
        "",
        "| file | 口径 |",
        "|------|------|",
        "| `figs/fig_feature_hist_session_from_first.png` | session + from_first |",
        "| `figs/fig_feature_box_session_from_first.png` | session + from_first |",
        "| `figs/fig_feature_scatters_session_from_first.png` | session + from_first |",
        "",
        "| feature | mean | p50 | p10–p90 | mean_long | mean_short |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in cross_rows:
        lines.append(
            f"| `{r['feature']}` | {r['mean']:.4g} | {r['p50']:.4g} | "
            f"{r['p10']:.4g} – {r['p90']:.4g} | {r['mean_long']:.4g} | {r['mean_short']:.4g} |"
        )
    (feat / "feature_cross_section_session_readme.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n" + cross.to_string(index=False))
    print(f"\nwrote {out_path}")
    print("TOP 5 from_first_sharpe:")
    print(
        out.head(5)[
            [
                "agent_id",
                "side",
                "from_first_sharpe",
                "from_first_bar_pnl_mean",
                "final_cum_ot_pnl",
                "from_first_n_active",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
