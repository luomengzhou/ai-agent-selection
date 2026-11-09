#!/usr/bin/env bash
# Run the EDA suite on one local data cut.
#   usage: run_eda_nasdaq.sh [--with-time-trades] DATA_DIR OUT_DIR SESSION_START SESSION_END
#   e.g.   run_eda_nasdaq.sh data_cut2 outputs_eda_cut2 HH:MM HH:MM
# DATA_DIR holds the raw parquet files; OUT_DIR is git-ignored (outputs_eda_*).
# Default skips time/ + trades/; pass --with-time-trades to also refresh those.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python}
WITH_TIME_TRADES=0
if [[ "${1:-}" == "--with-time-trades" ]]; then
  WITH_TIME_TRADES=1
  shift
fi
if [[ $# -ne 4 ]]; then
  echo "usage: $0 [--with-time-trades] DATA_DIR OUT_DIR SESSION_START SESSION_END" >&2
  exit 1
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
  # summary/raw only (no per-agent PNGs)
  $PY eda_hold_spell_vs_market.py --data-dir "$data_dir" \
    --out-dir "$out/hold_spell_vs_market" \
    --session-start "$sess_start" --session-end "$sess_end" \
    --no-figs

  echo "======== $(date '+%F %T') DONE $out ========"
}

run_one "$1" "$2" "$3" "$4"

echo "ALL DONE $(date '+%F %T')"
