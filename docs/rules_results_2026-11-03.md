# 选人规则第一轮结果（2026-11-03，汇报用）

数据：主数据集，70 个 agent（45 long / 25 short），固定日内 session 窗口（具体时刻不公开），2006-01 到 2026-10-02。  
代码：`agent_selection_rules.py`（主规则）、`agent_selection_diagnostics.py`（消融 + 随机对照）、`agent_selection_experiments.py`（两个修正方向）。  
规则定义见 `docs/agent_selection_rules_zh.md`。

## 完整结果文件（不要只看本 MD）

`agent_selection_rules.py` 本轮全部产出已导出到 [`rules_results_2026-11-03/`](rules_results_2026-11-03/)。**注：`raw/` 下的日频 / 逐 agent CSV 只保留在本地，不随仓库发布**（含逐 agent 日度 PnL）；下表中 `raw/` 条目仅作说明：

| 文件 | 内容 |
|------|------|
| [`concat_path_stats.csv`](rules_results_2026-11-03/concat_path_stats.csv) | 拼接 OOS 路径总 PnL / Sharpe / maxDD / Calmar |
| [`yearly_table.csv`](rules_results_2026-11-03/yearly_table.csv) | 逐年 pool/kept、各路径 PnL/Sharpe、相对 b2 超额 |
| [`summary.txt`](rules_results_2026-11-03/summary.txt) | 同上文字版 + 冻结的 D 参数 |
| `raw/oos_daily_paths.csv` | 日频 OOS PnL（rules / b1 / b2）+ 市场 close |
| `raw/selection_by_year.csv` | 每年每个候选 agent 的特征、分数、聚类、是否入选 |
| `raw/yearly_excess_vs_market.csv` | 逐年超额 vs 市场收益/回撤（仅本地） |
| [`figs/`](rules_results_2026-11-03/figs/) | 累计曲线（含 R1…R6 单规则虚线）、逐年超额柱状图 |
| `raw/oos_daily_paths_with_single_rules.csv` | 主路径 + 单规则日频 PnL |
| [`single_rule_path_stats.csv`](rules_results_2026-11-03/single_rule_path_stats.csv) | 单规则拼接路径指标 |
| `note_excess_vs_market_{zh,en}.md` | 超额 vs 市场好坏附注（含标的逐年收益，仅本地，不入库） |

诊断与修正方向（另两支脚本）仍在 `outputs_rules_light/diagnostics.txt` 与 `outputs_rules_light/experiments/`。  
日常复跑默认仍写 `outputs_rules_light/`（字段与上表相同）。

---

## 1. 一句话结论

按"规则定死、每年只用过去数据选人"的方式，六条规则选出的组合**没有打败分轨等权**，而且**不比随机选同样人数更好**。两个修正方向（改 R1、改成"剔坏的"）也都没有产生增量。

---

## 2. 我们定的样本外口径

- **Walk-forward，每年重选**：每年第一个交易日之前，只用此前全部数据算分、选人，持有一年。2010 到 2026 共 17 段，接成一条连续曲线再算指标。
- **规则不从数据里学**：所有阈值事先写死（见 `summary.txt` 末尾的 D 参数），不在历史上调。
- **诚实标注**：规则是看完整段历史的图之后想出来的，所以这只能叫 pseudo-OOS。真正的 OOS 要等 2026-10 之后的新数据。
- **主基准**：分轨等权 = 50% 全体 long 等权 + 50% 全体 short 等权，与规则组合唯一的区别是"有没有挑人"。

---

## 3. 结果摘要

拼接 OOS 路径，2010–2026（日 PnL，Sharpe 年化）。**完整数字以 [`concat_path_stats.csv`](rules_results_2026-11-03/concat_path_stats.csv) / [`yearly_table.csv`](rules_results_2026-11-03/yearly_table.csv) 为准。**

| 组合 | 总 PnL | Sharpe | 最大回撤 | 赢基准的年数 /17 |
|---|---|---|---|---|
| 分轨等权（基准） | 1320 | **1.61** | 92 | – |
| 规则 v0（六条规则原版） | 1395 | 0.80 | 215 | 7 |
| 随机选同样人数（300 次中位数） | – | 1.12 | – | – |
| 方向 A：R1 改相对口径 | 1463 | 1.03 | 108 | 10 |
| 方向 B：等权但剔除 R2 最差 20% | 1305 | 1.60 | 95 | 4 |
| 随机剔除 20%（300 次中位数） | – | 1.60 | – | – |

- 规则 v0 落在随机选法的第 **5–8** 分位：比随机还差。
- 方向 A 提到第 26 分位，仍低于随机中位数。
- 方向 B 与随机剔除完全重合（第 52 分位）：R2 对"谁明年会差"没有信息。
- 只看 2018 年之后（两边池子都有人）结论相同：基准 1.98，v0 1.04，A 1.38，B 1.96。

逐条规则单独用（`outputs_rules_light/diagnostics.txt`）：R1 0.80、R2 0.97、R3 0.92、R4 0.92，全部低于随机中位数 1.12。

---

## 4. 为什么不行

1. **R1 的压力日定义有缺陷。** 压力阈值用 2006 年起全历史的 20% 分位，被 2008 年大跌锚定；2012–2017 没有一天够得上压力，long 的 R1 算不出，long 轨八年空仓。改成滚动 5 年分位（方向 A）后修复，但 R1 仍无选人能力。
2. **R1 区分度极低。** agent 一年只出手约 10 次，所以"机会日出手率"人人接近 0，"压力日不出手率"人人接近 1，R1 挤在 0.43–0.54。改成相对口径后仍然没有预测力。
3. **过去的表现不预测未来。** R2（近期恶化）、R4（效率、Calmar）本质是过去业绩；之前已发现年度 Sharpe 排名相关约 −0.04。挑"过去好的"等于在噪声里挑。
4. **集中本身有代价。** 规则组合只持有约 12 个 agent，等权持有约 60 个。即使选人完全随机，Sharpe 也从 1.6 掉到 1.1，这就是分散度损失。要靠挑人补回这部分，需要规则有很强的信息，而我们没有。

这和 DeMiguel–Garlappi–Uppal (2009) 的结论一致：等权很难被打败。

### 4.1 附注：逐年超额 vs 市场（假说，未坐实）

看 [`fig_yearly_excess_vs_b2.png`](rules_results_2026-11-03/figs/fig_yearly_excess_vs_b2.png) 时的直觉：是不是牛市相对等权更差、市场不好时反而更好？

简短结论：2018 / 2022 压力年超额为大正，2019–2021 强上涨年为大负，方向有一点；但 2023/2024 大牛年超额仍为正，且 2018 起只有 9 个年点（Spearman −0.63，p≈0.07），**还不能当成稳定的 risk-appetite 结论**。

完整表与表述见本地附注 `note_excess_vs_market_{zh,en}.md` 与数据 `raw/yearly_excess_vs_market.csv`（均不入库，因为会暴露标的逐年收益）。

---

## 5. 局限

- PnL 单位、点值、成本未确认，只报 PnL 单位组合。
- 上线日用"首次出手日"代理，分不清"没上线"和"上线但没出手"。
- 2010–2017 池子很薄（long 0 人、short 1–3 人），这段的比较意义有限。
- 规则看过全历史，所有结果都是 pseudo-OOS。

---

## 6. 想请教授挑刺的三件事（按"我们定了 X，理由是 Y"的方式问）

1. **OOS 口径**：我们定为每年 walk-forward，规则事先冻结。你觉得哪里站不住？是否需要再划一段 2024 年起的冻结留出期？
2. **目标**：数据显示等权很难打败。研究目标是否可以从"选出赢家"改为"给等权组合加一层风控"（比如剔除刚爆仓的、限制单 agent 权重）？还是必须交付一个选人规则？
3. **启动日含义**：晚启动的 agent Sharpe 普遍高。它们是新上线，还是规则一直存在只是没触发？这决定"短样本高 Sharpe"是选择偏差还是行情。

---

## 7. 复跑

```bash
cd "Sauma Capital"
.venv/bin/python agent_selection_rules.py          # → outputs_rules_light/
.venv/bin/python agent_selection_diagnostics.py    # → outputs_rules_light/diagnostics.txt
.venv/bin/python agent_selection_experiments.py    # → outputs_rules_light/experiments/
```

本轮归档副本：`docs/rules_results_2026-11-03/`。
