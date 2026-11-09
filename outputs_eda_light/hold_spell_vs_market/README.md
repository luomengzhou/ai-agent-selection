# hold_spell_vs_market

Data: `Mini_20261006_2158-120min-1130`  session Mon–Fri 11:35–13:30

Compare in-spell agent PnL to **same-side** dead-hold (±4).

## Result (boundary-aligned)

Dead-hold uses the same price boundary as `bar_pnl` (bar *before* spell start → spell end),
so constant ±4 matches the agent **exactly** while in spell.
On this dump: **`agent_minus_same_side` ≡ 0 for all 70 agents** (0/70 beat dead-hold).
Same-side dead-hold is an alignment sanity check, **not** a selection signal.
No gap-by-side figure (bars would be height 0).

## Human
- `hold_spell_summary.csv`

## Raw
- `raw/hold_spell_vs_passive_all70.csv`
