"""
Diagnostics for agent_selection_rules.py output:
(1) single-rule ablation (each R alone, R2-R4 without R1, all four without the R1 gate);
(2) random same-size selection from the same point-in-time pool (null distribution).
Reads outputs_rules_light/raw/*.csv; writes outputs_rules_light/diagnostics.txt.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

import agent_selection_rules as R

VARIANTS = [  # (label, column to rank on, require R1 non-missing)
    ("R1 only", "R1", True),
    ("R2 only", "R2_raw", False),
    ("R3 only", "R3_raw", False),
    ("R4 only", "R4_raw", False),
    ("R2+R3+R4 (no R1)", "score_noR1", False),
    ("all 4, R1 not required", "score_all_noreq", False),
]


def sharpe(x: pd.Series) -> float:
    return float(x.mean() / x.std() * np.sqrt(252))


def stats(x: pd.Series) -> dict:
    cum = x.cumsum()
    return dict(total=round(float(x.sum())), sharpe=round(sharpe(x), 2),
                maxdd=round(float((cum.cummax() - cum).max())))


def add_scores(sel: pd.DataFrame) -> pd.DataFrame:
    sel = sel.copy()
    for (Y, side), idx in sel.groupby(["year", "side"]).groups.items():
        m = sel.index.isin(idx) & (sel["entries"] >= R.MIN_ENTRIES)
        comp = pd.DataFrame({c: sel.loc[m, c].rank(pct=True) for c in ("R1", "R2_raw", "R3_raw", "R4_raw")})
        sel.loc[m, "score_noR1"] = comp[["R2_raw", "R3_raw", "R4_raw"]].mean(axis=1)
        sel.loc[m, "score_all_noreq"] = comp.mean(axis=1)
    return sel


def variant_path(sel, P, col, require_r1, years) -> pd.Series:
    days = P.index
    out = []
    for Y in years:
        yd = days[days.year == Y]
        d = sel[sel["year"] == Y]
        if len(yd) == 0 or d.empty:
            continue
        asof = d["feature_asof"].iloc[0]
        tot = pd.Series(0.0, index=yd)
        for side in ("long", "short"):
            s = d[(d["side"] == side) & (d["entries"] >= R.MIN_ENTRIES) & d[col].notna()]
            if require_r1:
                s = s[s["R1"].notna()]
            if s.empty:
                continue
            top = s.sort_values(col, ascending=False).head(math.ceil(R.TOP_FRAC * len(s))).copy()
            top["score_final"] = top[col]
            top = R.dedupe(top, P, asof)
            tot += 0.5 * P.loc[yd, list(top.loc[top["kept"], "agent"])].mean(axis=1)
        out.append(tot)
    return pd.concat(out)


def random_path(sel, P, years, rng) -> pd.Series:
    days = P.index
    out = []
    for Y in years:
        yd = days[days.year == Y]
        d = sel[sel["year"] == Y]
        if len(yd) == 0:
            continue
        tot = pd.Series(0.0, index=yd)
        for side in ("long", "short"):
            s = d[(d["side"] == side) & d["in_pool"]]
            if s.empty:
                continue
            pick = rng.choice(s["agent"].values, math.ceil(R.TOP_FRAC * len(s)), replace=False)
            tot += 0.5 * P.loc[yd, list(pick)].mean(axis=1)
        out.append(tot)
    return pd.concat(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=R.DATA)
    ap.add_argument("--out-dir", type=Path, default=R.OUT)
    ap.add_argument("--session-start", required=True, help="HH:MM inclusive (supplied by the data owner)")
    ap.add_argument("--session-end", required=True, help="HH:MM inclusive (supplied by the data owner)")
    ap.add_argument("--n-random", type=int, default=300)
    ap.add_argument("--from-year", type=int, default=2018, help="second window start (both sides populated)")
    a = ap.parse_args()
    P, _, _, _ = R.load(a.data_dir, R.parse_hhmm(a.session_start), R.parse_hhmm(a.session_end))
    sel = add_scores(pd.read_csv(a.out_dir / "raw" / "selection_by_year.csv", parse_dates=["feature_asof"]))
    oos = pd.read_csv(a.out_dir / "raw" / "oos_daily_paths.csv", parse_dates=["date"]).set_index("date")
    rng = np.random.default_rng(0)
    lines = []
    for y0 in (int(oos.index.year.min()), a.from_year):
        years = range(y0, int(oos.index.year.max()) + 1)
        o = oos[oos.index.year >= y0]
        rows = {"b2_side_1n": stats(o["b2_side_1n"]), "rules (as run)": stats(o["rules"])}
        for label, col, req in VARIANTS:
            rows[label] = stats(variant_path(sel, P, col, req, years))
        sims = np.array([sharpe(random_path(sel, P, years, rng)) for _ in range(a.n_random)])
        r = sharpe(o["rules"])
        lines += [f"== {years[0]}-{years[-1]} ==", pd.DataFrame(rows).T.to_string(), "",
                  f"random same-size top-{R.TOP_FRAC:.0%} from the same pool, n={a.n_random}: "
                  f"Sharpe median={np.median(sims):.2f}, 5%={np.percentile(sims, 5):.2f}, "
                  f"95%={np.percentile(sims, 95):.2f}; rules={r:.2f} sits at percentile "
                  f"{np.mean(sims < r) * 100:.0f}%", ""]
    text = "\n".join(lines)
    (a.out_dir / "diagnostics.txt").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
