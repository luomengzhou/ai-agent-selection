"""Smoke tests for the pure functions in agent_selection_rules.py (no data files needed)."""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent_selection_rules as R  # noqa: E402


def test_sharpe_annualises_daily_with_sqrt_252():
    x = pd.Series([1.0, -1.0, 2.0, 0.5, -0.5])
    expected = x.mean() / x.std() * math.sqrt(252)
    assert math.isclose(R.sharpe(x), expected)
    assert np.isnan(R.sharpe(pd.Series([1.0, 1.0, 1.0])))  # zero std -> NaN, not inf
    assert np.isnan(R.sharpe(pd.Series([1.0])))


def test_path_stats_max_drawdown_and_total():
    x = pd.Series([10.0, -4.0, -6.0, 5.0, -12.0, 3.0])
    # cum: 10, 6, 0, 5, -7, -4 ; peak-to-trough: 10 -> -7 = 17
    st = R.path_stats(x, None, pd.Series([1.0]))
    assert st["total_pnl"] == -4.0
    assert st["max_dd"] == 17.0
    assert st["years_beat_b2"] == "-"


def test_market_labels_use_previous_day_only():
    idx = pd.bdate_range("2020-01-01", periods=400)
    close = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
    lab = R.market_labels(close)
    # labels for day d are shifted by one session, so a jump on day d must not show up in d's label
    close2 = close.copy()
    close2.iloc[300] *= 2
    lab2 = R.market_labels(close2)
    # day 300 (and 301, whose label is the day-300 new high) unchanged; from day 302 the label sees the spike
    assert lab.loc[idx[300], "dd"] == lab2.loc[idx[300], "dd"]
    assert lab2.loc[idx[301], "dd"] == 0.0
    assert lab2.loc[idx[302], "dd"] < lab.loc[idx[302], "dd"]
    # monotone up-trend -> trend label +1 once all windows are available
    assert lab["trend"].iloc[-1] == 1.0


def test_dedupe_keeps_one_agent_per_correlated_cluster():
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2015-01-01", periods=600)
    a = rng.normal(size=len(idx))
    P = pd.DataFrame({"A": a, "B": a + 0.05 * rng.normal(size=len(idx)),  # clone of A
                      "C": rng.normal(size=len(idx))}, index=idx)
    sel = pd.DataFrame({"agent": ["A", "B", "C"], "launch_date": [idx[0]] * 3,
                        "score_final": [0.9, 0.8, 0.7]})
    out = R.dedupe(sel, P, idx[-1])
    assert out.loc[out["agent"] == "A", "cluster_id"].item() == out.loc[out["agent"] == "B", "cluster_id"].item()
    assert bool(out.loc[out["agent"] == "A", "kept"].item())
    assert not bool(out.loc[out["agent"] == "B", "kept"].item())  # lower-scored clone dropped
    assert bool(out.loc[out["agent"] == "C", "kept"].item())
