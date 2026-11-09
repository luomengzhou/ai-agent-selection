#!/usr/bin/env python3
"""
Sauma Capital Mini — lightweight EDA (memory-conscious, one file at a time).

Full methodology: docs/METHODOLOGY.md

Definitions
-----------
- bar_pnl = cum_ot_pnl.diff(); first bar filled with 0.0 (so n_bars matches file rows).
- zero bar: bar_pnl == 0
- Summary stats window ("valid segment"): from first nonzero bar_pnl INCLUSIVE
  through the END of the full series. This INCLUDES all later zero bars
  (not "active bars only"). So mean/std/skew/kurtosis are diluted by zeros.
- Sharpe (simple): (mean_bar_pnl / std_bar_pnl) * sqrt(BARS_PER_YEAR)
  BARS_PER_YEAR = n_bars_full / (span_calendar_days / 365.25) on the shared grid.

Outputs (default)
-----------------
  outputs_eda_light/inventory.csv
  outputs_eda_light/time/      — gaps, zeros, activity, align (figs/ + raw/)
  outputs_eda_light/features/ — eda_light_summary, outliers, cum PnL reps (figs/ + raw/)

Usage
-----
  .venv/bin/python eda_mini_light.py
  .venv/bin/python eda_mini_light.py --limit 3   # debug
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "Mini_20261006_2158-120min-1130"
OUT_DIR = ROOT / "outputs_eda_light"
LONG_GAP_SEC = 5 * 60  # >5 min for weekday×hour counts
FNAME_RE = re.compile(
    r"^pnl_(?:Mini|Nasdaq)_\d+_\d+_([0-9A-Fa-f]+)_(long|short)\.parquet$"
)


def parse_agent(path: Path) -> tuple[str, str]:
    m = FNAME_RE.match(path.name)
    if not m:
        raise ValueError(f"Unexpected filename: {path.name}")
    return m.group(1), m.group(2)


def hash_int64_array(arr: np.ndarray) -> str:
    """Stable content hash for int64 nanosecond timestamps (or any contiguous int64)."""
    a = np.ascontiguousarray(arr, dtype=np.int64)
    return hashlib.sha256(a.tobytes()).hexdigest()


def load_cols(path: Path) -> pd.DataFrame:
    """Read only needed columns; timestamp as UTC-naive DatetimeIndex-friendly series."""
    df = pd.read_parquet(path, columns=["timestamp", "price", "cum_ot_pnl"])
    # parquet may store timestamp as column or already index depending on writer;
    # our files have timestamp as a column that pandas may promote — normalize.
    if "timestamp" not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            if df.columns[0] != "timestamp":
                df = df.rename(columns={df.columns[0]: "timestamp"})
        else:
            raise ValueError(f"No timestamp in {path}")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def bar_pnl_from_cum(cum: np.ndarray) -> np.ndarray:
    """bar_pnl = diff(cum); first bar = 0.0 (documented fill)."""
    out = np.empty_like(cum, dtype=np.float64)
    out[0] = 0.0
    out[1:] = cum[1:] - cum[:-1]
    return out


def longest_zero_run(is_zero: np.ndarray) -> int:
    if is_zero.size == 0:
        return 0
    # run-length via diff of padded mask
    m = is_zero.astype(np.int8)
    if not m.any():
        return 0
    # find runs of 1s
    padded = np.concatenate(([0], m, [0]))
    d = np.diff(padded)
    starts = np.where(d == 1)[0]
    ends = np.where(d == -1)[0]
    return int((ends - starts).max()) if len(starts) else 0


def estimate_bars_per_year(median_dt_sec: float, n_bars: int, span_days: float) -> float:
    """
    Annualization for Sharpe.
    Prefer: observed bars / observed calendar years, scaled to 1 year of *same density*.
    Fallback: if span tiny, use 365.25 * (86400 / median_dt) * (n_bars / theoretical_full).
    We use: bars_per_year = n_bars / (span_days / 365.25) when span_days > 1.
    This reflects the actual trading calendar density in the sample (includes gaps).
    """
    if span_days > 1 and n_bars > 0:
        return float(n_bars) / (span_days / 365.25)
    if median_dt_sec > 0:
        return 365.25 * 86400.0 / median_dt_sec
    return float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--limit", type=int, default=0, help="process only first N files (debug)")
    args = ap.parse_args()

    data_dir: Path = args.data_dir
    out_dir: Path = args.out_dir
    time_dir = out_dir / "time"
    feat_dir = out_dir / "features"
    time_figs, time_raw = time_dir / "figs", time_dir / "raw"
    feat_figs, feat_raw = feat_dir / "figs", feat_dir / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    for d in (time_dir, feat_dir, time_figs, time_raw, feat_figs, feat_raw):
        d.mkdir(parents=True, exist_ok=True)

    paths = sorted(data_dir.glob("pnl_*.parquet"))
    if args.limit and args.limit > 0:
        paths = paths[: args.limit]
    if not paths:
        print(f"No parquet files in {data_dir}", file=sys.stderr)
        return 1

    print(f"Found {len(paths)} parquet files under {data_dir}")
    print(f"Output -> {out_dir} (time/, features/)")

    # ---------- inventory ----------
    inv_rows = []
    for p in paths:
        agent_id, side = parse_agent(p)
        inv_rows.append(
            {
                "agent_id": agent_id,
                "side": side,
                "path": p.name,  # file name only; no local absolute paths in committed outputs
                "n_rows": None,  # filled on read
                "file_bytes": p.stat().st_size,
            }
        )
    inv = pd.DataFrame(inv_rows)

    # ---------- pass 1: baseline timestamps/prices + per-agent stats ----------
    base_ts_ns: np.ndarray | None = None
    base_ts_hash: str | None = None
    base_price: np.ndarray | None = None
    base_agent: str | None = None
    base_ts: pd.DatetimeIndex | None = None

    align_lines: list[str] = []
    ts_mismatch = 0
    price_mismatch = 0
    price_checked = 0

    activity_rows = []
    missing_rows = []
    summary_rows = []

    # For zero_calendar: accumulate per-day sums
    # day -> {n_bars (from base), sum_zero_share, n_all_zero, price_open, price_close}
    day_sum_zero = {}  # date -> sum of zero_share
    day_n_all_zero = {}  # date -> count agents with all bars zero that day
    day_n_agents = {}  # date -> agents counted
    day_n_bars = {}  # date -> n bars (set from base)
    day_price_open = {}
    day_price_close = {}

    # keep light series for plot agents later: store cum for selected after we know picks
    # first pass: only scalars; second mini-pass for 4 plot agents
    agent_meta = {}  # agent_id -> dict for selection

    # Gap stats computed once from baseline timestamps
    gap_summary = None
    gap_by_wh = None
    bars_per_year = float("nan")
    median_dt_sec = float("nan")

    for i, p in enumerate(paths):
        agent_id, side = parse_agent(p)
        print(f"[{i+1}/{len(paths)}] {p.name}", flush=True)
        df = load_cols(p)
        n = len(df)
        inv.loc[inv["agent_id"] == agent_id, "n_rows"] = n

        ts = df["timestamp"].to_numpy(dtype="datetime64[ns]")
        ts_ns = ts.view("int64")
        price = df["price"].to_numpy(dtype=np.float64)
        cum = df["cum_ot_pnl"].to_numpy(dtype=np.float64)
        bp = bar_pnl_from_cum(cum)
        is_zero = bp == 0.0

        # --- align ---
        h = hash_int64_array(ts_ns)
        if base_ts_ns is None:
            base_ts_ns = ts_ns
            base_ts_hash = h
            base_price = price
            base_agent = agent_id
            base_ts = pd.DatetimeIndex(ts)
            align_lines.append("METHOD")
            align_lines.append(
                "- timestamp: SHA256 of int64 ns array; also np.array_equal vs baseline."
            )
            align_lines.append(
                f"- price: full-array equality vs baseline agent {base_agent} "
                "(np.allclose rtol=0 atol=0 for finite; NaN positions must match)."
            )
            align_lines.append(f"BASELINE_AGENT={base_agent}")
            align_lines.append(f"BASELINE_N={n}")
            align_lines.append(f"BASELINE_TS_SHA256={base_ts_hash}")
            align_lines.append(f"BASELINE_TS_MIN={base_ts.min()}")
            align_lines.append(f"BASELINE_TS_MAX={base_ts.max()}")

            # gaps from baseline
            dt_sec = np.diff(ts_ns) / 1e9
            median_dt_sec = float(np.median(dt_sec)) if dt_sec.size else float("nan")
            span_days = (ts_ns[-1] - ts_ns[0]) / 1e9 / 86400.0 if n > 1 else 0.0
            bars_per_year = estimate_bars_per_year(median_dt_sec, n, span_days)

            qs = [0, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 1.0]
            qvals = np.quantile(dt_sec, qs) if dt_sec.size else [np.nan] * len(qs)
            gap_summary = pd.DataFrame(
                {
                    "stat": [f"q{int(q*100):02d}" if q not in (0, 1) else ("min" if q == 0 else "max") for q in qs]
                    + [
                        "mean",
                        "std",
                        "n_gaps",
                        "n_gaps_gt_5min",
                        "n_gaps_gt_1h",
                        "n_gaps_gt_1d",
                        "median_dt_sec",
                        "mode_approx_sec",
                        "bars_per_year_est",
                        "span_calendar_days",
                    ],
                    "value_sec": list(qvals)
                    + [
                        float(np.mean(dt_sec)) if dt_sec.size else np.nan,
                        float(np.std(dt_sec)) if dt_sec.size else np.nan,
                        int(dt_sec.size),
                        int((dt_sec > LONG_GAP_SEC).sum()),
                        int((dt_sec > 3600).sum()),
                        int((dt_sec > 86400).sum()),
                        median_dt_sec,
                        float(median_dt_sec),  # 5m grid -> median==mode typically
                        bars_per_year,
                        span_days,
                    ],
                }
            )
            # also human labels for quantile rows
            gap_summary.loc[: len(qs) - 1, "stat"] = [
                "min",
                "p01",
                "p05",
                "p25",
                "p50",
                "p75",
                "p95",
                "p99",
                "max",
            ]

            long_mask = dt_sec > LONG_GAP_SEC
            if long_mask.any():
                # attribute gap to the timestamp at the *end* of the gap (arrival bar)
                end_ts = pd.to_datetime(ts[1:][long_mask])
                gdf = pd.DataFrame({"ts": end_ts})
                gdf["weekday"] = gdf["ts"].dt.dayofweek  # Mon=0
                gdf["hour"] = gdf["ts"].dt.hour
                gap_by_wh = (
                    gdf.groupby(["weekday", "hour"], as_index=False)
                    .size()
                    .rename(columns={"size": "n_gaps_gt_5min"})
                )
            else:
                gap_by_wh = pd.DataFrame(columns=["weekday", "hour", "n_gaps_gt_5min"])

            # calendar day price open/close from baseline
            day = pd.Series(ts).dt.floor("D")
            # vectorized day aggregates for price
            tmp = pd.DataFrame({"day": day, "price": price})
            grp = tmp.groupby("day", sort=True)
            day_n_bars_series = grp.size()
            day_price_open_s = grp["price"].first()
            day_price_close_s = grp["price"].last()
            for d, nb in day_n_bars_series.items():
                key = pd.Timestamp(d).date()
                day_n_bars[key] = int(nb)
                day_price_open[key] = float(day_price_open_s.loc[d])
                day_price_close[key] = float(day_price_close_s.loc[d])
                day_sum_zero[key] = 0.0
                day_n_all_zero[key] = 0
                day_n_agents[key] = 0

            align_lines.append(f"MEDIAN_DT_SEC={median_dt_sec}")
            align_lines.append(f"BARS_PER_YEAR_EST={bars_per_year}")
            align_lines.append(
                "NOTE: gap stats computed on baseline timestamps only "
                "(valid iff all agents share the same timestamp index)."
            )
        else:
            same_ts = h == base_ts_hash and np.array_equal(ts_ns, base_ts_ns)
            if not same_ts:
                ts_mismatch += 1
                align_lines.append(f"TS_MISMATCH agent={agent_id} sha={h} n={n}")
            # price compare
            price_checked += 1
            if base_price is not None and price.shape == base_price.shape:
                both_nan = np.isnan(price) & np.isnan(base_price)
                finite_eq = np.isclose(
                    np.where(np.isnan(price), 0, price),
                    np.where(np.isnan(base_price), 0, base_price),
                    rtol=0,
                    atol=0,
                    equal_nan=False,
                )
                ok = bool(np.all(both_nan | finite_eq) and np.array_equal(np.isnan(price), np.isnan(base_price)))
                if not ok:
                    # count mismatches
                    bad = ~(both_nan | (price == base_price))
                    n_bad = int(bad.sum())
                    price_mismatch += 1
                    align_lines.append(
                        f"PRICE_MISMATCH agent={agent_id} n_bad={n_bad}"
                    )
            else:
                price_mismatch += 1
                align_lines.append(f"PRICE_SHAPE_MISMATCH agent={agent_id}")

        # --- missing / outliers ---
        n_nan_price = int(np.isnan(price).sum())
        n_nan_cum = int(np.isnan(cum).sum())
        n_nan_bp = int(np.isnan(bp).sum())
        n_inf_price = int(np.isinf(price).sum())
        n_inf_cum = int(np.isinf(cum).sum())
        n_inf_bp = int(np.isinf(bp).sum())
        n_dup_ts = int(n - len(np.unique(ts_ns)))
        # extreme quantiles on finite values
        def qstats(x, name_prefix):
            x = x[np.isfinite(x)]
            if x.size == 0:
                return {f"{name_prefix}_{k}": np.nan for k in ("min", "p001", "p01", "p99", "p999", "max")}
            qs = np.quantile(x, [0, 0.001, 0.01, 0.99, 0.999, 1.0])
            keys = ("min", "p001", "p01", "p99", "p999", "max")
            return {f"{name_prefix}_{k}": float(v) for k, v in zip(keys, qs)}

        miss = {
            "agent_id": agent_id,
            "side": side,
            "n_rows": n,
            "n_nan_price": n_nan_price,
            "n_nan_cum_ot_pnl": n_nan_cum,
            "n_nan_bar_pnl": n_nan_bp,
            "n_inf_price": n_inf_price,
            "n_inf_cum_ot_pnl": n_inf_cum,
            "n_inf_bar_pnl": n_inf_bp,
            "n_dup_timestamp": n_dup_ts,
        }
        miss.update(qstats(price, "price"))
        miss.update(qstats(bp, "bar_pnl"))
        missing_rows.append(miss)

        # --- activity ---
        nz = np.flatnonzero(~is_zero)
        if nz.size:
            first_i = int(nz[0])
            last_i = int(nz[-1])
            first_nz_ts = pd.Timestamp(ts[first_i])
            last_nz_ts = pd.Timestamp(ts[last_i])
        else:
            first_i = None
            last_i = None
            first_nz_ts = pd.NaT
            last_nz_ts = pd.NaT

        zero_share = float(is_zero.mean()) if n else np.nan
        lz = longest_zero_run(is_zero)
        final_cum = float(cum[-1]) if n else np.nan

        activity_rows.append(
            {
                "agent_id": agent_id,
                "side": side,
                "first_nonzero_ts": first_nz_ts,
                "last_nonzero_ts": last_nz_ts,
                "zero_bar_share": zero_share,
                "longest_zero_run_bars": lz,
                "final_cum_ot_pnl": final_cum,
                "n_bars": n,
            }
        )
        agent_meta[agent_id] = {
            "side": side,
            "path": p,
            "first_nonzero_ts": first_nz_ts,
            "zero_bar_share": zero_share,
            "final_cum_ot_pnl": final_cum,
        }

        # --- summary: from first nonzero through END (includes later zeros) ---
        # NOT restricted to active bars only; see docs/METHODOLOGY.md
        if first_i is not None:
            seg = bp[first_i:]
            seg = seg[np.isfinite(seg)]
            mean_ = float(seg.mean()) if seg.size else np.nan
            std_ = float(seg.std(ddof=1)) if seg.size > 1 else np.nan
            # Fisher skew / excess kurtosis via pandas
            s = pd.Series(seg)
            skew_ = float(s.skew()) if seg.size > 2 else np.nan
            kurt_ = float(s.kurt()) if seg.size > 3 else np.nan  # excess kurtosis
            if std_ and std_ > 0 and np.isfinite(bars_per_year):
                sharpe = mean_ / std_ * np.sqrt(bars_per_year)
            else:
                sharpe = np.nan
            n_seg = int(seg.size)
        else:
            mean_ = std_ = skew_ = kurt_ = sharpe = np.nan
            n_seg = 0

        summary_rows.append(
            {
                "agent_id": agent_id,
                "side": side,
                "first_nonzero_ts": first_nz_ts,
                "n_bars_valid_segment": n_seg,
                "bar_pnl_mean": mean_,
                "bar_pnl_std": std_,
                "bar_pnl_skew": skew_,
                "bar_pnl_kurtosis_excess": kurt_,
                "sharpe_simple": sharpe,
                "bars_per_year_est": bars_per_year,
                "final_cum_ot_pnl": final_cum,
                "zero_bar_share_full": zero_share,
            }
        )

        # --- zero calendar contribution ---
        # use baseline day keys; if timestamps mismatch, still group this agent's own days
        day = pd.Series(ts).dt.floor("D")
        tmp = pd.DataFrame({"day": day, "is_zero": is_zero})
        g = tmp.groupby("day", sort=False)
        zero_share_by_day = g["is_zero"].mean()
        all_zero_by_day = g["is_zero"].all()
        for d, zs in zero_share_by_day.items():
            key = pd.Timestamp(d).date()
            if key not in day_sum_zero:
                day_sum_zero[key] = 0.0
                day_n_all_zero[key] = 0
                day_n_agents[key] = 0
                day_n_bars.setdefault(key, int((day == d).sum()))
            day_sum_zero[key] += float(zs)
            day_n_agents[key] += 1
            if bool(all_zero_by_day.loc[d]):
                day_n_all_zero[key] += 1

        # free
        del df, ts, ts_ns, price, cum, bp, is_zero

    # ---------- write tables ----------
    inv.to_csv(out_dir / "inventory.csv", index=False)

    align_lines.append("")
    align_lines.append("SUMMARY")
    align_lines.append(f"n_agents_checked={len(paths)}")
    align_lines.append(f"timestamp_mismatches={ts_mismatch}")
    align_lines.append(f"price_mismatches_vs_baseline={price_mismatch}")
    align_lines.append(
        f"all_timestamps_identical={'YES' if ts_mismatch == 0 else 'NO'}"
    )
    align_lines.append(
        f"all_prices_identical_to_baseline={'YES' if price_mismatch == 0 else 'NO'}"
    )
    (time_dir / "align_check.txt").write_text("\n".join(align_lines) + "\n", encoding="utf-8")

    if gap_summary is not None:
        gap_summary.to_csv(time_dir / "gap_summary.csv", index=False)
    if gap_by_wh is not None:
        gap_by_wh.to_csv(time_dir / "gap_by_weekday_hour.csv", index=False)
    else:
        pd.DataFrame(columns=["weekday", "hour", "n_long_gaps"]).to_csv(
            time_dir / "gap_by_weekday_hour.csv", index=False
        )

    pd.DataFrame(missing_rows).to_csv(feat_raw / "missing_outliers.csv", index=False)
    act = pd.DataFrame(activity_rows)
    act.to_csv(time_raw / "agent_activity.csv", index=False)
    pd.DataFrame(summary_rows).to_csv(feat_raw / "eda_light_summary.csv", index=False)

    # zero_calendar
    zc_rows = []
    for key in sorted(day_sum_zero.keys()):
        na = day_n_agents.get(key, 0)
        po = day_price_open.get(key, np.nan)
        pc = day_price_close.get(key, np.nan)
        ret = (pc / po - 1.0) if (po and np.isfinite(po) and np.isfinite(pc) and po != 0) else np.nan
        zc_rows.append(
            {
                "date": key.isoformat(),
                "n_bars": day_n_bars.get(key, np.nan),
                "n_agents": na,
                "mean_zero_share_across_agents": (day_sum_zero[key] / na) if na else np.nan,
                "n_agents_all_zero_that_day": day_n_all_zero.get(key, 0),
                "frac_agents_all_zero": (day_n_all_zero.get(key, 0) / na) if na else np.nan,
                "price_open": po,
                "price_close": pc,
                "price_ret": ret,
            }
        )
    zc = pd.DataFrame(zc_rows)
    zc.to_csv(time_raw / "zero_calendar.csv", index=False)

    # ---------- plots ----------
    # 1) Δt distribution (baseline)
    if base_ts_ns is not None:
        dt_sec = np.diff(base_ts_ns) / 1e9
        fig, axes = plt.subplots(1, 2, figsize=(11, 4))
        # clip for readability of bulk
        clip = np.clip(dt_sec, 0, np.quantile(dt_sec, 0.99))
        axes[0].hist(clip, bins=80, color="#2f4f6f", alpha=0.9)
        axes[0].set_title("Δt distribution (clipped at p99)")
        axes[0].set_xlabel("seconds")
        axes[0].set_ylabel("count")
        # long gaps only
        long_dt = dt_sec[dt_sec > LONG_GAP_SEC]
        if long_dt.size:
            axes[1].hist(np.log10(long_dt / 60.0), bins=60, color="#8b4513", alpha=0.9)
            axes[1].set_title("Long gaps (>5min), log10(minutes)")
            axes[1].set_xlabel("log10(minutes)")
        else:
            axes[1].text(0.5, 0.5, "no gaps >5min", ha="center")
            axes[1].set_axis_off()
        fig.tight_layout()
        fig.savefig(time_figs / "fig_dt_gaps.png", dpi=120)
        plt.close(fig)

    # 2) zero-share cross-section
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(act["zero_bar_share"].dropna(), bins=30, color="#3d5a40", alpha=0.9)
    ax.set_title("Cross-section: zero_bar_share by agent")
    ax.set_xlabel("zero_bar_share")
    ax.set_ylabel("n_agents")
    fig.tight_layout()
    fig.savefig(time_figs / "fig_zero_share_hist.png", dpi=120)
    plt.close(fig)

    # 3) zero calendar: mean zero share + n all-zero
    if len(zc):
        fig, ax1 = plt.subplots(figsize=(11, 4))
        x = pd.to_datetime(zc["date"])
        ax1.plot(x, zc["mean_zero_share_across_agents"], color="#2f4f6f", lw=0.8, label="mean zero share")
        ax1.set_ylabel("mean_zero_share_across_agents")
        ax1.set_ylim(0, 1.05)
        ax2 = ax1.twinx()
        ax2.plot(x, zc["n_agents_all_zero_that_day"], color="#c45c26", lw=0.7, alpha=0.8, label="n all-zero")
        ax2.set_ylabel("n_agents_all_zero_that_day")
        ax1.set_title("Daily zero activity (cross-agent)")
        fig.tight_layout()
        fig.savefig(time_figs / "fig_zero_calendar.png", dpi=120)
        plt.close(fig)

    # 4) pick 4 representative agents and plot cum_ot_pnl
    # Prefer distinct agents per role; on collision take the next candidate.
    def _first_unused(ordered_ids, seen: set) -> str | None:
        for aid in ordered_ids:
            if aid not in seen:
                return aid
        return None

    seen: set[str] = set()
    pick_list: list[tuple[str, str]] = []
    valid = act.dropna(subset=["first_nonzero_ts"])
    role_orders = [
        (
            "earliest_active",
            valid.sort_values("first_nonzero_ts")["agent_id"].tolist() if len(valid) else [],
        ),
        (
            "latest_active",
            valid.sort_values("first_nonzero_ts", ascending=False)["agent_id"].tolist()
            if len(valid)
            else [],
        ),
        (
            "high_zero_share",
            act.sort_values("zero_bar_share", ascending=False)["agent_id"].tolist(),
        ),
        (
            "high_final_pnl",
            act.sort_values("final_cum_ot_pnl", ascending=False)["agent_id"].tolist(),
        ),
    ]
    for label, ordered in role_orders:
        aid = _first_unused(ordered, seen)
        if aid is not None:
            seen.add(aid)
            pick_list.append((label, aid))
    if len(pick_list) < 4:
        for aid in act.sort_values(
            "final_cum_ot_pnl", key=lambda s: s.abs(), ascending=False
        )["agent_id"]:
            if aid not in seen:
                pick_list.append((f"abs_pnl_{len(pick_list)}", aid))
                seen.add(aid)
            if len(pick_list) >= 4:
                break

    fig, ax = plt.subplots(figsize=(11, 5))
    for label, aid in pick_list:
        p = agent_meta[aid]["path"]
        d = load_cols(p)
        ax.plot(d["timestamp"], d["cum_ot_pnl"], lw=0.9, label=f"{label}:{aid[:8]}")
        del d
    ax.legend(fontsize=8)
    ax.set_title("cum_ot_pnl — representative agents")
    ax.set_xlabel("timestamp")
    ax.set_ylabel("cum_ot_pnl")
    fig.tight_layout()
    fig.savefig(feat_figs / "fig_cum_ot_pnl_reps.png", dpi=120)
    plt.close(fig)

    # write pick note into align or small sidecar
    (feat_dir / "plot_agent_picks.txt").write_text(
        "\n".join(f"{lab}\t{aid}" for lab, aid in pick_list) + "\n",
        encoding="utf-8",
    )

    print("DONE")
    print(f"timestamp_mismatches={ts_mismatch} price_mismatches={price_mismatch}")
    print(f"median_dt_sec={median_dt_sec} bars_per_year_est={bars_per_year}")
    # quick zero conclusions
    if len(zc):
        frac_all = (zc["n_agents_all_zero_that_day"] == zc["n_agents"]).mean()
        print(f"frac_days_all_agents_all_zero={frac_all:.4f}")
        print(
            f"mean_daily_mean_zero_share={zc['mean_zero_share_across_agents'].mean():.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
