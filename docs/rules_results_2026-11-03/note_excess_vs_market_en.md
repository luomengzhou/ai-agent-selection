# Note: Does yearly rules−benchmark excess track “good vs bad” markets?

Figure: [`figs/fig_yearly_excess_vs_b2.png`](figs/fig_yearly_excess_vs_b2.png)  
Data: [`raw/yearly_excess_vs_market.csv`](raw/yearly_excess_vs_market.csv)  
Chinese version: [`note_excess_vs_market_zh.md`](note_excess_vs_market_zh.md)

## Hypothesis

From the yearly excess bar chart: relative to side-matched equal weight (b2), do the R1–R6 rules look **worse in bull years** and **better in weak/down years**? If so, excess may partly reflect risk appetite / regime, not only a uniform selection failure.

## Setup

- Excess = annual PnL of the rules portfolio − b2 (same definition as the figure).
- Market = session `market_close` return over the year (`mkt_ret`); also within-year max drawdown and realized vol.
- Primary lens: **2018 onward** (both long and short sides have kept agents). 2010–2017 often have an empty long sleeve and are not comparable.

## Results

**Correlation of excess with annual market return**

| Sample | n | Spearman | p | Pearson | p |
|--------|---|----------|---|---------|---|
| All years | 17 | −0.22 | 0.40 | −0.35 | 0.17 |
| 2018+ | 9 | **−0.63** | 0.07 | −0.62 | 0.07 |

Sign matches “stronger market → worse excess,” but the full sample is insignificant; with only nine post-2017 years (p≈0.07) this is suggestive, not conclusive.

**By up/down years (2018+)**

| Market | Years | Approx. excess |
|--------|-------|----------------|
| Down | 2018 (−6%), 2022 (−20%) | +118, +55 (both beat b2) |
| Strong up, clear underperformance | 2019 (+28%), 2021 (+27%) | −52, −27 |
| Strong up but positive excess | 2023 (+24%), 2024 (+23%) | +18, +70 |
| Other up years | 2020, 2025, 2026 | −34, −9, +39 |

**Counterexamples to a clean “bears win / bulls lose” story**

- 2023 and 2024 are strong up years with **positive** excess.
- 2015 is roughly flat with large **negative** excess (−63); the long sleeve was still empty that year.

## Takeaway (for discussion)

1. There is a **partial regime footprint**: stress years 2018 and 2022 show large positive excess; strong-trend years 2019–2021 show large negative excess.
2. This is **not** yet a stable risk-appetite result: the correlation rests on nine annual points, and clear exceptions exist.
3. Safer wording: underperformance vs equal weight is **uneven across years**, concentrated in some strong up years, while two down years produced meaningful outperformance. Treat that as a hypothesis for daily/weekly tests (drawdown quantile or trend state × rules−b2), not as a settled claim from yearly bars.

## Table (same as CSV)

| year | excess_vs_b2 | mkt_ret | mkt_maxdd | n_kept_L | n_kept_S |
|------|-------------:|--------:|----------:|---------:|---------:|
| 2010 | −16.0 | +12.9% | −16.6% | 0 | 0 |
| 2011 | 0.0 | −1.1% | −20.1% | 0 | 1 |
| 2012 | −0.7 | +12.4% | −10.5% | 0 | 1 |
| 2013 | +0.1 | +29.7% | −6.3% | 0 | 1 |
| 2014 | +35.7 | +12.1% | −9.4% | 0 | 1 |
| 2015 | −62.9 | −0.3% | −11.8% | 0 | 1 |
| 2016 | −51.1 | +9.9% | −10.7% | 0 | 3 |
| 2017 | −8.8 | +20.2% | −2.9% | 0 | 2 |
| 2018 | **+118.3** | **−6.0%** | −20.3% | 4 | 2 |
| 2019 | **−51.8** | **+28.3%** | −6.9% | 5 | 4 |
| 2020 | −33.6 | +15.1% | −33.7% | 7 | 4 |
| 2021 | **−26.8** | **+27.3%** | −5.9% | 8 | 4 |
| 2022 | **+54.9** | **−19.7%** | −24.5% | 8 | 4 |
| 2023 | +17.7 | +24.3% | −10.1% | 9 | 4 |
| 2024 | +70.2 | +23.1% | −8.0% | 9 | 5 |
| 2025 | −9.1 | +16.6% | −17.5% | 9 | 5 |
| 2026 | +38.7 | +12.7% | −8.8% | 9 | 5 |
