"""
Daily session PnL per agent → Sharpe / max drawdown / entry frequency,
small-grid cum PnL overview + stacked per-agent cum PnL with market twin axis,
cohort batch table, and year-over-year persistence.

Session Mon–Fri 11:35–13:30 → sum bar_pnl per day. Each agent's stats start at its
first active day (from_first).

Default (--drop-zero-days off): idle session days stay as 0 in the daily series;
Sharpe = mean/std × √252 including those zeros.

With --drop-zero-days: remove every day whose session PnL is exactly 0, then
Sharpe/DD/plots use only days with nonzero PnL (still × √252 on that thinner
series). Default out-dir becomes outputs_eda_light/sharpe_dd_active_days/.
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
OUT = ROOT / "outputs_eda_light" / "sharpe_dd"
FNAME_RE = re.compile(
    r"pnl_(?:Mini|Nasdaq)_\d+_\d+_([0-9A-Fa-f]+)_(long|short)\.parquet"
)
TOP_K = 10


def parse_hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def load_daily(
    data_dir: Path, session_start: int, session_end: int
) -> tuple[pd.DataFrame, pd.Series, dict[str, str], dict[str, dict]]:
    """Position = round(ΔPnL / Δprice). Every agent is only 0 or ±4.

    A nonzero PnL bar is mark-to-market while holding. An entry is the bar
    where position leaves 0. Round-trip PnL is cum at the matching exit
    minus cum on the bar before entry.

    Also returns session last `price` per day (shared across agents).
    """
    daily: dict[str, pd.Series] = {}
    sides: dict[str, str] = {}
    ops: dict[str, dict] = {}
    market_daily: pd.Series | None = None
    for fp in sorted(data_dir.glob("*.parquet")):
        m = FNAME_RE.match(fp.name)
        assert m, fp.name
        aid, side = m.group(1)[:6], m.group(2)
        sides[aid] = side
        df = pd.read_parquet(fp)
        if "timestamp" not in df.columns:
            df = df.reset_index().rename(columns={"index": "timestamp"})
            df = df.rename(columns={df.columns[0]: "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        dpx = df["price"].astype(float).diff()
        dpnl = df["cum_ot_pnl"].astype(float).diff()
        pos = pd.Series(np.nan, index=df.index)
        moved = dpx != 0
        pos.loc[moved] = (dpnl[moved] / dpx[moved]).round(6)
        pos = pos.ffill().fillna(0.0)
        prev = pos.shift(fill_value=0.0)
        ent = ((prev == 0) & (pos != 0)).to_numpy()
        ex = ((prev != 0) & (pos == 0)).to_numpy()
        ei, xi = np.flatnonzero(ent), np.flatnonzero(ex)
        n = min(len(ei), len(xi))
        cum = df["cum_ot_pnl"].to_numpy(dtype=float)
        before = np.where(ei[:n] > 0, cum[ei[:n] - 1], 0.0)
        trip = cum[xi[:n]] - before
        # Entry calendar days (0 → ±4); used as markers on cum-PnL / market panels
        entry_dates = (
            pd.to_datetime(df["timestamp"].iloc[ei]).dt.floor("D").drop_duplicates().to_numpy()
            if len(ei)
            else np.array([], dtype="datetime64[ns]")
        )
        ops[aid] = dict(
            n_entries=int(n),
            trade_hit_rate=float((trip > 0).mean()) if n else np.nan,
            entry_dates=entry_dates,
        )

        tod = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
        mask = (df["timestamp"].dt.dayofweek < 5) & (tod >= session_start) & (tod <= session_end)
        s = df.loc[mask].copy()
        s["date"] = s["timestamp"].dt.floor("D")
        s["bar_pnl"] = s.groupby("date", sort=False)["cum_ot_pnl"].diff().fillna(0.0)
        ops[aid]["active_bars"] = int((s["bar_pnl"] != 0).sum())
        daily[aid] = s.groupby("date", sort=True)["bar_pnl"].sum()
        if market_daily is None:
            market_daily = s.groupby("date", sort=True)["price"].last().astype(float)
    assert market_daily is not None
    M = pd.DataFrame(daily).sort_index().fillna(0.0)
    market_daily = market_daily.reindex(M.index).ffill().bfill()
    return M, market_daily, sides, ops


def from_first(x: pd.Series) -> pd.Series:
    nz = x.to_numpy().nonzero()[0]
    return x.iloc[nz[0]:] if len(nz) else x.iloc[:0]


def drop_zero_days(x: pd.Series) -> pd.Series:
    """Keep only days with nonzero session PnL (after from_first)."""
    return x.loc[x != 0]


def agent_daily(x: pd.Series, drop_zeros: bool) -> pd.Series:
    x = from_first(x)
    return drop_zero_days(x) if drop_zeros else x


def sharpe(x: pd.Series) -> float:
    sd = x.std()
    return float(x.mean() / sd * np.sqrt(252)) if sd > 0 and len(x) > 1 else np.nan


def max_dd(x: pd.Series) -> float:
    if len(x) == 0:
        return np.nan
    cum = x.cumsum()
    return float((cum.cummax() - cum).max())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DATA)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--session-start", default="11:35")
    ap.add_argument("--session-end", default="13:30")
    ap.add_argument(
        "--drop-zero-days",
        action="store_true",
        help="Drop session days with PnL==0 before Sharpe/DD/plots (active days only).",
    )
    args = ap.parse_args()
    drop_zeros = bool(args.drop_zero_days)
    out: Path = args.out_dir or (
        ROOT / "outputs_eda_light" / ("sharpe_dd_active_days" if drop_zeros else "sharpe_dd")
    )
    figs, raw = out / "figs", out / "raw"
    for d in (out, figs, raw):
        d.mkdir(parents=True, exist_ok=True)
    session_start = parse_hhmm(args.session_start)
    session_end = parse_hhmm(args.session_end)
    M, market, sides, ops = load_daily(args.data_dir, session_start, session_end)

    mode_label = (
        "ACTIVE DAYS ONLY — every day with session PnL==0 removed"
        if drop_zeros
        else "INCL. IDLE DAYS — session days with PnL==0 kept as 0"
    )
    sharpe_note = (
        "Sharpe = mean/std of nonzero daily session PnL × √252 "
        "(idle days excluded from mean and std)"
        if drop_zeros
        else "Sharpe = mean/std of daily session PnL × √252 "
        "(idle days after first trade stay as 0 and dilute mean/std)"
    )

    rows = []
    for a in M.columns:
        x = agent_daily(M[a], drop_zeros)
        if len(x) == 0:
            continue
        span_days = (x.index[-1] - x.index[0]).days
        years = max(span_days / 365.25, 1e-9)
        n_active_days = int((x != 0).sum()) if not drop_zeros else len(x)
        rows.append(
            dict(
                agent=a,
                side=sides[a],
                first_day=x.index[0].date(),
                years=round(years, 2),
                n_days_in_series=len(x),
                n_active_days=n_active_days,
                final_pnl=x.sum(),
                sharpe=sharpe(x),
                max_dd=max_dd(x),
                calmar=x.sum() / years / max_dd(x) if max_dd(x) > 0 else np.nan,
                n_entries=ops[a]["n_entries"],
                entries_per_year=ops[a]["n_entries"] / years,
                trade_hit_rate=ops[a]["trade_hit_rate"],
                active_bars=ops[a]["active_bars"],
                bars_per_entry=ops[a]["active_bars"] / max(ops[a]["n_entries"], 1),
                day_hit_rate=(x > 0).sum() / max(len(x) if drop_zeros else (x != 0).sum(), 1),
            )
        )
    T = pd.DataFrame(rows).set_index("agent").sort_values("sharpe", ascending=False)
    T.round(3).to_csv(raw / "agent_sharpe_dd.csv")

    top_sharpe = set(T.head(TOP_K).index)
    low_dd = set(T.nsmallest(TOP_K, "max_dd").index)
    corr_s_dd = T[["sharpe", "max_dd"]].corr(method="spearman").iloc[0, 1]
    corr_s_freq = T[["sharpe", "entries_per_year"]].corr(method="spearman").iloc[0, 1]
    corr_dd_freq = T[["max_dd", "entries_per_year"]].corr(method="spearman").iloc[0, 1]

    t_end = M.index.max()
    # cum PnL on the same day filter used for Sharpe (from_first ± drop zeros)
    paths = {a: agent_daily(M[a], drop_zeros).cumsum() for a in T.index}

    def _pad_lim(lo: float, hi: float, frac: float = 0.05) -> tuple[float, float]:
        pad = frac * (hi - lo) if hi > lo else 1.0
        return lo - pad, hi + pad

    def draw_agent_market_panel(
        ax,
        a: str,
        *,
        pnl_ylim: tuple[float, float],
        title: str,
        ylabel: str | None = None,
        show_price_axis: bool = False,
    ) -> None:
        """Same dates for agent + market; left=PnL $, right=market price.

        Orange dots = entry days (position 0 → ±4), plotted on both the cum-PnL
        path and the market path so you can see whether entries sit on 'good' market.
        """
        p = paths[a]
        t0 = p.index[0]
        mseg = market.loc[(market.index >= t0) & (market.index <= t_end)]
        idx = p.index.intersection(mseg.index)
        p_al = p.reindex(idx)
        m_al = mseg.reindex(idx)
        color = "tab:blue" if sides[a] == "long" else "tab:red"
        ax.plot(idx, p_al.to_numpy(), lw=0.85, color=color, zorder=2)
        ax.set_xlim(idx[0], idx[-1])
        ax.set_ylim(pnl_ylim)
        ax.axhline(0, color="#cbd5e1", lw=0.4, zorder=0)
        ax2 = ax.twinx()
        ax2.plot(idx, m_al.to_numpy(), color="#334155", lw=0.55, alpha=0.9, zorder=1)
        ax2.set_ylim(_pad_lim(float(m_al.min()), float(m_al.max())))

        # Mark entry days (no date labels — just dots)
        ed = pd.DatetimeIndex(ops[a].get("entry_dates", []))
        ed = ed[(ed >= idx[0]) & (ed <= idx[-1])]
        if len(ed):
            # snap to dates present on the panel index
            ed = ed.intersection(idx)
            if len(ed):
                ax.scatter(
                    ed,
                    p_al.reindex(ed).to_numpy(),
                    s=36,
                    c="#f59e0b",
                    edgecolors="#7c2d12",
                    linewidths=0.4,
                    marker="o",
                    zorder=5,
                    alpha=0.95,
                )
                ax2.scatter(
                    ed,
                    m_al.reindex(ed).to_numpy(),
                    s=36,
                    c="#f59e0b",
                    edgecolors="#7c2d12",
                    linewidths=0.4,
                    marker="o",
                    zorder=5,
                    alpha=0.95,
                )

        if show_price_axis:
            ax2.tick_params(labelsize=5, colors="#334155")
            ax2.set_ylabel("px", fontsize=6, color="#334155")
        else:
            ax2.tick_params(labelright=False, length=0)
        ax.set_title(title, fontsize=6.5)
        ax.tick_params(labelsize=5)
        if ylabel:
            ax.set_ylabel(ylabel, fontsize=7)

    n = len(T)

    # Small-grid overview (PnL only) — keep alongside the market stacked view
    ncol = 10
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(26, 2.3 * nrow), sharex=True)
    axes_flat = np.atleast_1d(axes).ravel()
    for ax, a in zip(axes_flat, T.index):
        p = paths[a]
        ax.plot(
            p.index,
            p.to_numpy(),
            lw=0.7,
            color="tab:blue" if sides[a] == "long" else "tab:red",
        )
        ax.set_title(f"{a} {sides[a][0].upper()} SR={T.loc[a, 'sharpe']:.2f}", fontsize=7)
        ax.tick_params(labelsize=5)
    for ax in axes_flat[n:]:
        ax.axis("off")
    fig.suptitle(
        f"Cumulative session PnL, ordered by Sharpe (blue=long, red=short) | {mode_label}"
    )
    fig.tight_layout()
    fig.savefig(figs / "fig_cum_pnl_all70.png", dpi=110)
    plt.close()

    # Tall stacked figure: one wide row per agent + market twin axis
    row_h = 1.65
    fig_w = 28
    fig, axes = plt.subplots(
        n,
        1,
        figsize=(fig_w, row_h * n + 1.2),
        sharex=False,
        squeeze=False,
    )
    for i, a in enumerate(T.index):
        ax = axes[i, 0]
        p = paths[a]
        ylim = _pad_lim(float(p.min()), float(p.max()), 0.08)
        draw_agent_market_panel(
            ax,
            a,
            pnl_ylim=ylim,
            title=(
                f"{a}  {sides[a]}  SR={T.loc[a, 'sharpe']:.2f}  "
                f"maxDD={T.loc[a, 'max_dd']:.0f}  entries/yr={T.loc[a, 'entries_per_year']:.1f}  "
                f"from {T.loc[a, 'first_day']}  n_days={int(T.loc[a, 'n_days_in_series'])}"
            ),
            ylabel="PnL $",
            show_price_axis=True,
        )
        ax.tick_params(labelsize=7)
        ax.title.set_fontsize(9)
    fig.suptitle(
        f"fig_cum_pnl_all70_stacked — one row per agent (wide time axis) | {mode_label}\n"
        f"Left: cumsum daily session PnL (own $ scale per row). Right: market price. "
        f"Blue=long, red=short, grey=market. Orange dots=entry days (0→±4). "
        f"Rows ordered by Sharpe (top=highest). {sharpe_note}",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.995))
    fig.savefig(figs / "fig_cum_pnl_all70_stacked.png", dpi=110)
    plt.close()
    for obsolete in (
        figs / "fig_cum_pnl_cohort_zoom.png",
        figs / "fig_cum_pnl_with_market.png",
        figs / "fig_cum_pnl_zoom.png",
        out / "fig_cum_pnl_cohort_zoom.png",
        out / "fig_cum_pnl_with_market.png",
        out / "fig_cum_pnl_zoom.png",
    ):
        if obsolete.exists():
            obsolete.unlink()

    # Start-date cohort membership table (no crowded multi-panel figure)
    N_BATCH = 5
    by_start = T.sort_values("first_day")
    batches = [list(g) for g in np.array_split(by_start.index.to_numpy(), N_BATCH)]
    batch_meta = []
    for r, batch in enumerate(batches):
        batch_sorted = sorted(batch, key=lambda a: T.loc[a, "sharpe"], reverse=True)
        batch_meta.append(
            dict(
                batch=r + 1,
                n=len(batch),
                first_day_min=str(min(pd.Timestamp(T.loc[a, "first_day"]) for a in batch).date()),
                first_day_max=str(max(pd.Timestamp(T.loc[a, "first_day"]) for a in batch).date()),
                agents=",".join(batch_sorted),
            )
        )
    pd.DataFrame(batch_meta).to_csv(out / "cum_pnl_cohort_batches.csv", index=False)

    # Sharpe scatter pair: shared Sharpe y-axis
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4), sharey=True)
    col = T["side"].map({"long": "tab:blue", "short": "tab:red"})
    s_lo, s_hi = float(T["sharpe"].min()), float(T["sharpe"].max())
    s_pad = 0.05 * (s_hi - s_lo) if s_hi > s_lo else 0.1
    axes[0].scatter(T["max_dd"], T["sharpe"], c=col, s=18)
    axes[0].set_xlabel("max drawdown on the same daily series ($)")
    axes[0].set_ylabel("annualized Sharpe (this mode)")
    axes[0].set_title(
        f"LEFT: Sharpe vs MaxDD (Spearman {corr_s_dd:.2f})\n"
        f"Each point = one agent. MaxDD = peak-to-trough of cumsum(daily PnL) under this day filter.",
        fontsize=9,
    )
    axes[1].scatter(T["entries_per_year"], T["sharpe"], c=col, s=18)
    axes[1].set_xlabel("entries / calendar year  (0 → ±4 position)")
    axes[1].set_ylabel("annualized Sharpe (this mode)")
    axes[1].set_title(
        f"RIGHT: Sharpe vs entry frequency (Spearman {corr_s_freq:.2f})\n"
        f"Entries counted on full history; years = calendar span from first→last day in series.",
        fontsize=9,
    )
    for ax in axes:
        ax.set_ylim(s_lo - s_pad, s_hi + s_pad)
    fig.suptitle(
        f"fig_sharpe_vs_dd_freq — cross-section of agents | {mode_label}\n{sharpe_note}",
        fontsize=10,
    )
    fig.tight_layout()
    fig.savefig(figs / "fig_sharpe_vs_dd_freq.png", dpi=130)
    plt.close()

    # Year-over-year persistence (optionally drop zero days inside each calendar year)
    first_year = {
        a: agent_daily(M[a], drop_zeros).index[0].year
        for a in M.columns
        if len(agent_daily(M[a], drop_zeros))
    }
    years = sorted(set(M.index.year))
    yearly = {}
    for y in years:
        seg = M[M.index.year == y]
        yearly[y] = {}
        for a, y0 in first_year.items():
            if y0 >= y:
                continue
            xs = drop_zero_days(seg[a]) if drop_zeros else seg[a]
            if len(xs) > 1 and xs.std() > 0:
                yearly[y][a] = sharpe(xs)
    pers = []
    for y in years[:-1]:
        common = [a for a in yearly[y] if a in yearly[y + 1] and np.isfinite(yearly[y][a]) and np.isfinite(yearly[y + 1][a])]
        if len(common) < 8:
            continue
        s0 = pd.Series({a: yearly[y][a] for a in common})
        s1 = pd.Series({a: yearly[y + 1][a] for a in common})
        pers.append(dict(year=y, n_agents=len(common), spearman_next_year=s0.corr(s1, method="spearman")))
    P = pd.DataFrame(pers)
    P.round(3).to_csv(raw / "sharpe_persistence_yoy.csv", index=False)

    Y = pd.DataFrame(yearly).T.sort_index()
    own = []
    for a in Y.columns:
        s = Y[a].dropna()
        if len(s) < 5:
            continue
        pv, nv = s.iloc[:-1].to_numpy(), s.iloc[1:].to_numpy()
        ok = (s.index[1:].to_numpy() - s.index[:-1].to_numpy()) == 1
        if ok.sum() < 4:
            continue
        own.append(
            dict(
                agent=a,
                side=sides[a],
                n_years=int(len(s)),
                autocorr=float(np.corrcoef(pv[ok], nv[ok])[0, 1]),
            )
        )
    O = pd.DataFrame(own).set_index("agent").sort_values("autocorr") if len(own) else pd.DataFrame()
    if len(O):
        O.round(3).to_csv(raw / "sharpe_autocorr_by_agent.csv")

    # Walk-forward: same day filter on history / next-year series
    bt = []
    min_hist = 60 if drop_zeros else 252  # fewer days once zeros dropped
    for y in years[1:]:
        hist = M[M.index.year < y]
        elig = [
            a
            for a in M.columns
            if len(agent_daily(hist[a], drop_zeros)) >= min_hist
        ]
        if len(elig) < 2 * TOP_K:
            continue
        trail = pd.Series({a: sharpe(agent_daily(hist[a], drop_zeros)) for a in elig})
        picks = trail.nlargest(TOP_K).index
        nxt = M[M.index.year == y]
        # portfolio daily: equal-weight mean across picks on the shared calendar (incl zeros for P&L total)
        bt.append(
            dict(
                year=y,
                n_eligible=len(elig),
                topk_pnl=nxt[picks].sum(axis=1).sum() / TOP_K,
                all_eligible_pnl=nxt[elig].sum(axis=1).sum() / len(elig),
                topk_sharpe=sharpe(
                    agent_daily(nxt[picks].mean(axis=1), drop_zeros)
                    if drop_zeros
                    else nxt[picks].mean(axis=1)
                ),
                all_eligible_sharpe=sharpe(
                    agent_daily(nxt[elig].mean(axis=1), drop_zeros)
                    if drop_zeros
                    else nxt[elig].mean(axis=1)
                ),
            )
        )
    B = pd.DataFrame(bt)
    B.round(3).to_csv(raw / "walkforward_topk_sharpe.csv", index=False)

    summary = [
        f"MODE: {mode_label}",
        sharpe_note,
        f"session={args.session_start}–{args.session_end}  agents={n}  "
        f"long={sum(v == 'long' for v in sides.values())}",
        f"Spearman(Sharpe, MaxDD)={corr_s_dd:.2f}",
        f"Spearman(Sharpe, entries/yr)={corr_s_freq:.2f}",
        f"Spearman(MaxDD, entries/yr)={corr_dd_freq:.2f}",
        f"entries/yr median={T['entries_per_year'].median():.1f} max={T['entries_per_year'].max():.1f}",
        f"days in series median={T['n_days_in_series'].median():.0f}",
        f"nonzero-PnL bars per entry median={T['bars_per_entry'].median():.1f}",
        f"overlap top{TOP_K} Sharpe & lowest{TOP_K} MaxDD = {len(top_sharpe & low_dd)}",
        "",
        "Top10 Sharpe:",
        T.head(TOP_K).round(2).to_string(),
        "",
        "Lowest10 MaxDD:",
        T.nsmallest(TOP_K, "max_dd").round(2).to_string(),
        "",
        "YoY Sharpe rank persistence:",
        P.round(2).to_string(index=False) if len(P) else "(insufficient)",
        f"mean spearman = {P['spearman_next_year'].mean():.2f}" if len(P) else "",
        "",
        (
            f"Own yearly-Sharpe autocorr (n>={5} years): "
            f"median={O['autocorr'].median():.2f}  positive={int((O['autocorr'] > 0).sum())}/{len(O)}"
            if len(O)
            else "Own yearly-Sharpe autocorr: (insufficient)"
        ),
        O.round(2).to_string() if len(O) else "",
        "",
        f"Walk-forward top{TOP_K} trailing Sharpe vs equal-weight eligible (per-agent avg PnL):",
        B.round(2).to_string(index=False) if len(B) else "(insufficient)",
    ]
    if len(B):
        summary.append(
            f"years topk beats all: {(B['topk_pnl'] > B['all_eligible_pnl']).sum()}/{len(B)}; "
            f"mean topk SR={B['topk_sharpe'].mean():.2f} vs all SR={B['all_eligible_sharpe'].mean():.2f}"
        )
    (out / "summary.txt").write_text("\n".join(summary), encoding="utf-8")

    readme = [
        "# sharpe_dd" + ("_active_days" if drop_zeros else ""),
        "",
        f"**Mode:** {mode_label}",
        "",
        sharpe_note,
        "",
        f"Session window: Mon–Fri **{args.session_start}–{args.session_end}** → one daily PnL = sum of 5-min `bar_pnl` in that window.",
        "Stats / plots start at each agent’s first nonzero day (`from_first`).",
        "",
        "## Layout",
        "",
        "- Human: `figs/`, `summary.txt`, `cum_pnl_cohort_batches.csv`",
        "- Raw (agent-level / long tables): `raw/`",
        "",
        "## Figures",
        "",
        f"- **`figs/fig_cum_pnl_all70.png`** — small-grid cum session PnL (no market), ordered by Sharpe.",
        f"- **`figs/fig_cum_pnl_all70_stacked.png`** — one wide row per agent + market twin axis, "
        f"stacked by Sharpe. Left=cum PnL, right=market, orange dots=entries. {mode_label}.",
        f"- **`figs/fig_sharpe_vs_dd_freq.png`** — Sharpe vs max DD / entries/year. {sharpe_note}",
        f"- **`cum_pnl_cohort_batches.csv`** — start-date cohort membership (small).",
        "",
        "## Raw / text",
        "",
        "- **`raw/agent_sharpe_dd.csv`** — primary ranking table (one row per agent).",
        "- **`summary.txt`** — Top/bottom, Spearman, YoY, walk-forward blurb.",
        "- **`raw/sharpe_persistence_yoy.csv`**, **`raw/sharpe_autocorr_by_agent.csv`**, "
        "**`raw/walkforward_topk_sharpe.csv`**.",
        "",
        "## Re-run",
        "```bash",
        (
            ".venv/bin/python eda_sharpe_dd_persistence.py --drop-zero-days"
            if drop_zeros
            else ".venv/bin/python eda_sharpe_dd_persistence.py"
        ),
        "```",
        "",
        "## Contrast",
        (
            "Default folder `outputs_eda_light/sharpe_dd/` keeps idle (PnL=0) days. "
            "This folder drops them."
            if drop_zeros
            else "For the version that **deletes** idle (PnL=0) days, run with `--drop-zero-days` "
            "→ `outputs_eda_light/sharpe_dd_active_days/`."
        ),
        "",
    ]
    (out / "README.md").write_text("\n".join(readme), encoding="utf-8")
    print("\n".join(summary))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
