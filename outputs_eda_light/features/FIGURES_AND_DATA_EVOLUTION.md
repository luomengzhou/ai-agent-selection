# Features 图与数据口径演进

口径变更时：**重跑脚本并更新本文件**。当前权威算法见 [`../../docs/METHODOLOGY.md`](../../docs/METHODOLOGY.md)。

---

## 当前口径（CURRENT）— 2026-10-14 起

**方案 C：`session` + `from_first`**

- Session：Mon–Fri **11:35–13:30**（含），每天 24 根 5 分钟 bar  
- 统计窗口：每个 agent 从**首次** `bar_pnl ≠ 0` 起 → 文件末，**仅 session bar**（session 内的 0 仍计入）  
- 主表：`raw/eda_light_summary_session.csv`  
- 列字典：`COLUMN_DICTIONARY_session.md`  
- 生成脚本：`eda_session_features.py`  
- 布局：人眼看根目录小表 + `figs/`；大表进 `raw/`

| 当前图文件名 | 内容 |
|--------------|------|
| `figs/fig_feature_hist_session_from_first.png` | 横截面直方图 |
| `figs/fig_feature_box_session_from_first.png` | 横截面箱线图 |
| `figs/fig_feature_scatters_session_from_first.png` | mean–std / Sharpe–终值 / skew–kurt |
| `figs/fig_cum_ot_pnl_reps.png` | 代表 agent 的**累计 PnL 曲线**（不是矩统计；路径本身） |

一眼表：`feature_cross_section_session_readme.md` / `feature_cross_section_session.csv` / `top_bottom_sharpe_session.csv`

复跑（口径或数据变了就跑）：

```bash
cd "Sauma Capital"
.venv/bin/python eda_session_features.py
```

---

## 历史口径 v0（已废弃作主结果）— ~2026-10-13

**全天 5 分钟网格 + 首次非零→末（含盘外/周末网格上的大量 0）**

- 表：`eda_light_summary.csv`（仍保留作对照，**不要当主读数**）  
- 脚本：`eda_mini_light.py` + 当时的 `eda_feature_cross_section.py`  
- 旧图文件名（已删除，避免误读）：
  - `fig_feature_hist_by_side.png`
  - `fig_feature_box_by_side.png`
  - `fig_feature_scatters.png`
  - `feature_cross_section_readme.md`（旧）

特征：`n_bars_valid_segment` 可达 \(10^5\sim10^6\)，`zero_bar_share_full` ≈ 0.996+，`bar_pnl_mean` 被盘外 0 严重稀释。

过渡文件名 `fig_feature_hist_session.png`（仅 hist、命名未写 from_first）也已删，由 `*_session_from_first.png` 取代。

---

## 变更规则（给以后的自己 / agent）

1. 换口径 → **先改脚本与 `METHODOLOGY.md`**，再重跑出图。  
2. 图文件名尽量带口径关键词（如 `session_from_first`），标题里也写一口径。  
3. 在本文件顶部「当前口径」下追加一节「历史」，写清旧文件名与旧定义。  
4. 删除或移走会误导的旧图，不要留同名旧口径文件。
