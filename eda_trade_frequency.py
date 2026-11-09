"""
Per-agent activity frequency and co-timing (ignore PnL sign).

Definition:
  active bar = 5-min bar where bar_pnl = diff(cum_ot_pnl) != 0

trades_per_year (NOT a year-by-year mean then average):
  n_active_bars / active_span_years
  active_span_years = (last_active_ts - first_active_ts) / (365.25 * 24 * 3600)

So it is a single career-average rate over the span from first to last nonzero bar.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "outputs_eda_light" / "time"


def load_bar_pnl(path: Path) -> pd.Series:
    df = pd.read_parquet(path, columns=["cum_ot_pnl"])
    if not isinstance(df.index, pd.DatetimeIndex):
        df = pd.read_parquet(path)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
    bar = df["cum_ot_pnl"].astype("float64").diff()
    bar.iloc[0] = 0.0
    return bar


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DATA)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    args = ap.parse_args()
    data_dir: Path = args.data_dir
    out: Path = args.out_dir
    figs, raw = out / "figs", out / "raw"
    for d in (out, figs, raw):
        d.mkdir(parents=True, exist_ok=True)

    files = sorted(data_dir.glob("pnl_*.parquet"))
    if not files:
        raise SystemExit(f"No parquet files in {data_dir}")
    rows = []
    hour_hits = np.zeros(24, dtype=np.int64)
    wd_hits = np.zeros(7, dtype=np.int64)
    HOW = 7 * 24
    agent_how = []

    for fp in files:
        parts = fp.stem.split("_")
        side, agent_id = parts[-1], parts[-2]
        bar = load_bar_pnl(fp)
        active = bar.to_numpy() != 0
        n_active = int(active.sum())
        idx = bar.index
        final_pnl = float(pd.read_parquet(fp, columns=["cum_ot_pnl"])["cum_ot_pnl"].iloc[-1])

        if n_active == 0:
            first = last = pd.NaT
            years = days = 0.0
            freq_per_year = freq_per_day = np.nan
            longest_gap_days = np.nan
        else:
            aidx = idx[active]
            first, last = aidx[0], aidx[-1]
            span_sec = (last - first).total_seconds()
            years = span_sec / (365.25 * 24 * 3600) if span_sec > 0 else 0.0
            days = span_sec / 86400 if span_sec > 0 else 0.0
            freq_per_year = n_active / years if years > 0 else np.nan
            freq_per_day = n_active / days if days > 0 else np.nan
            gaps = np.diff(aidx.view("i8")) / 1e9 / 86400
            longest_gap_days = float(gaps.max()) if len(gaps) else 0.0

            hours = aidx.hour.to_numpy()
            wds = aidx.dayofweek.to_numpy()
            for h in hours:
                hour_hits[h] += 1
            for w in wds:
                wd_hits[w] += 1
            how = np.zeros(HOW, dtype=np.float64)
            np.add.at(how, wds * 24 + hours, 1)
            agent_how.append((agent_id, side, how))

        rows.append(
            {
                "agent_id": agent_id,
                "side": side,
                "n_active_bars": n_active,
                "first_active_ts": first,
                "last_active_ts": last,
                "active_span_years": years,
                "trades_per_year": freq_per_year,
                "trades_per_calendar_day": freq_per_day,
                "avg_days_between_trades": (days / n_active) if n_active and days > 0 else np.nan,
                "longest_gap_between_trades_days": longest_gap_days,
                "final_cum_ot_pnl": final_pnl,
            }
        )

    freq = pd.DataFrame(rows).sort_values("trades_per_year", ascending=False)
    freq["freq_bucket"] = pd.cut(
        freq["trades_per_year"],
        bins=[-np.inf, 12, 52, 252, 504, np.inf],
        labels=["<1/month", "monthly_to_weekly", "weekly_to_daily", "~1-2_per_day", ">2_per_day"],
    )
    freq.to_csv(raw / "agent_trade_frequency.csv", index=False)

    ids = [x[0] for x in agent_how]
    M = np.vstack([x[2] for x in agent_how])
    norms = np.linalg.norm(M, axis=1, keepdims=True)
    norms[norms == 0] = 1
    sim = (M / norms) @ (M / norms).T
    pd.DataFrame(sim, index=ids, columns=ids).to_csv(raw / "agent_activity_tod_cosine.csv")

    pd.DataFrame({"hour": np.arange(24), "n_active_bars_all_agents": hour_hits}).to_csv(
        out / "activity_by_hour.csv", index=False
    )
    pd.DataFrame(
        {
            "weekday": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "n_active_bars_all_agents": wd_hits,
        }
    ).to_csv(out / "activity_by_weekday.csv", index=False)

    (out / "trade_frequency_readme.txt").write_text(
        "Definition: active bar = bar_pnl = diff(cum_ot_pnl) != 0.\n"
        "trades_per_year = n_active_bars / years(first_active, last_active).\n"
        "This is one career-average rate, NOT mean of per-calendar-year rates.\n"
        "year length = 365.25 days.\n"
    )

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(freq["trades_per_year"].dropna(), bins=20, color="#334155", edgecolor="white")
    ax.set_xlabel("active bars / year (first→last active)")
    ax.set_ylabel("n agents")
    ax.set_title("Agent activity frequency")
    fig.tight_layout()
    fig.savefig(figs / "fig_trades_per_year_hist.png", dpi=120)
    plt.close()

    hour_df = pd.read_csv(out / "activity_by_hour.csv")
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.bar(hour_df["hour"], hour_df["n_active_bars_all_agents"], color="#0f766e")
    ax.set_xlabel("hour of day")
    ax.set_ylabel("active bars (all agents)")
    ax.set_title("When do agents change PnL? (ignore sign)")
    fig.tight_layout()
    fig.savefig(figs / "fig_activity_by_hour.png", dpi=120)
    plt.close()

    order = np.argsort(-sim.mean(axis=1))
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(sim[order][:, order], vmin=0, vmax=1, cmap="viridis", aspect="auto")
    ax.set_title("Activity schedule cosine (hour-of-week)")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    fig.savefig(figs / "fig_activity_schedule_cosine.png", dpi=120)
    plt.close()

    print(f"wrote {raw / 'agent_trade_frequency.csv'} ({len(freq)} agents)")
    print("top by trades_per_year:")
    print(
        freq.head(5)[
            ["agent_id", "n_active_bars", "active_span_years", "trades_per_year"]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
