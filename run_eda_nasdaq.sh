#!/usr/bin/env bash
# Run the same EDA suite as Mini on both Nasdaq datasets.
# Default skips time/ + trades/ (session window already in folder titles).
# Pass --with-time-trades to also refresh those.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
WITH_TIME_TRADES=0
if [[ "${1:-}" == "--with-time-trades" ]]; then
  WITH_TIME_TRADES=1
  shift
fi

run_one() {
  local data_dir=$1 out=$2 sess_start=$3 sess_end=$4
  echo "======== $(date '+%F %T') START $data_dir → $out  session=$sess_start-$sess_end ========"
  mkdir -p "$out"/{features,sharpe_dd,hold_spell_vs_market}

  if [[ "$WITH_TIME_TRADES" -eq 1 ]]; then
    mkdir -p "$out"/{time,trades}
    echo "--- eda_mini_light ---"
    $PY eda_mini_light.py --data-dir "$data_dir" --out-dir "$out"

    echo "--- eda_trade_frequency ---"
    $PY eda_trade_frequency.py --data-dir "$data_dir" --out-dir "$out/time"

    echo "--- eda_trade_spells ---"
    $PY eda_trade_spells.py --data-dir "$data_dir" --out-dir "$out/trades" \
      --session-start "$sess_start" --session-end "$sess_end"
  else
    echo "--- skip time/ + trades/ (pass --with-time-trades to refresh) ---"
  fi

  echo "--- eda_session_features ---"
  $PY eda_session_features.py --data-dir "$data_dir" --out-dir "$out/features" \
    --session-start "$sess_start" --session-end "$sess_end"

  echo "--- eda_sharpe_dd_persistence ---"
  $PY eda_sharpe_dd_persistence.py --data-dir "$data_dir" --out-dir "$out/sharpe_dd" \
    --session-start "$sess_start" --session-end "$sess_end"

  echo "--- eda_agent_corr_session ---"
  $PY eda_agent_corr_session.py --data-dir "$data_dir" --out-dir "$out/features" \
    --session-start "$sess_start" --session-end "$sess_end"

  echo "--- eda_hold_spell_vs_market ---"
  # Match Mini: summary/raw only (per-agent PNGs are not in Mini outputs)
  $PY eda_hold_spell_vs_market.py --data-dir "$data_dir" \
    --out-dir "$out/hold_spell_vs_market" \
    --session-start "$sess_start" --session-end "$sess_end" \
    --no-figs

  echo "======== $(date '+%F %T') DONE $out ========"
}

run_one \
  Nasdaq_20261019_1548_120min_1130 \
  outputs_eda_nasdaq_120min_1130 \
  11:35 13:30

run_one \
  Nasdaq_20261020_0912_90min_1430 \
  outputs_eda_nasdaq_90min_1430 \
  14:35 16:00

echo "ALL DONE $(date '+%F %T')"
