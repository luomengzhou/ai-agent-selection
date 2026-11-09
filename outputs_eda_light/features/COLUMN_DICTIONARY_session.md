# `raw/eda_light_summary_session.csv` 列字典

Session = **周一至周五、每天 11:35–13:30（含）**，共 24 根 5 分钟 bar／交易日。  
`bar_pnl` = 相邻累计 PnL 的美元增量。

脚本：`eda_session_features.py` · 总述：`docs/METHODOLOGY.md`

---

## 全员相同的两列（所以会觉得「咋一样」）

| 列名 | 是什么 | 本数据取值 |
|------|--------|------------|
| `session_bars_per_year` | **Sharpe 年化用的常数**：平均一年有多少根 session bar。`= n_session_bars_shared / (日历跨度天/365.25)`。公式里只用在 `sharpe = mean/std * sqrt(这个数)`。 | ≈ **6263.84**（70 行都相同） |
| `n_session_bars_shared` | **共享日历上 session bar 总根数**（整段历史里所有 Mon–Fri 11:35–13:30）。 | **129960**（70 行都相同） |

这两个**不是同一个量**：一个是「每年约多少根」，一个是「全样本一共多少根」。  
每人填一样，是因为时间轴共用，不是复制错了。

---

## `from_first_*` 里的 “first” 是什么

**不是**「第一根 bar 自己的 mean」。意思是：

> 从该 agent **第一次** `bar_pnl ≠ 0` 的那根 session bar 起，到文件末尾，**只保留 session bar**，再在这串序列上算统计。

| 列名 | 定义 |
|------|------|
| `from_first_n_bars` | 上述窗口里的 session bar 根数（**每人不同**：越早开跑越大） |
| `from_first_n_active` | 其中 `bar_pnl ≠ 0` 的根数 |
| `from_first_frac_bars_zero` | **零 bar 占比** = 窗口内 `bar_pnl==0` 的根数 / `from_first_n_bars` = `1 - n_active/n_bars`。分母是「首次出手之后的 session bar」，不是全天、也不是非零 bar。 |
| `from_first_bar_pnl_mean` | 窗口内 `bar_pnl` 算术平均（**含 0**） |
| `from_first_bar_pnl_std` | 同上，样本标准差（`ddof=1`） |
| `from_first_bar_pnl_skew` | 偏度 |
| `from_first_bar_pnl_kurtosis_excess` | 超额峰度 |
| `from_first_sharpe` | `(bar_pnl_mean / bar_pnl_std) * sqrt(session_bars_per_year)` |

---

## `full_grid_*`

同样只留 session bar，但**不从首次出手截断**（全员同一段日历）。晚启动前面全是 0。

---

## 其它

| 列名 | 定义 |
|------|------|
| `session` | 时段文字 |
| `first_nonzero_ts` / `last_nonzero_ts` | 首次 / 末次非零时刻 |
| `final_cum_ot_pnl` | 文件最后累计 PnL |
| `side` | long / short |
