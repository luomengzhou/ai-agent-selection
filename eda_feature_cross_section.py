"""
DEPRECATED for main plots.

This script reads the OLD full-grid table `eda_light_summary.csv`
(24h bars + from first nonzero, including off-session zeros).

Current canonical cross-section plots are produced by:
  eda_session_features.py
  → fig_feature_*_session_from_first.png

See outputs_eda_light/features/FIGURES_AND_DATA_EVOLUTION.md
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
FEAT_DIR = ROOT / "outputs_eda_light" / "features"
# tolerate pre-move flat layout
SUMMARY_CANDIDATES = [
    FEAT_DIR / "eda_light_summary.csv",
    ROOT / "outputs_eda_light" / "eda_light_summary.csv",
]

FEATURE_COLS = [
    "bar_pnl_mean",
    "bar_pnl_std",
    "bar_pnl_skew",
    "bar_pnl_kurtosis_excess",
    "sharpe_simple",
    "final_cum_ot_pnl",
    "n_bars_valid_segment",
    "zero_bar_share_full",
]


def find_summary() -> Path:
    for p in SUMMARY_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError("eda_light_summary.csv not found; run eda_mini_light.py first")


def main() -> None:
    print(
        "WARNING: eda_feature_cross_section.py uses OLD full-grid口径.\n"
        "For CURRENT session+from_first figures run: eda_session_features.py\n"
        "Writing only to features/_archive_fullgrid_cross_section/ ..."
    )
    FEAT_DIR.mkdir(parents=True, exist_ok=True)
    arch = FEAT_DIR / "_archive_fullgrid_cross_section"
    arch.mkdir(parents=True, exist_ok=True)
    src = find_summary()
    df = pd.read_csv(src)
    # keep a canonical copy inside features/
    if src.resolve() != (FEAT_DIR / "eda_light_summary.csv").resolve():
        df.to_csv(FEAT_DIR / "eda_light_summary.csv", index=False)

    rows = []
    for col in FEATURE_COLS:
        if col not in df.columns:
            continue
        s = df[col]
        rows.append(
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
                "mean_long": float(df.loc[df["side"] == "long", col].mean()),
                "mean_short": float(df.loc[df["side"] == "short", col].mean()),
            }
        )
    cross = pd.DataFrame(rows)
    cross.to_csv(arch / "feature_cross_section_summary.csv", index=False)

    by_side = (
        df.groupby("side")[FEATURE_COLS]
        .agg(["count", "mean", "std", "median", "min", "max"])
    )
    by_side.to_csv(arch / "feature_by_side_summary.csv")

    # histograms: 2x4
    plot_cols = [c for c in FEATURE_COLS if c in df.columns][:8]
    fig, axes = plt.subplots(2, 4, figsize=(14, 6.5))
    axes = axes.ravel()
    for ax, col in zip(axes, plot_cols):
        for side, color in [("long", "#1d4ed8"), ("short", "#b45309")]:
            sub = df.loc[df["side"] == side, col].dropna()
            ax.hist(sub, bins=12, alpha=0.55, color=color, label=side, edgecolor="white")
        ax.axvline(df[col].mean(), color="#111827", ls="--", lw=1, label="mean_all")
        ax.set_title(col, fontsize=9)
        ax.tick_params(labelsize=7)
    axes[0].legend(fontsize=7, loc="best")
    for ax in axes[len(plot_cols) :]:
        ax.axis("off")
    fig.suptitle("ARCHIVED full-grid 口径 (not session)", fontsize=12)
    fig.tight_layout()
    fig.savefig(arch / "fig_feature_hist_by_side.png", dpi=130)
    plt.close()

    # boxplots
    fig, axes = plt.subplots(2, 4, figsize=(14, 6.5))
    axes = axes.ravel()
    for ax, col in zip(axes, plot_cols):
        data = [df.loc[df["side"] == s, col].dropna() for s in ("long", "short")]
        ax.boxplot(data, tick_labels=["long", "short"], showfliers=True)
        ax.set_title(col, fontsize=9)
        ax.tick_params(labelsize=7)
    for ax in axes[len(plot_cols) :]:
        ax.axis("off")
    fig.suptitle("ARCHIVED full-grid 口径 (not session)", fontsize=12)
    fig.tight_layout()
    fig.savefig(arch / "fig_feature_box_by_side.png", dpi=130)
    plt.close()

    # key scatters
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for side, color in [("long", "#1d4ed8"), ("short", "#b45309")]:
        m = df["side"] == side
        axes[0].scatter(df.loc[m, "bar_pnl_mean"], df.loc[m, "bar_pnl_std"], c=color, s=28, alpha=0.8, label=side)
        axes[1].scatter(df.loc[m, "sharpe_simple"], df.loc[m, "final_cum_ot_pnl"], c=color, s=28, alpha=0.8, label=side)
        axes[2].scatter(df.loc[m, "bar_pnl_skew"], df.loc[m, "bar_pnl_kurtosis_excess"], c=color, s=28, alpha=0.8, label=side)
    axes[0].set_xlabel("mean"); axes[0].set_ylabel("std"); axes[0].set_title("mean vs std")
    axes[1].set_xlabel("sharpe"); axes[1].set_ylabel("final PnL"); axes[1].set_title("sharpe vs final PnL")
    axes[2].set_xlabel("skew"); axes[2].set_ylabel("excess kurtosis"); axes[2].set_title("skew vs kurtosis")
    axes[0].legend(fontsize=8)
    fig.suptitle("ARCHIVED full-grid 口径", fontsize=11)
    fig.tight_layout()
    fig.savefig(arch / "fig_feature_scatters.png", dpi=130)
    plt.close()

    lines = [
        "# ARCHIVED — full-grid cross-section (not current)",
        "",
        "See `../FIGURES_AND_DATA_EVOLUTION.md`. Current plots: `eda_session_features.py`.",
        "",
    ]
    (arch / "README.md").write_text("\n".join(lines), encoding="utf-8")

    print(cross.to_string(index=False))
    print(f"\nwrote under {arch}")


if __name__ == "__main__":
    main()
