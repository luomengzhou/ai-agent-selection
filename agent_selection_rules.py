"""
Agent selection rules R1-R6 with yearly walk-forward (pseudo-OOS).
Spec: docs/agent_selection_rules_zh.md sections 1-4.

For each year Y: features use only data <= feature_asof (last session day before Y);
the chosen agents' daily PnL over Y is the OOS path. Benchmarks: all-agent 1/N and
side-matched 50/50 1/N (primary).
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import norm

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "outputs_rules_light"
FNAME_RE = re.compile(r"pnl_[^_]+_\d+_\d+_([0-9A-Fa-f]+)_(long|short)\.parquet")

# ---- "D" parameters (doc leaves them to us) ----
MIN_ENTRIES = 10        # gate: entries for entering the pool
MIN_STATE_DAYS = 20     # R1: min days in opportunity / adverse
RECENT_DAYS = 252       # R2: recent window
MIN_RECENT_TRADES = 5   # R2: min trade days in recent window
MIN_FULL_YEARS = 3      # R3
MIN_ENTRIES_R3 = 20     # R3
N_DAYS_FULL = 756       # R5: days for full weight
TOP_FRAC = 0.2          # top share per side
STRESS_Q = 0.20         # stress quantile
CORR_MIN_DAYS = 252     # R6: min common days
RHO_CUT = 0.7           # R6: cluster at rho >= 0.7
TREND_WINDOWS = (21, 63, 252)


def parse_hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def load(data_dir: Path, s0: int, s1: int):
    """Returns pnl (days x agents), trade (1/0/NaN), sides, market close per session day."""
    pnl, trade, sides = {}, {}, {}
    close = None
    for fp in sorted(data_dir.glob("*.parquet")):
        m = FNAME_RE.match(fp.name)
        assert m, fp.name
        aid, side = m.group(1)[:6], m.group(2)
        sides[aid] = side
        df = pd.read_parquet(fp)
        if "timestamp" not in df.columns:
            df = df.reset_index()
            df = df.rename(columns={df.columns[0]: "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        # diff on the full timeline first, then cut the session
        df["dpx"] = df["price"].astype(float).diff()
        df["dpnl"] = df["cum_ot_pnl"].astype(float).diff()
        tod = df["timestamp"].dt.hour * 60 + df["timestamp"].dt.minute
        s = df[(df["timestamp"].dt.dayofweek < 5) & (tod >= s0) & (tod <= s1)].copy()
        s["date"] = s["timestamp"].dt.floor("D")
        moved = s["dpx"] != 0
        s["pos"] = 0.0
        s.loc[moved, "pos"] = (s.loc[moved, "dpnl"] / s.loc[moved, "dpx"]).round()
        g = s.groupby("date", sort=True)
        pnl[aid] = g["dpnl"].sum()
        has_move = s.assign(m=moved).groupby("date")["m"].any()
        has_pos = s.assign(p=(s["pos"] != 0)).groupby("date")["p"].any()
        t = pd.Series(np.nan, index=has_move.index)
        t[has_move] = 0.0
        t[has_pos] = 1.0
        trade[aid] = t
        if close is None:
            close = g["price"].last().astype(float)
    P = pd.DataFrame(pnl).sort_index().fillna(0.0)
    T = pd.DataFrame(trade).reindex(P.index)
    close = close.reindex(P.index).ffill().bfill()
    return P, T, sides, close


def market_labels(close: pd.Series) -> pd.DataFrame:
    sg = sum(np.sign(close / close.shift(k) - 1) for k in TREND_WINDOWS) / len(TREND_WINDOWS)
    dd = close / close.rolling(252).max() - 1
    # label for decision day d uses previous session day
    return pd.DataFrame({"trend": sg.shift(1), "dd": dd.shift(1)})


def sharpe(x: pd.Series) -> float:
    sd = x.std()
    return float(x.mean() / sd * np.sqrt(252)) if len(x) > 1 and sd > 0 else np.nan


def pctrank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True)


def agent_features(aid, side, pnl, trade, lab, q20, launch, asof):
    """All features for one agent using data <= asof only."""
    x = pnl.loc[launch:asof]
    tr = trade.loc[launch:asof]
    n_days = len(x)
    entries = int((tr == 1).sum())
    f = dict(agent=aid, side=side, launch_date=launch, n_days=n_days, entries=entries)

    # R1
    l = lab.loc[launch:asof]
    ok = tr.notna() & l["trend"].notna() & l["dd"].notna()
    up, down, stress = l["trend"] > 0, l["trend"] < 0, l["dd"] <= q20
    opp, adv = (up, stress) if side == "long" else ((down | stress), up)
    opp, adv = opp & ok, adv & ok
    f["n_opp"], f["n_adv"] = int(opp.sum()), int(adv.sum())
    f["R1"] = np.nan
    if f["n_opp"] >= MIN_STATE_DAYS and f["n_adv"] >= MIN_STATE_DAYS:
        f["R1"] = 0.5 * ((tr[opp] == 1).mean() + (tr[adv] == 0).mean())

    # R2 raw ingredients
    f["perf_gap"] = f["giveback"] = np.nan
    if n_days >= 2 * RECENT_DAYS:
        rec, old = x.iloc[-RECENT_DAYS:], x.iloc[:-RECENT_DAYS]
        if (tr.iloc[-RECENT_DAYS:] == 1).sum() >= MIN_RECENT_TRADES:
            f["perf_gap"] = sharpe(rec) - sharpe(old)
    cum = x.cumsum()
    peak = cum.max()
    if peak > 0:
        f["giveback"] = (peak - cum.iloc[-1]) / peak

    # R3 ingredients
    f["CV"] = f["HHI"] = np.nan
    ent = (tr == 1)
    years = list(range(launch.year + 1, asof.year + 1))
    if len(years) >= MIN_FULL_YEARS and entries >= MIN_ENTRIES_R3:
        cnt = ent.groupby(ent.index.year).sum().reindex(years).fillna(0)
        if cnt.mean() > 0:
            f["CV"] = cnt.std(ddof=0) / cnt.mean()
        iso = ent.index.isocalendar()
        wk = ent.groupby([iso["year"].values, iso["week"].values]).sum()
        W = len(wk)
        s = wk / wk.sum()
        if W > 1:
            f["HHI"] = ((s**2).sum() - 1 / W) / (1 - 1 / W)

    # R4 ingredients
    total = float(x.sum())
    f["cum_pnl"] = total
    f["efficiency"] = total / entries if entries else np.nan
    mdd = float((cum.cummax() - cum).max())
    yrs = (asof - launch).days / 365.25
    f["calmar"] = (total / yrs) / mdd if mdd > 0 and yrs > 0 else np.nan

    # R5 / PSR
    f["w"] = min(1.0, n_days / N_DAYS_FULL)
    sd = x.std()
    f["psr"] = float(norm.cdf(x.mean() / sd * np.sqrt(n_days - 1))) if n_days > 2 and sd > 0 else np.nan
    return f


def score_side(df: pd.DataFrame) -> pd.DataFrame:
    """df: candidate rows for one side. Adds in_pool, R2_raw, R3_raw, R4_raw, score, score_final."""
    df = df.copy()
    df["in_pool"] = (df["entries"] >= MIN_ENTRIES) & df["R1"].notna()
    for c in ("R2_raw", "R3_raw", "R4_raw", "score", "score_final"):
        df[c] = np.nan
    p = df[df["in_pool"]]
    if p.empty:
        return df
    r2 = pctrank(p["perf_gap"]) - pctrank(p["giveback"])
    r3 = -0.5 * (pctrank(p["CV"]) + pctrank(p["HHI"]))
    r4 = 0.5 * (pctrank(p["efficiency"]) + pctrank(p["calmar"]))
    df.loc[p.index, "R2_raw"], df.loc[p.index, "R3_raw"], df.loc[p.index, "R4_raw"] = r2, r3, r4
    p = df[df["in_pool"]]
    comp = pd.DataFrame({c: pctrank(p[c]) for c in ("R1", "R2_raw", "R3_raw", "R4_raw")})
    df.loc[p.index, "score"] = comp.mean(axis=1)
    df["score_final"] = df["w"] * df["score"] + (1 - df["w"]) * 0.5
    return df


def dedupe(sel: pd.DataFrame, P: pd.DataFrame, asof) -> pd.DataFrame:
    """R6 on the selected rows of one side. Returns sel with cluster_id, kept."""
    sel = sel.copy()
    if len(sel) < 2:
        sel["cluster_id"], sel["kept"] = 1, True
        return sel
    ids = list(sel["agent"])
    L = {r.agent: r.launch_date for r in sel.itertuples()}
    D = np.zeros((len(ids), len(ids)))
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            start = max(L[ids[i]], L[ids[j]])
            a, b = P[ids[i]].loc[start:asof], P[ids[j]].loc[start:asof]
            d = 1.0
            if len(a) >= CORR_MIN_DAYS and a.std() > 0 and b.std() > 0:
                rho = np.corrcoef(a, b)[0, 1]
                d = math.sqrt(max(0.0, (1 - rho) / 2))
            D[i, j] = D[j, i] = d
    Z = linkage(squareform(D, checks=False), method="average")
    cl = fcluster(Z, t=math.sqrt((1 - RHO_CUT) / 2), criterion="distance")
    sel["cluster_id"] = cl
    sel["kept"] = False
    for c in np.unique(cl):
        idx = sel.index[sel["cluster_id"] == c]
        sel.loc[sel.loc[idx, "score_final"].idxmax(), "kept"] = True
    return sel


def side_mean(P: pd.DataFrame, ids: list[str], idx) -> pd.Series:
    if not ids:
        return pd.Series(0.0, index=idx)
    return P.loc[idx, ids].mean(axis=1)


def walk_forward(P, T, sides, close):
    lab = market_labels(close)
    days = P.index
    launch = {}
    for a in P.columns:
        t = T[a]
        fd = t.index[t == 1]
        if len(fd):
            launch[a] = fd[0]
    first_year = min(launch.values()).year
    sel_rows, oos_rows, ytab = [], [], []
    for Y in range(first_year + 1, days[-1].year + 1):
        yd = days[days.year == Y]
        if len(yd) == 0:
            continue
        asof = days[days < yd[0]][-1]
        q20 = lab["dd"].loc[:asof].dropna().quantile(STRESS_Q)
        cands = [a for a in launch if launch[a] <= asof]
        feats = [agent_features(a, sides[a], P[a], T[a], lab, q20, launch[a], asof) for a in cands]
        F = pd.DataFrame(feats)
        parts = []
        kept = {"long": [], "short": []}
        n_pool = {"long": 0, "short": 0}
        for side in ("long", "short"):
            d = F[F["side"] == side].reset_index(drop=True) if len(F) else F
            if d.empty:
                continue
            d = score_side(d)
            n_pool[side] = int(d["in_pool"].sum())
            d["selected_top"], d["cluster_id"], d["kept"] = False, np.nan, False
            if n_pool[side]:
                k = math.ceil(TOP_FRAC * n_pool[side])
                top = d[d["in_pool"]].sort_values("score_final", ascending=False).head(k)
                d.loc[top.index, "selected_top"] = True
                dd_ = dedupe(d.loc[top.index], P, asof)
                d.loc[dd_.index, "cluster_id"] = dd_["cluster_id"]
                d.loc[dd_.index, "kept"] = dd_["kept"]
                kept[side] = list(d.loc[d["kept"].astype(bool), "agent"])
            parts.append(d)
        if parts:
            S = pd.concat(parts)
            S.insert(0, "feature_asof", asof)
            S.insert(0, "year", Y)
            sel_rows.append(S)

        # OOS paths
        allL = [a for a in cands if sides[a] == "long"]
        allS = [a for a in cands if sides[a] == "short"]
        rules = 0.5 * side_mean(P, kept["long"], yd) + 0.5 * side_mean(P, kept["short"], yd)
        b1 = P.loc[yd, cands].mean(axis=1) if cands else pd.Series(0.0, index=yd)
        b2 = 0.5 * side_mean(P, allL, yd) + 0.5 * side_mean(P, allS, yd)
        o = pd.DataFrame({"date": yd, "year": Y, "rules": rules.values, "b1_all_1n": b1.values,
                          "b2_side_1n": b2.values, "market_close": close.loc[yd].values})
        oos_rows.append(o)
        row = dict(year=Y, n_pool_long=n_pool["long"], n_pool_short=n_pool["short"],
                   n_kept_long=len(kept["long"]), n_kept_short=len(kept["short"]))
        for c in ("rules", "b1_all_1n", "b2_side_1n"):
            row[f"{c}_pnl"] = float(o[c].sum())
            row[f"{c}_sharpe"] = sharpe(o[c])
        row["excess_vs_b2"] = row["rules_pnl"] - row["b2_side_1n_pnl"]
        ytab.append(row)
    return pd.concat(sel_rows, ignore_index=True), pd.concat(oos_rows, ignore_index=True), pd.DataFrame(ytab)


def path_stats(x: pd.Series, yearly: pd.Series | None, b2_year: pd.Series):
    cum = x.cumsum()
    mdd = float((cum.cummax() - cum).max())
    yrs = len(x) / 252
    tot = float(x.sum())
    return dict(total_pnl=tot, sharpe=sharpe(x), max_dd=mdd,
                calmar=(tot / yrs) / mdd if mdd > 0 else np.nan,
                n_years=len(b2_year),
                years_beat_b2=int((yearly > b2_year).sum()) if yearly is not None else "-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DATA)
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--session-start", required=True, help="HH:MM inclusive (supplied by the data owner)")
    ap.add_argument("--session-end", required=True, help="HH:MM inclusive (supplied by the data owner)")
    a = ap.parse_args()
    figs, raw = a.out_dir / "figs", a.out_dir / "raw"
    figs.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)

    P, T, sides, close = load(a.data_dir, parse_hhmm(a.session_start), parse_hhmm(a.session_end))
    sel, oos, ytab = walk_forward(P, T, sides, close)
    sel_cols = ["year", "feature_asof", "agent", "side", "launch_date", "n_days", "entries", "R1",
                "perf_gap", "giveback", "R2_raw", "CV", "HHI", "R3_raw", "efficiency", "calmar",
                "R4_raw", "score", "w", "score_final", "psr", "in_pool", "selected_top",
                "cluster_id", "kept"]
    sel[sel_cols].to_csv(raw / "selection_by_year.csv", index=False)
    oos.to_csv(raw / "oos_daily_paths.csv", index=False)
    ytab.to_csv(a.out_dir / "yearly_table.csv", index=False)

    names = ["rules", "b1_all_1n", "b2_side_1n"]
    yr = oos.groupby("year")[names].sum()
    stats = pd.DataFrame({n: path_stats(oos[n], None if n == "b2_side_1n" else yr[n], yr["b2_side_1n"])
                          for n in names}).T
    stats.index.name = "path"
    stats.reset_index().to_csv(a.out_dir / "concat_path_stats.csv", index=False)
    with open(a.out_dir / "summary.txt", "w") as f:
        f.write(f"Walk-forward OOS, {oos['date'].min().date()} to {oos['date'].max().date()}, "
                f"{len(oos)} session days\n\nConcatenated OOS path stats (daily PnL, Sharpe x sqrt(252))\n")
        f.write(stats.to_string(float_format=lambda v: f"{v:,.4g}") + "\n\nYearly table\n")
        f.write(ytab.to_string(index=False, float_format=lambda v: f"{v:,.4g}") + "\n\nD parameters\n")
        for k in ("MIN_ENTRIES", "MIN_STATE_DAYS", "RECENT_DAYS", "MIN_RECENT_TRADES", "MIN_FULL_YEARS",
                  "MIN_ENTRIES_R3", "N_DAYS_FULL", "TOP_FRAC", "STRESS_Q", "CORR_MIN_DAYS", "RHO_CUT",
                  "TREND_WINDOWS"):
            f.write(f"{k} = {globals()[k]}\n")
        f.write(f"session = {a.session_start}-{a.session_end}\n")

    path_labels = {
        "rules": "Rules R1–R6: select agents each year",
        "b1_all_1n": "Benchmark: equal-weight all agents",
        "b2_side_1n": "Benchmark: equal-weight long/short 50/50 (primary)",
    }
    fig, ax = plt.subplots(figsize=(11, 5))
    for n in names:
        ax.plot(oos["date"], oos[n].cumsum(), label=path_labels[n],
                lw=1.6 if n == "rules" else 1.0)
    for y in ytab["year"]:
        ax.axvline(pd.Timestamp(f"{y}-01-01"), color="gray", ls="--", lw=0.5)
    ax.set_title("Concatenated OOS cumulative PnL")
    ax.set_ylabel("Cumulative PnL (session units)")
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(figs / "fig_oos_cum_paths.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(ytab["year"].astype(str), ytab["excess_vs_b2"],
           color=np.where(ytab["excess_vs_b2"] >= 0, "tab:green", "tab:red"))
    ax.axhline(0, color="k", lw=0.6)
    ax.set_title("Yearly PnL excess: Rules R1–R6 − side 50/50 1/N")
    ax.set_ylabel("PnL excess vs primary benchmark")
    fig.tight_layout()
    fig.savefig(figs / "fig_yearly_excess_vs_b2.png", dpi=130)
    plt.close(fig)

    (a.out_dir / "README.md").write_text(
        "# Agent selection rules (R1-R6) walk-forward\n\n"
        "Implements docs/agent_selection_rules_zh.md sections 1-4. Each year Y, features use data up to the "
        "last session day before Y (`feature_asof`); the kept agents' daily PnL over Y is the OOS path.\n\n"
        "- `raw/oos_daily_paths.csv`: daily OOS PnL of rules and benchmarks b1/b2, plus market close.\n"
        "- `raw/selection_by_year.csv`: one row per candidate agent per year with all features, scores, "
        "selection and cluster flags.\n"
        "- `yearly_table.csv`: per-year pool/kept counts, PnL and Sharpe of each path, excess vs b2.\n"
        "- `concat_path_stats.csv`: concatenated-path total PnL / Sharpe / maxDD / Calmar.\n"
        "- `summary.txt`: concatenated-path stats, yearly table, D parameters.\n"
        "- `figs/fig_oos_cum_paths.png`, `figs/fig_yearly_excess_vs_b2.png`.\n\n"
        "Rerun: `.venv/bin/python agent_selection_rules.py [--data-dir DIR --out-dir DIR "
        "--session-start HH:MM --session-end HH:MM]`\n")
    print((a.out_dir / "summary.txt").read_text())


if __name__ == "__main__":
    main()
