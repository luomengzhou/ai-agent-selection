# Agent Selection Rules (R1–R6)

Status: **implemented for Mini; first walk-forward results are negative** (rules do not beat side-equal-weight or a same-size random draw).  
Chinese design memo (full rationale): [`agent_selection_rules_zh.md`](agent_selection_rules_zh.md).  
First-round results: [`rules_results_2026-11-03.md`](rules_results_2026-11-03.md).

**Code**

| Script | Role | Output |
|--------|------|--------|
| `agent_selection_rules.py` | Primary R1–R6 + yearly walk-forward | `outputs_rules_light/` |
| `agent_selection_diagnostics.py` | Single-rule ablation + random same-size null | `outputs_rules_light/diagnostics.txt` |
| `agent_selection_experiments.py` | Two correction directions (A / B) | `outputs_rules_light/experiments/` |

Rerun notes and file layout: `outputs_rules_light/README.md`.

Goal: using only information known as of `feature_asof`, select a subset of agents that beats matched equal-weight benchmarks. Rules below are the computable definitions.

---

## 1. Six rules

Each rule is a feature to test, not a proven selection law. Ranks are within-side percentile ranks unless noted.

### R1 — Side-aware regime participation

Long should trade in up markets and stay flat in stress; short should trade in down/stress and stay flat in up.

**Market labels** (prices known before the decision day only):

\[
trend_d=\frac{\operatorname{sign}(r_{21})+\operatorname{sign}(r_{63})+\operatorname{sign}(r_{252})}{3}
\]

- `up`: `trend>0`; `down`: `trend<0`; `neutral`: `trend=0`.
- `stress`: prior-day 252-day rolling drawdown below the training-window 20th percentile.
- Count only post-launch days whose full session identifies trade vs flat.

\[
R1=\tfrac12\left[P(trade=1\mid opportunity)+P(flat=1\mid adverse)\right]
\]

- Long: `opportunity=up`, `adverse=stress`.
- Short: `opportunity=down or stress`, `adverse=up`.
- Missing if either condition has fewer than 20 identifiable decision days.

### R2 — Recent deterioration

- `perf_gap = Sharpe(last 252 session days) - Sharpe(prior history)`; prior history ≥ 252 days.
- `giveback = current_drawdown / max(gross_profit_to_peak, ε)`, all as of `feature_asof`.
- Within side: `R2 = rank(perf_gap) - rank(giveback)`.
- Too few recent trades → missing (not “bad”).

### R3 — Activation stability

- `entry` = inferred position 0→±4 (not `bar_pnl!=0`).
- Annual entry-count CV; weekly normalized HHI:

\[
HHI^*=\frac{\sum_w s_w^2-1/W}{1-1/W}
\]

`R3 = -0.5 × [rank(CV) + rank(HHI*)]`. Require ≥3 complete years and ≥20 identifiable entries; else missing.

### R4 — Trading efficiency

Within the same side and `feature_asof` cross-section:

- `efficiency = cumulative PnL / completed entries`
- `Calmar = historical annualized PnL / maxDD`

`R4 = 0.5 × [rank(efficiency) + rank(Calmar)]`. Entries/year (or turnover proxies) are diagnostic only.

### R5 — Evidence sufficiency (length discount)

R5 is not a separate score. It shrinks the R1–R4 composite toward the mid-rank:

- `score` = equal-weight average of available within-side ranks of R1–R4 (see §2).
- `w = min(1, n / N0)` with `N0 = 756` session days (~3 years); `n` = live session days as of `feature_asof`.
- `score_final = w × score + (1 − w) × 0.5`.

Eligibility (not the R5 score): ≥10 completed entries and R1 computable; else missing this period. PSR / MinTRL are reported as diagnostics; a hard `PSR ≥ 95%` gate is a robustness check, not primary.

### R6 — Same-side clone removal (correlation clustering)

Within each side only, using pre-`feature_asof` daily PnL and **signed** \(\rho\):

- Distance \(d_{ij}=\sqrt{(1-\rho_{ij})/2}\), average linkage, ≥252 common days.
- Cut clusters at \(\rho\ge0.7\) (\(d\approx0.387\)); insufficient overlap → singleton.
- Keep the highest-`score_final` agent per cluster.

Goal: drop same-side clones. Do not pair long–short on correlation.

### Explicit exclusions

- Same-side dead-hold gap ≡ 0 after alignment: sanity check only.
- Do not force more trades because hit rate is high; this project selects agents, it does not change their policy.
- Same-side capture under fixed ±4, near-full-session holds is nearly an identity; not a core signal.

---

## 2. Portfolio construction

1. **Split sides.** Long and short pools ranked separately.
2. **Compute gate.** ≥10 completed entries and R1 available; else out of pool this period.
3. **Within-side ranks.** Convert R1–R4 to percentile ranks inside each side.
4. **Score.** R1 required; use whichever of R2–R4 are available; equal-average those ranks → `score`.
5. **R5 discount.** `score_final = w × score + (1 − w) × 0.5`.
6. **Top 20% per side** by `score_final`.
7. **R6 de-clone** among selected agents; one survivor per cluster (final count can be below 20% of the eligible pool).
8. **Equal weight within side; 50% long / 50% short** gross budget. Empty side stays cash (not reallocated).
9. **Yearly reselect.** Before the first trading day of year \(Y\), redo steps 1–8 on data ≤ last session day before \(Y\); hold one year.

Top 20%, equal feature weights, and 50/50 are preregistered design choices, not paper optima.

### Benchmarks to beat

1. Point-in-time all-agent equal weight.
2. **Side-matched long/short 50/50 equal weight** (primary): same side budget, no selection inside each side.

Do **not** add a “risk-budget / vol-scaled” benchmark. Scaling the side-equal-weight path by \(\sigma_{\text{rules}}/\sigma_{\text{b2}}\) is just leverage on the benchmark, not a separate strategy. If rules already lose on Sharpe and total PnL, that check is unnecessary.

Until point value, costs, slippage, and capital use are confirmed, report a PnL-unit portfolio, not investable returns.

### Point-in-time universe

- No official launch/retire dates; temporary proxy = first identifiable trade day.
- Cannot separate pre-launch from live-but-never-traded; survivorship risk remains.
- Pool membership uses the compute gate above only; future file existence cannot define the historical universe. R5 discounts scores; it does not decide pool entry.
