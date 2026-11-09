"""
Hold-spell vs market.

For every agent: drop flat (no price-move) time; stitch hold windows; sample
spells and compare in-spell agent PnL to same-side dead-hold (±sleep_size).

Price boundary is aligned with bar_pnl: both use P_before (bar before spell
start) → P_end, so a constant ±4 hold matches agent exactly.

No opposite-sign overlay (no sleep-long on short agents). Example figures are
PnL-only (no left market column).

Default output: outputs_eda_light/hold_spell_vs_market/ (local only)
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
FNAME_RE = re.compile(r"pnl_[^_]+_\d+_\d+_([0-9A-Fa-f]+)_(long|short)\.parquet")
N_EXAMPLE_SPELLS = 4


def parse_hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def load_frame(fp: Path) -> pd.DataFrame:
    df = pd.read_parquet(fp)
    if "timestamp" not in df.columns:
        df = df.reset_index()
        if df.columns[0] != "timestamp":
            df = df.rename(columns={df.columns[0]: "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.set_index("timestamp").sort_index()


def with_position(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["price", "cum_ot_pnl"]].astype(float).copy()
    dpx = out["price"].diff()
    dpnl = out["cum_ot_pnl"].diff()
    pos = pd.Series(np.nan, index=out.index)
    moved = dpx.ne(0) & dpx.notna()
    pos.loc[moved] = (dpnl[moved] / dpx[moved]).round(6)
    out["pos"] = pos.ffill().fillna(0.0)
    out["dpx"] = dpx.fillna(0.0)
    out["bar_pnl"] = dpnl.fillna(0.0)
    return out


def spells(df: pd.DataFrame) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Hold runs on price-move bars only (observational cut)."""
    moved = df["dpx"].ne(0)
    pos_m = df.loc[moved, "pos"]
    on = pos_m.to_numpy() != 0
    idx = pos_m.index
    out: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    i, n = 0, len(on)
    while i < n:
        if not on[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and on[j + 1]:
            j += 1
        out.append((idx[i], idx[j]))
        i = j + 1
    return out


def pick_example_spells(
    rows: list[tuple[pd.Timestamp, pd.Timestamp]], k: int
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    if not rows:
        return []
    if len(rows) <= k:
        return rows
    idxs = np.linspace(0, len(rows) - 1, k, dtype=int)
    return [rows[i] for i in idxs]


def stitch_spells(df: pd.DataFrame, spell_list: list) -> pd.DataFrame:
    parts = [df.loc[a:b] for a, b in spell_list]
    if not parts:
        return df.iloc[:0].copy()
    return pd.concat(parts)


def price_before(df: pd.DataFrame, a: pd.Timestamp) -> float:
    """Price on the bar immediately before spell start (aligns with bar_pnl)."""
    loc = df.index.get_loc(a)
    if isinstance(loc, slice):
        loc = loc.start
    elif isinstance(loc, np.ndarray):
        loc = int(np.flatnonzero(loc)[0])
    loc = int(loc)
    if loc <= 0:
        return float(df["price"].iloc[0])
    return float(df["price"].iloc[loc - 1])


def aligned_deadhold_path(
    df: pd.DataFrame, a: pd.Timestamp, b: pd.Timestamp, size: float
) -> pd.Series:
    """Dead-hold PnL path on [a, b] using P_before → price_t (same as Σ bar_pnl if pos≡size)."""
    hold = df.loc[a:b]
    p0 = price_before(df, a)
    return size * (hold["price"] - p0)


def aligned_deadhold_pnl(
    df: pd.DataFrame, a: pd.Timestamp, b: pd.Timestamp, size: float
) -> float:
    hold = df.loc[a:b]
    p0 = price_before(df, a)
    return float(size * (float(hold["price"].iloc[-1]) - p0))


def plot_stitched(fig_dir: Path, aid: str, side: str, active: pd.DataFrame) -> None:
    if active.empty:
        return
    t = np.arange(len(active))
    cum = active["bar_pnl"].cumsum()
    fig, ax1 = plt.subplots(figsize=(11, 4.2))
    ax1.plot(t, active["price"].to_numpy(), color="#334155", lw=0.9, label="market (in-spell bars)")
    ax1.set_ylabel("price")
    ax1.set_xlabel("bar index inside holds (flat time removed)")
    ax2 = ax1.twinx()
    ax2.plot(t, cum.to_numpy(), color="#b45309", lw=1.1, label="agent cum PnL (in-spell)")
    ax2.set_ylabel("cum PnL ($)")
    ax1.set_title(f"{aid} ({side}) — stitched hold windows  n={len(active)}")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_dir / f"{aid}_stitched_hold.png", dpi=120)
    plt.close(fig)


def plot_example_spells(
    fig_dir: Path,
    aid: str,
    side: str,
    df: pd.DataFrame,
    examples: list[tuple[pd.Timestamp, pd.Timestamp]],
    sleep_size: float,
) -> None:
    """PnL-only panels: agent vs same-side dead-hold (boundary-aligned)."""
    if not examples:
        return
    n = len(examples)
    signed = sleep_size if side == "long" else -sleep_size
    fig, axes = plt.subplots(n, 1, figsize=(10, 2.4 * n), sharex=False)
    axes = np.atleast_1d(axes)
    for r, (a, b) in enumerate(examples):
        hold = df.loc[a:b]
        ax = axes[r]
        agent_path = hold["bar_pnl"].cumsum()
        dead_path = aligned_deadhold_path(df, a, b, signed)
        ax.plot(hold.index, agent_path, color="#b45309", lw=1.3, label=f"agent ({side})")
        ax.plot(
            hold.index,
            dead_path,
            color="#1d4ed8",
            lw=1.2,
            ls="--",
            label=f"same-side dead-hold {signed:+.0f}",
        )
        ax.axhline(0, color="#cbd5e1", lw=0.6)
        ax.set_ylabel("PnL ($)")
        ax.set_title(
            f"{a:%Y-%m-%d %H:%M} → {b:%H:%M}  |  "
            f"agent {agent_path.iloc[-1]:+.1f}  vs  dead-hold {dead_path.iloc[-1]:+.1f}",
            fontsize=9,
            loc="left",
        )
        ax.legend(fontsize=7, loc="best")
    fig.suptitle(
        f"{aid} ({side}) — example holds: agent vs same-side dead-hold (aligned)",
        y=1.01,
    )
    fig.tight_layout()
    fig.savefig(fig_dir / f"{aid}_example_spells.png", dpi=120, bbox_inches="tight")
    plt.close(fig)


def summarize_agent(
    aid: str,
    side: str,
    df: pd.DataFrame,
    spell_list: list,
    sleep_size: float,
) -> dict:
    active = stitch_spells(df, spell_list)
    agent_pnl = float(active["bar_pnl"].sum()) if len(active) else 0.0
    signed = sleep_size if side == "long" else -sleep_size
    same_side_sum = 0.0
    n_beat = 0
    for a, b in spell_list:
        agent_spell = float(df.loc[a:b, "bar_pnl"].sum())
        dead = aligned_deadhold_pnl(df, a, b, signed)
        same_side_sum += dead
        if agent_spell > dead:
            n_beat += 1
    n_sp = len(spell_list)
    return dict(
        agent=aid,
        side=side,
        n_spells=n_sp,
        n_in_spell_bars=int(len(active)),
        agent_pnl_in_spells=agent_pnl,
        same_side_deadhold_sum=same_side_sum,
        agent_minus_same_side=agent_pnl - same_side_sum,
        beat_same_side_deadhold=agent_pnl > same_side_sum,
        share_spells_beating_same_side=(n_beat / n_sp if n_sp else np.nan),
        first_spell=spell_list[0][0] if spell_list else pd.NaT,
        last_spell=spell_list[-1][1] if spell_list else pd.NaT,
        final_cum_ot_pnl=float(df["cum_ot_pnl"].iloc[-1]),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "data",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "outputs_eda_light" / "hold_spell_vs_market",
    )
    ap.add_argument("--session-start", required=True, help="HH:MM inclusive (supplied by the data owner)")
    ap.add_argument("--session-end", required=True, help="HH:MM inclusive (supplied by the data owner)")
    ap.add_argument(
        "--sleep-size",
        type=float,
        default=4.0,
        help="contract size for same-side dead-hold (the agent dumps use a fixed ±4)",
    )
    ap.add_argument(
        "--no-figs",
        action="store_true",
        help="write CSV/README only (no per-agent PNGs)",
    )
    args = ap.parse_args()

    data_dir: Path = args.data_dir
    out: Path = args.out_dir
    fig_dir = out / "figs"
    sleep_size = float(args.sleep_size)

    raw_dir = out / "raw"
    out.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(data_dir.glob("*.parquet"))
    assert files, f"no parquet under {data_dir}"

    rows: list[dict] = []
    for i, fp in enumerate(files, 1):
        m = FNAME_RE.match(fp.name)
        assert m, fp.name
        aid, side = m.group(1)[:6], m.group(2)
        df = with_position(load_frame(fp))
        sp = spells(df)
        active = stitch_spells(df, sp)
        if not args.no_figs:
            plot_stitched(fig_dir, aid, side, active)
            plot_example_spells(
                fig_dir,
                aid,
                side,
                df,
                pick_example_spells(sp, N_EXAMPLE_SPELLS),
                sleep_size,
            )
        rows.append(summarize_agent(aid, side, df, sp, sleep_size))
        print(f"[{i}/{len(files)}] {aid} ({side}) spells={len(sp)} bars={len(active)}", flush=True)

    S = pd.DataFrame(rows).sort_values(
        ["beat_same_side_deadhold", "agent_minus_same_side"],
        ascending=[False, False],
    )
    csv_name = f"hold_spell_vs_passive_all{len(S)}.csv"
    S.to_csv(raw_dir / csv_name, index=False)
    if len(S) == 70:
        S.to_csv(raw_dir / "sleep_vs_agent_all70.csv", index=False)

    n_beat = int(S["beat_same_side_deadhold"].sum())
    g = S["agent_minus_same_side"]
    summ_rows = [
        {"metric": "n_agents", "value": len(S)},
        {"metric": "n_beat_same_side_deadhold", "value": n_beat},
        {"metric": "frac_beat_same_side_deadhold", "value": float(n_beat / len(S))},
        {"metric": "gap_mean", "value": float(g.mean())},
        {"metric": "gap_median", "value": float(g.median())},
    ]
    for s, sub in S.groupby("side"):
        summ_rows.append({"metric": f"n_{s}", "value": len(sub)})
        summ_rows.append(
            {"metric": f"gap_mean_{s}", "value": float(sub["agent_minus_same_side"].mean())}
        )
        summ_rows.append(
            {
                "metric": f"frac_beat_{s}",
                "value": float(sub["beat_same_side_deadhold"].mean()),
            }
        )
    pd.DataFrame(summ_rows).to_csv(out / "hold_spell_summary.csv", index=False)

    readme = [
        "# hold_spell_vs_market",
        "",
        f"Data: `{data_dir.name}`  session {args.session_start}–{args.session_end}",
        "",
        "Strip flat (no price-move) time. Compare in-spell agent PnL to **same-side**",
        f"dead-hold (±{sleep_size:g}). Long agents vs +{sleep_size:g}; short vs −{sleep_size:g}.",
        "No opposite-sign benchmark.",
        "",
        "## Result (boundary-aligned)",
        "",
        "Dead-hold uses the same price boundary as `bar_pnl` (bar *before* spell start → spell end),",
        f"so a constant ±{sleep_size:g} position matches the agent **exactly** while in spell.",
        f"Therefore `agent_minus_same_side` is **identically 0** for all agents here "
        f"({n_beat}/{len(S)} beat dead-hold; gap mean={float(g.mean()):.4g}).",
        "Same-side dead-hold is a sanity check of the alignment, **not** a selection signal.",
        "",
        f"Agents: **{len(S)}** / {len(files)}",
        "",
        "## Human layer",
        "- `hold_spell_summary.csv` — one-screen metrics (expect gap≈0 after alignment)",
        (
            "- `figs/{id}_example_spells.png` / `_stitched_hold.png` — per-agent detail"
            if not args.no_figs
            else "- (no per-agent figs; ran with `--no-figs`)"
        ),
        "",
        "## Raw",
        f"- `raw/{csv_name}` — one row per agent",
        "",
        "## Re-run",
        "```bash",
        f".venv/bin/python eda_hold_spell_vs_market.py --data-dir {data_dir.name} "
        f"--out-dir {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out} "
        f"--session-start {args.session_start} --session-end {args.session_end}",
        "```",
        "",
    ]
    (out / "README.md").write_text("\n".join([x for x in readme if x is not None]), encoding="utf-8")
    print(f"beat same-side dead-hold {n_beat}/{len(S)}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
