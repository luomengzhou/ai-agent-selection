# hold_spell_vs_market

Data: `Nasdaq_20261019_1548_120min_1130`  session 11:35–13:30

Strip flat (no price-move) time. Compare in-spell agent PnL to **same-side**
dead-hold (±4). Long agents vs +4; short vs −4.
No opposite-sign benchmark.

## Result (boundary-aligned)

Dead-hold uses the same price boundary as `bar_pnl` (bar *before* spell start → spell end),
so a constant ±4 position matches the agent **exactly** while in spell.
Therefore `agent_minus_same_side` is **identically 0** for all agents here (0/148 beat dead-hold; gap mean=0).
Same-side dead-hold is a sanity check of the alignment, **not** a selection signal.

Agents: **148** / 148

## Human layer
- `hold_spell_summary.csv` — one-screen metrics (expect gap≈0 after alignment)
- (no per-agent figs; ran with `--no-figs`)

## Raw
- `raw/hold_spell_vs_passive_all148.csv` — one row per agent

## Re-run
```bash
.venv/bin/python eda_hold_spell_vs_market.py --data-dir Nasdaq_20261019_1548_120min_1130 --out-dir outputs_eda_nasdaq_120min_1130/hold_spell_vs_market --session-start 11:35 --session-end 13:30
```
