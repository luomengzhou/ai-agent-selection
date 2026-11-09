# Sauma EDA — 指标算法说明

本文记录**当前本地脚本实际在算什么**。代码入口。所有 `outputs_eda_*/` 目录均为本地产物（逐 agent 统计、累计 PnL 图、session 窗口、标的鉴定），**不随仓库发布**；仓库内仅保留池级汇总：[`eda_aggregate_results.md`](eda_aggregate_results.md)。

| 脚本 | 作用 | 主要输出 |
|------|------|----------|
| [`eda_mini_light.py`](../eda_mini_light.py) | 对齐、缺口、零值、每 agent 矩/Sharpe | `outputs_eda_light/time|features/{figs,raw}/` |
| [`eda_trade_frequency.py`](../eda_trade_frequency.py) | 活动次数/频率、共时 | `outputs_eda_light/time/{figs,raw}/` |
| [`eda_feature_cross_section.py`](../eda_feature_cross_section.py) | 70 人特征的横截面分布（旧全网格表） | `outputs_eda_light/features/`（旧口径归档） |
| [`eda_session_features.py`](../eda_session_features.py) | **方案 C**：仅每日固定 session 窗口上重算矩/Sharpe | `outputs_eda_light/features/`（小表在根；图→`figs/`；agent 表→`raw/`） |
| [`eda_underlying_fingerprint.py`](../eda_underlying_fingerprint.py) | 本地日末价对齐 Yahoo 候选连续期货合约，鉴定标的（结果不发布） | `outputs_eda_light/underlying/` |
| [`eda_hold_spell_vs_market.py`](../eda_hold_spell_vs_market.py) | 持仓窗内 PnL vs **同向** dead-hold ±4（边界与 `bar_pnl` 对齐；无反向 sleep-long） | `outputs_eda_light/hold_spell_vs_market/`（Nasdaq：`outputs_eda_nasdaq_*/hold_spell_vs_market/`） |

**输出布局（三套数据一致）**：每个主题目录 = 人眼层（`README` + 小表 + `figs/`）+ `raw/`（一屏看不完的 CSV）。三套根目录 `outputs_eda_*/` 对应主数据集与另外两个数据切片（148 / 103 个 agent，session 窗口不同），全部 git-ignore。

**选人研究协议（尚未实现）**：[`agent_selection_rules_zh.md`](agent_selection_rules_zh.md) / [`agent_selection_rules_en.md`](agent_selection_rules_en.md)。协议区分文献方法、外部先验、项目假设与人为参数，并规定 point-in-time universe 和 pseudo-OOS 验证。

复跑：

```bash
cd "Sauma Capital"
.venv/bin/python eda_mini_light.py
.venv/bin/python eda_trade_frequency.py
.venv/bin/python eda_feature_cross_section.py   # 旧全网格横截面
.venv/bin/python eda_session_features.py      # 推荐：session-only
```

---

## 0. 方案 C（推荐主表）：session-only

经验事实：全部非零 `bar_pnl` 落在工作日一段**固定的日内 session 窗口**内（含端点；具体时刻由数据方给定，不在仓库中公开）。

主输出：`features/raw/eda_light_summary_session.csv`（人眼先看 `features/figs/` + `top_bottom_sharpe_session.csv`）

| 列前缀 | 窗口 |
|--------|------|
| `from_first_*` | 只保留 session bar；再从该 agent 首次非零起算到末（session 内的 0 仍计入） |
| `full_grid_*` | 只保留 session bar；**全员同一日历**（晚启动前面为 0） |

Sharpe 年化：`bars_per_year_est ≈ n_session_bars / (span_days/365.25)`（约几千，不是 ~74531）。

旧表 `features/raw/eda_light_summary.csv`（24h 网格、含盘外 0）保留对照，**读数请优先看 session 表**。

特征图文件名与口径演进记录随本地输出目录一起保存（`outputs_eda_light/features/FIGURES_AND_DATA_EVOLUTION.md`，不入库）。  
口径变更后务必重跑 `eda_session_features.py` 再生图。

---

## 1. 原始字段与 `bar_pnl`

每个 parquet：`timestamp`, `price`, `cum_ot_pnl`。

\[
\texttt{bar\_pnl}[0] = 0,\quad
\texttt{bar\_pnl}[t] = \texttt{cum\_ot\_pnl}[t] - \texttt{cum\_ot\_pnl}[t-1]\ (t\ge 1)
\]

含义：该 5 分钟 bar 上累计 PnL 的**美元增量**（不是收益率）。

**活动 bar / 非零 bar**：`bar_pnl != 0`。

---

## 2. `eda_light_summary` 里的 mean / std / skew / kurtosis / Sharpe

### 样本窗口（重要）

**不是**「只在有交易的 bar 上算」。

对每个 agent：

1. 找**首次** `bar_pnl != 0` 的下标 `first_i`
2. 取片段：`seg = bar_pnl[first_i : ]`  
   → 从首次出手起，一直到**整条序列结束**（含之后所有 `bar_pnl == 0` 的 bar：盘外、周末网格、未出手时段等）
3. 去掉非有限值后，在 `seg` 上算样本矩

因此：

- `n_bars_valid_segment` = 该片段长度（通常几十万），**远大于**活动次数（通常几千）
- `bar_pnl_mean` 会被大量 0 **严重拉向 0**
- `bar_pnl_std` / skew / kurtosis 也是在「稀疏散点 + 大量 0」的混合分布上算的

若改成「只在 `bar_pnl != 0` 的 bar 上算」，数字会完全不同；**当前表没有这一列**，需要的话另加脚本。

### 各统计量（pandas / numpy）

设片段为 \(x_1,\ldots,x_n\)（`seg`）：

| 列名 | 算法 |
|------|------|
| `bar_pnl_mean` | \(\bar x = \frac{1}{n}\sum x_i\)（`numpy.mean`） |
| `bar_pnl_std` | 样本标准差，`ddof=1`：\(\sqrt{\frac{1}{n-1}\sum(x_i-\bar x)^2}\) |
| `bar_pnl_skew` | `pandas.Series.skew()`（偏度，Fisher 校正的样本偏度） |
| `bar_pnl_kurtosis_excess` | `pandas.Series.kurt()`（**超额**峰度；正态为 0） |
| `final_cum_ot_pnl` | 全序列最后一个 `cum_ot_pnl`（与片段无关） |
| `zero_bar_share_full` | 全序列上 `(bar_pnl==0).mean()`（从文件开头算，不只片段） |

### Sharpe（`sharpe_simple`）

\[
\texttt{sharpe\_simple} = \frac{\texttt{bar\_pnl\_mean}}{\texttt{bar\_pnl\_std}} \times \sqrt{B}
\]

其中 \(B =\) `bars_per_year_est`，由**基准时间轴**（全体共用）估计：

\[
B = \frac{N_{\text{bars, full}}}{\text{span\_calendar\_days}/365.25}
\]

即：全样本约 154 万根 bar ÷ 日历年跨度 ≈ **74531 bar/年**（不是 252 交易日）。  
无风险利率按 0。这是**简易年化**，分母仍是「含大量 0 的片段 std」。

---

## 3. 活动 bar / 频率（`eda_trade_frequency.py`）——旧口径

这里统计的是 **nonzero PnL bar，不是真实交易次数**：

| 列名 | 算法 |
|------|------|
| `n_active_bars` | 全序列 `count(bar_pnl != 0)` |
| `first_active_ts` / `last_active_ts` | 首次 / 末次非零时间戳 |
| `active_span_years` | \((t_{\text{last}}-t_{\text{first}}) / (365.25\times 86400)\) 秒 |
| `trades_per_year` | **旧列名有误导性**：实际为 `n_active_bars / active_span_years`，不是 entry/year |
| `avg_days_between_trades` | **旧列名有误导性**：实际为 `active_span_days / n_active_bars` |

共时：把活动 bar 按「星期×小时」打成 7×24 直方图，agent 两两 **cosine 相似度**（忽略 PnL 符号）。

真实 entry 应由推断仓位 \(0\rightarrow \pm4\) 定义；一次近乎整段 session 的持仓通常产生约二十来个 nonzero PnL bars。后续选人规则不得使用上述旧列作为交易次数。

---

## 4. 零值日历与缺口（`eda_mini_light.py` → `time/`）

| 输出 | 算法要点 |
|------|----------|
| 对齐 | 全体 timestamp SHA256 / `array_equal`；`price` 相对基准 agent 全量相等 |
| `gap_summary` | 相邻 timestamp 的 \(\Delta t\)（秒）分位数；`>5min` 长缺口计数 |
| `gap_by_weekday_hour` | 长缺口终点的 weekday×hour |
| `agent_activity` | `first/last_nonzero`、全序列 `zero_bar_share`、最长连续零 run |
| `zero_calendar` | 每个日历日：各 agent 当日零 bar 占比平均；当日是否「该 agent 全天全零」再跨 agent 计数 |

`n_bars` 按**自然日**切：周日≈71、周五≈205、周一–周四≈288（期货会话），不是异常。

---

## 5. 横截面特征 EDA（`eda_feature_cross_section.py`）

输入：`eda_light_summary.csv`（已是每 agent 一行）。

对每一列特征（如 `bar_pnl_mean`），在 **70 个 agent** 上再算 mean / std / 分位数，以及 long vs short 的 mean。  
这是「特征的分布」，不再回到原始 5 分钟序列。

---

## 6. 口径对照（避免混）

| 问题 | 当前答案 |
|------|----------|
| mean/std/skew 除以的是「有交易的 bar」吗？ | **否**。从首次非零到文件末尾的**所有 bar**（含海量 0） |
| 频率 `trades_per_year` 呢？ | 它按非零 PnL bar 计数，**不是交易频率**；一次真实交易是当日仓位 \(0\rightarrow\pm4\)，并在当日 session 内平仓 |
| 当前主矩是否只留 session？ | **是**。`eda_session_features.py` 主表只保留 session 窗口内的 bar；旧全网格表仅对照 |
| flat 是什么？ | agent 当日没有下单；是否 flat 看整段 session 的推断仓位，不能只凭单根或日 PnL=0 |

---

## 7. 已知局限（读表时心里有数）

1. 片段含大量 0 → mean≈0、Sharpe 解释需谨慎。  
2. 短样本晚启动 agent 与长历史 agent 直接比全样本矩不公平（见 `ta_questions.md` Q1）。  
3. Sharpe 年化因子按全网格密度，与「只在 session 窗口内活动」的经济含义不完全对齐。
4. `eda_sharpe_dd_persistence.py` 与 `eda_agent_corr_session.py` 当前先裁 session 再按日 `diff()`，会把每天 session 首根 PnL 置 0；正式验证前须改为“完整时间轴先 diff，再裁 session”。
5. 单根 `Δprice=0` 时仓位不可识别，但可用当日其他价格变动 bar 判断该日 trade/flat；若整段 session 价格完全不动则排除该日。forward-fill 仍是近似，不是订单真值。
6. 首次观测持仓不一定等于官方 launch date；缺少 point-in-time launch/retire universe 会带来 survivorship/incubation bias。
7. 点值、交易成本、滑点和资本占用尚未确认；当前组合只能称 PnL-unit portfolio。
8. 现有完整历史已参与读图与规则构思，未来在这段历史上的 walk-forward 只能称 pseudo-OOS。
