"""
Two follow-up experiments on top of agent_selection_rules.py (same walk-forward, same look-ahead rules).

A. "Fix the rules": R1 becomes a *relative* participation measure
       R1_rel = [P(trade|opportunity) - P(trade|adverse)] / P(trade)
   and the stress quantile is taken over the trailing STRESS_WINDOW session days (not since 2006).
   Variants: A_R1rel (R1 optional), A_R1rel_req (R1 required). Rest of the pipeline unchanged.

B. "Drop the bad ones": start from the side-1/N benchmark (all launched agents) and remove the
   bottom DROP_FRAC of each side by a deterioration score; agents that cannot be scored are kept.
   Variants: B_dropR2 (by R2_raw), B_dropScore (by mean rank of R2/R3/R4).

Nulls: random top-20% picks (for A) and random 20% drops (for B), N_RANDOM draws each.
Outputs: outputs_rules_light/experiments/{summary.txt, yearly_table.csv, raw/selection_<variant>.csv, figs/}.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import agent_selection_rules as R

STRESS_WINDOW = 1260   # D: trailing 5 years of session days for the stress quantile (exp A)
DROP_FRAC = 0.2        # D: share of each side removed in exp B
N_RANDOM = 300


def r1_relative(tr, lab, q20, side, launch, asof) -> float:
    l, t = lab.loc[launch:asof], tr.loc[launch:asof]
    ok = t.notna() & l["trend"].notna() & l["dd"].notna()
    up, down, stress = l["trend"] > 0, l["trend"] < 0, l["dd"] <= q20
    opp, adv = (up, stress) if side == "long" else ((down | stress), up)
    opp, adv = opp & ok, adv & ok
    base = (t[ok] == 1).mean() if ok.sum() else 0.0
    if opp.sum() < R.MIN_STATE_DAYS or adv.sum() < R.MIN_STATE_DAYS or base == 0:
        return np.nan
    return float(((t[opp] == 1).mean() - (t[adv] == 1).mean()) / base)


def pct(s):
    return s.rank(pct=True)


def score_rank_pick(d: pd.DataFrame, cols, require_r1: bool, P, asof):
    """Top-20% by mean of available pct-ranks of `cols`, R5 discount, R6 dedupe. Returns kept agent ids."""
    pool = d[d["entries"] >= R.MIN_ENTRIES].copy()
    if require_r1:
        pool = pool[pool["R1"].notna()]
    if pool.empty:
        return [], pool
    comp = pd.DataFrame({c: pct(pool[c]) for c in cols})
    pool["score"] = comp.mean(axis=1)
    pool = pool[pool["score"].notna()]
    pool["score_final"] = pool["w"] * pool["score"] + (1 - pool["w"]) * 0.5
    top = pool.sort_values("score_final", ascending=False).head(math.ceil(R.TOP_FRAC * len(pool)))
    top = R.dedupe(top, P, asof)
    return list(top.loc[top["kept"], "agent"]), top


def drop_pick(d: pd.DataFrame, cols, all_ids):
    """Side-1/N minus the bottom DROP_FRAC by mean pct-rank of `cols`. Unscorable agents are kept."""
    pool = d[d["entries"] >= R.MIN_ENTRIES].copy()
    if pool.empty:
        return list(all_ids), pd.DataFrame()
    comp = pd.DataFrame({c: pct(pool[c]) for c in cols})
    pool["bad_score"] = comp.mean(axis=1)
    scorable = pool[pool["bad_score"].notna()].sort_values("bad_score")
    dropped = set(scorable.head(math.floor(DROP_FRAC * len(scorable)))["agent"])
    pool["dropped"] = pool["agent"].isin(dropped)
    return [a for a in all_ids if a not in dropped], pool


def sharpe(x):
    return R.sharpe(x)


def stats(x: pd.Series) -> dict:
    cum = x.cumsum()
    return dict(total=round(float(x.sum())), sharpe=round(sharpe(x), 2),
                maxdd=round(float((cum.cummax() - cum).max())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=R.DATA)
    ap.add_argument("--out-dir", type=Path, default=R.OUT / "experiments")
    ap.add_argument("--session-start", default="11:35")
    ap.add_argument("--session-end", default="13:30")
    ap.add_argument("--from-year", type=int, default=2018)
    a = ap.parse_args()
    figs, raw = a.out_dir / "figs", a.out_dir / "raw"
    figs.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)

    P, T, sides, close = R.load(a.data_dir, R.parse_hhmm(a.session_start), R.parse_hhmm(a.session_end))
    lab = R.market_labels(close)
    days = P.index
    launch = {c: T[c].index[T[c] == 1][0] for c in P.columns if (T[c] == 1).any()}
    rng = np.random.default_rng(0)

    variants = ["b2_side_1n", "rules_v0", "A_R1rel", "A_R1rel_req", "B_dropR2", "B_dropScore"]
    paths = {v: [] for v in variants}
    nulls = {"randTop20": [[] for _ in range(N_RANDOM)], "randDrop20": [[] for _ in range(N_RANDOM)]}
    sel_rows = {v: [] for v in variants}
    ytab = []
    for Y in range(min(l.year for l in launch.values()) + 1, days[-1].year + 1):
        yd = days[days.year == Y]
        if len(yd) == 0:
            continue
        asof = days[days < yd[0]][-1]
        q20_full = lab["dd"].loc[:asof].dropna().quantile(R.STRESS_Q)
        q20_roll = lab["dd"].loc[:asof].dropna().iloc[-STRESS_WINDOW:].quantile(R.STRESS_Q)
        cands = [c for c in launch if launch[c] <= asof]
        F = pd.DataFrame([R.agent_features(c, sides[c], P[c], T[c], lab, q20_full, launch[c], asof) for c in cands])
        F["R1_rel"] = [r1_relative(T[c], lab, q20_roll, sides[c], launch[c], asof) for c in cands]
        row = dict(year=Y)
        side_pnl = {v: pd.Series(0.0, index=yd) for v in variants}
        null_pnl = {k: [pd.Series(0.0, index=yd) for _ in range(N_RANDOM)] for k in nulls}
        for side in ("long", "short"):
            d = F[F["side"] == side].reset_index(drop=True)
            all_ids = list(d["agent"])
            if not all_ids:
                continue
            # raw ranks for R2-R4 among the pool, as in the main script
            d = R.score_side(d)
            kept = {"b2_side_1n": all_ids}
            kept["rules_v0"], t0 = score_rank_pick(d, ["R1", "R2_raw", "R3_raw", "R4_raw"], True, P, asof)
            dA = d.copy()
            dA["R1"] = dA["R1_rel"]
            kept["A_R1rel"], tA = score_rank_pick(dA, ["R1", "R2_raw", "R3_raw", "R4_raw"], False, P, asof)
            kept["A_R1rel_req"], tAr = score_rank_pick(dA, ["R1", "R2_raw", "R3_raw", "R4_raw"], True, P, asof)
            kept["B_dropR2"], bR2 = drop_pick(d, ["R2_raw"], all_ids)
            kept["B_dropScore"], bSc = drop_pick(d, ["R2_raw", "R3_raw", "R4_raw"], all_ids)
            for v in variants:
                side_pnl[v] += 0.5 * R.side_mean(P, kept[v], yd)
                row[f"n_{v}_{side}"] = len(kept[v])
            for v, t in (("rules_v0", t0), ("A_R1rel", tA), ("A_R1rel_req", tAr)):
                if len(t):
                    sel_rows[v].append(t.assign(year=Y, feature_asof=asof))
            for v, t in (("B_dropR2", bR2), ("B_dropScore", bSc)):
                if len(t):
                    sel_rows[v].append(t.assign(year=Y, feature_asof=asof))
            # nulls
            pool = list(d.loc[(d["entries"] >= R.MIN_ENTRIES), "agent"])
            k_top = math.ceil(R.TOP_FRAC * len(pool)) if pool else 0
            k_drop = math.floor(DROP_FRAC * len(pool)) if pool else 0
            for i in range(N_RANDOM):
                if k_top:
                    null_pnl["randTop20"][i] += 0.5 * R.side_mean(P, list(rng.choice(pool, k_top, replace=False)), yd)
                drop = set(rng.choice(pool, k_drop, replace=False)) if k_drop else set()
                null_pnl["randDrop20"][i] += 0.5 * R.side_mean(P, [x for x in all_ids if x not in drop], yd)
        for v in variants:
            paths[v].append(side_pnl[v])
            row[f"{v}_pnl"] = float(side_pnl[v].sum())
            row[f"{v}_sharpe"] = sharpe(side_pnl[v])
        for k in nulls:
            for i in range(N_RANDOM):
                nulls[k][i].append(null_pnl[k][i])
        ytab.append(row)

    paths = {v: pd.concat(p) for v, p in paths.items()}
    nulls = {k: [pd.concat(p) for p in lst] for k, lst in nulls.items()}
    ytab = pd.DataFrame(ytab)
    ytab.to_csv(a.out_dir / "yearly_table.csv", index=False)
    pd.DataFrame(paths).to_csv(raw / "oos_daily_paths.csv")
    for v, rows in sel_rows.items():
        if rows:
            pd.concat(rows, ignore_index=True).to_csv(raw / f"selection_{v}.csv", index=False)

    lines = [f"Experiments A/B, walk-forward {days[days.year >= ytab['year'].min()][0].date()} to {days[-1].date()}", ""]
    for y0 in (int(ytab["year"].min()), a.from_year):
        m = paths["b2_side_1n"].index.year >= y0
        tab = pd.DataFrame({v: stats(p[m]) for v, p in paths.items()}).T
        yy = ytab[ytab["year"] >= y0]
        tab["years_beat_b2"] = [int((yy[f"{v}_pnl"] > yy["b2_side_1n_pnl"]).sum()) if v != "b2_side_1n" else "-" for v in tab.index]
        lines += [f"== {y0}-{int(ytab['year'].max())} ==", tab.to_string(), ""]
        for k, lst in nulls.items():
            s = np.array([sharpe(p[m]) for p in lst])
            tgt = {"randTop20": ["rules_v0", "A_R1rel", "A_R1rel_req"], "randDrop20": ["B_dropR2", "B_dropScore"]}[k]
            where = ", ".join(f"{v}={sharpe(paths[v][m]):.2f} (pct {np.mean(s < sharpe(paths[v][m])) * 100:.0f}%)" for v in tgt)
            lines.append(f"null {k} (n={N_RANDOM}): Sharpe median={np.median(s):.2f} 5%={np.percentile(s, 5):.2f} "
                         f"95%={np.percentile(s, 95):.2f} | {where}")
        lines.append("")
    lines += ["Yearly table", ytab.to_string(index=False, float_format=lambda v: f"{v:,.4g}"), "",
              f"D parameters: STRESS_WINDOW={STRESS_WINDOW} DROP_FRAC={DROP_FRAC} N_RANDOM={N_RANDOM}; "
              f"others as in agent_selection_rules.py"]
    (a.out_dir / "summary.txt").write_text("\n".join(lines))
    print("\n".join(lines))

    fig, ax = plt.subplots(figsize=(11, 5))
    for v, p in paths.items():
        ax.plot(p.index, p.cumsum(), label=v, lw=1.6 if v == "b2_side_1n" else 1.0)
    for y in ytab["year"]:
        ax.axvline(pd.Timestamp(f"{y}-01-01"), color="gray", ls="--", lw=0.5)
    ax.set_title("Experiments A/B: concatenated OOS cumulative PnL")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figs / "fig_experiments_cum_paths.png", dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
