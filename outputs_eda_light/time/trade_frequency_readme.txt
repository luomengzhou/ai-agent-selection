Definition: an "active bar" / trade proxy = 5-min bar where bar_pnl = diff(cum_ot_pnl) != 0.
This is NOT exchange fill count; consecutive nonzero bars count separately.
trades_per_year = n_active_bars / years between first and last active bar.
Co-timing: cosine similarity of hour-of-week histograms (7*24 bins), ignoring PnL sign/direction.
