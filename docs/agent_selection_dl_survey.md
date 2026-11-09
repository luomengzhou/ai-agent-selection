# Agent Selection：深度学习与经典选管理人调研

> **文档性质**：调研备忘（survey），供后续 comprehensive 阶段参考。  
> **调研 ≠ 本阶段实现**：本文梳理问题映射、经典特征与 DL 路线，不要求立刻训练完整深度模型。

---

## 0. 项目背景（本仓库数据）

| 项 | 说明 |
|---|---|
| 标的 | 单一股指期货产品 |
| Agent 池 | 70 个（45 long / 25 short） |
| 粒度 | 约每文件 154 万行、5 分钟 bar |
| 原始列 | `timestamp`, `price`, `cum_ot_pnl` |
| 分析变量 | `bar_pnl = diff(cum_ot_pnl)`（**绝对美元增量**，不是 return） |
| 项目目标 | **用户自定义规则挑选 agent**；不是反推各 agent 的交易规则；也不是先上完整 DL 训练流水线 |

下文把业界「选 CTA / 选对冲基金」与「金融序列 DL」文献映射到上述设定。

---

## 1. 问题映射：Manager / Agent Selection vs 价格预测

本项目的核心任务更接近 **multi-manager / agent selection**（从候选池中挑组合构件），而不是对标的价格做 next-bar 预测。

| 维度 | 价格预测（price / return forecasting） | Agent / Manager Selection（本项目） |
|---|---|---|
| 输入对象 | 单一（或少数）价格序列 | 多条 agent 的 PnL 路径（以及可选的共同价格） |
| 输出 | 下一期收益 / 方向 / 仓位 | 「选谁、如何加权、是否进池」 |
| 评价 | 预测误差、信号 IC | 组合层面的风险调整收益、回撤、相关结构、危机表现 |
| 主要风险 | 过拟合噪声、lookahead | **全样本挑 Sharpe**、幸存者偏差、相关扎堆、regime 漂移 |
| 与本数据的对应 | `price` 可用于共同市场状态特征 | 主信号是各 agent 的 `bar_pnl` 时间序列 |

**要点**：

1. **不要把问题做成「预测标的下一根 bar」再间接挑 agent。** 更直接的是：对每条 agent PnL 路径做表征 → 排序 / 聚类 / 规则筛选 → 组合 fit。
2. 业界 CTA 选管理人的常见陷阱（软因素、追逐近期冠军）在本项目同样适用：70 个 agent 的全样本排名极易过拟合；必须 **walk-forward** 与 **组合层面** 指标。
3. 深度模型在文献中常出现在两条链上：（a）直接学仓位 / 组合权重；（b）先学 embedding 再做截面排序。对本课程阶段，**(b) + 手工特征表 + 用户规则** 更贴目标；端到端仓位网络属于后续可选。

---

## 2. 业界经典手工特征（CTA / HF 选管理人）

以下特征在 CTA FoF、托管期货与对冲基金筛选中长期使用。对本项目，把「管理人月度净值」换成 **agent 的 5min `bar_pnl`（及聚合后的日/周/月 PnL）** 即可。

### 2.1 风险调整收益

- **Sharpe / Sortino / Calmar**：均值–波动、下行波动、回撤维度的风险调整。
- **注意**：在 5min 绝对美元 `bar_pnl` 上算 Sharpe 时，需固定年化约定（例如按活跃 bar 数或交易日），并与 **波动目标 / 名义本金** 说明清楚；跨 agent 比较前建议统一尺度。

### 2.2 高阶矩与路径形状

- **偏度（skew） / 峰度（kurtosis）**：趋势策略常呈正偏、厚尾；均值回复类可能负偏。
- **回撤路径**：Max Drawdown (MDD)、回撤持续时间、水下曲线（underwater）、Ulcer Index 等。
- **盈亏不对称**：Gain-to-Pain、利润因子、胜率×盈亏比（在 bar 或交易日聚合层）。

### 2.3 Crisis alpha / 状态条件表现

- 在「风险资产大跌 / 波动飙升」窗口内的条件收益，是 CTA 叙事核心之一（crisis alpha）。
- 对本数据：可用标的 `price` 的大幅下跌段、已实现波动分位数、或外部宏观/股指危机窗，计算各 agent 的 **条件累计 `bar_pnl`**。
- 文献与实务警告：危机表现不稳定，且 **事后定义危机窗口** 会引入 hindsight；应用扩展窗或预注册危机定义。

### 2.4 相关结构与组合 Fit

- **两两相关 / 滚动相关**：避免选一堆高度同质的 long agent。
- **对基准 / 对等权池的 beta**：边际贡献（incremental Sharpe）、相关性惩罚。
- **Diversification ratio / 主成分占比**：组合是否被少数因子主导。
- CTA 实务强调：多管理人比单冠军更稳；追逐近期 Top-1 往往样本外最差（见 References 中 survivorship / hindsight 讨论）。

### 2.5 波动标准化与可比较性

- CTA 经典做法：仓位按波动缩放（vol targeting），使不同波动水平的策略可比较。
- 本项目建议：
  - 对 `bar_pnl` 做滚动 σ 标准化，得到近似「单位风险贡献」序列；
  - 或报告 **单位波动的累计 PnL / Sharpe**；
  - Long / Short 子池分开统计，再谈跨侧对冲。

### 2.6 活跃度与样本质量（本数据特有）

- 许多 bar 可能 `bar_pnl ≈ 0`（未交易或无敞口）。应构造 **activity mask**（如 `|bar_pnl| > ε` 或滚动活跃比例）。
- 特征应在「活跃样本」与「全样本」两套口径下报告，避免「大量零 bar 人为压低波动 → 虚假高 Sharpe」。

### 2.7 选管理人时的方法论陷阱（与特征同等重要）

- **软因素不可靠**：团队规模、PPT、品牌、技术叙事等对未来风险调整收益几乎无预测力（SEB「10 Fallacies」）。
- **追逐近期业绩**：全样本或 trailing 冠军的样本外衰减；幸存者偏差夸大可重复性（Alpha Architect / Handy–Meksi 相关讨论）。
- **可操作结论**：硬指标 + 子风格分类 + **相对客户组合的增量价值**，优于故事与全历史排名。

---

## 3. 深度学习常见路线

每条：**思路 → 为何与本项目相关 → 局限**。再次强调：调研 ≠ 本阶段必须实现。

### 3.1 序列表示学习 / Embedding → 聚类或排序

**思路**  
用 LSTM、PatchTST、VSN+LSTM、xLSTM 等对（多资产或单序列）窗口做表征 \(h_t\)，再：

- 对每个 agent 在固定窗口上取 embedding，做聚类（风格桶）或最近邻；
- 或接一个小头做截面打分 / learning-to-rank。

Oxford 大规模金融序列基准（Saly-Kaufmann et al.）表明：在 Sharpe 优化设定下，**擅长学时间表征的混合结构**（如 VSN+LSTM）往往优于泛化 Transformer；评价需覆盖下行风险、成本盈亏平衡、随机种子稳健性，而不仅是平均收益。

**为何相关**  
本项目有 70 条长序列 `bar_pnl`：embedding 可把「路径形状、活跃模式、波动结构」压成可比较向量，服务于用户规则（例如「与已选池相关 < 0.3 且危机窗为正」）。

**局限**

- 金融 SNR 低，表征易记噪声；
- 5min 超长序列需 patch / 降采样 / 日聚合，否则算力与过拟合并存；
- 本阶段若无清晰标签（何为「好 agent」），无监督 embedding 更稳妥，监督排序需谨慎定义标签与 walk-forward。

### 3.2 端到端组合 / 仓位网络（Deep Momentum / Deep Inception）

**思路**

- **Deep Momentum Networks (DMN)**：在波动缩放框架内，网络直接输出仓位，用 **负 Sharpe（可加 turnover 正则）** 训练，同时学趋势估计与仓位大小。
- **Deep Inception Networks (DIN)**：从收益矩阵同时抽 TS / CS 特征，对整组合输出仓位，优化组合 Sharpe，并平衡换手与跟市场高相关。

**为何相关**  
若把 70 个 agent 的 `bar_pnl` 视为「多资产收益面板」，DIN/DMN 类框架在形式上就是 **端到端 agent 配置**。文献证明「直接优化组合风险调整目标」比先 MSE 再启发式仓位更一致。

**局限**

- 与本课程目标不完全一致：用户要的是 **可解释、可改的选规则**，不是黑箱每日重配；
- 需要仔细处理成本、约束、long/short 边界；
- 小截面（N=70）+ 非平稳时，端到端极易过拟合；更适合 comprehensive 后期实验，而非第一阶段。

### 3.3 截面 ML 选基金（收益衍生特征 + DNN）

**思路**  
Wu et al.（*Management Science*）对冲基金截面预测：从历史收益构造 idiosyncratic 特征，用 LASSO / RF / GBDT / **DNN** 做截面预测与选基；发现截面框架常优于纯时间序列回归，DNN 总体较强；收益衍生特征与宏观衍生特征结合最好。

**为何相关**  
这是与本项目 **最同构** 的学术路线：

1. 每个 rebalance 日，对每个 agent 算 trailing 特征（Sharpe、偏度、回撤、相关、活跃度、危机窗…）；
2. 预测下一期相对表现或直接排序；
3. 选 Top-k 或优化权重。

**局限**

- 标签定义（下期收益 / 下期 Sharpe / 相对等权超额）强烈影响结论；
- 对冲基金月频 ≠ 5min bar：需先聚合，并处理 activity mask；
- 无真实「下架 agent」时，幸存者偏差较轻，但仍有 **多重比较与全样本调参** 风险。

### 3.4 多管理人偏好学习 / RL

**思路**

- **Preference learning + TD3** 类多管理人组合：用偏好或排序信号塑造奖励，再用深度 RL（如 TD3）学配置策略（Towards AI 实践向综述/教程）。
- **Cafe-GCN**：频域嵌入降噪 + 上下文多尺度时序 + 多关系 GCN，在 DRL 下直接输出组合权重，针对低 SNR 与时空依赖。
- **DSCRL**：双流（时序动态 + 资产相关）+ 去噪 + DPG 决策头，直接优化连续权重。

**为何相关**  
「多 agent 配置」与「多资产组合 RL」形式相同；偏好学习特别贴近 **用户自定义规则**——规则可编码为偏好对或约束奖励。

**局限**

- RL 样本效率差、奖励 hacking、回测过拟合常见；
- GCN 多关系假设（行业/板块邻接）在「同一标的上的 70 agent」上需重定义（例如按相关图、long/short 边）；
- 工程与调参成本高，不适合作为本阶段主路径；可作 comprehensive 对照实验。

### 3.5 金融目标直接优化（Sharpe / PnL / MDD Loss）

**思路**  
Khubiyev et al. 系统讨论：用 Sharpe、PnL、MDD 等 **finance-grounded loss** 替代 MSE，并加入 turnover 正则，使训练目标与交易评价对齐；DMN/DIN 亦属同一哲学。

**为何相关**  
若后续训练任何打分网络或仓位头，应用风险调整 / 路径依赖目标，而不是只最小化 `bar_pnl` 预测 MSE。

**局限**

- Sharpe/MDD 类目标对 batch、窗口长度、数值稳定敏感；
- 优化高 Sharpe 不等于样本外稳健；仍需 walk-forward 与成本压力测试；
- 本阶段无强制训练需求时，可把这些目标 **先用于评价与规则打分**，不必先做成可微 loss。

### 3.6 （可选）高频 / 不规则序列的异常与表示

**思路**  
高频或不规则采样序列上：掩码建模、异常检测、事件稀疏表示、频域滤波（Cafe-GCN 的 FEB 即一例）用于降噪与多尺度分离。

**为何相关**  
5min `bar_pnl` 高度稀疏、间歇活跃；activity mask、异常尖峰（数据错误 vs 真实大 PnL）、多时间尺度聚合都是数据层必做项。

**局限**  
纯异常检测不直接等于「好 agent」；需与经济意义指标绑定，避免把偶发尖峰当 alpha。

---

## 4. 映射到本数据集的建议

### 4.1 核心对象

- 主序列：`bar_pnl_i,t = cum_ot_pnl_i,t - cum_ot_pnl_i,t-1`
- 辅助：`price_t`（共同市场状态）、long/short 标签、activity mask \(m_{i,t}\)

### 4.2 特征与评价口径

1. **先聚合再比**：5min → 小时 / 日 / 周，再算 Sharpe、回撤、相关；5min 原始 Sharpe 仅作辅助。
2. **双口径**：全 bar vs 仅 `m_{i,t}=1` 的活跃 bar。
3. **组合 fit**：报告单 agent 指标时，同步报告相对「等权已选池」的增量 Sharpe / 相关。
4. **Crisis / regime 切片**：用 `price` 下跌分位或波动分位定义状态，算条件表现；定义写死在配置里，避免事后挑窗。

### 4.3 验证协议（强制思维）

- **Walk-forward**：滚动或扩展窗；在窗内只允许用当时可得信息选 agent，窗外评估。
- **禁止主结论只报全样本 Sharpe 排名。**
- 记录：种子（若有模型）、超参、选池规则版本；对比「等权 70」「等权 long」「随机子集」等朴素基线。
- 成本与换手：即使 agent 已是成交后 PnL，**再配置层**（调入调出 agent）仍有机会成本与滞后，应用决策滞后 1 个 bar/日。

### 4.4 与 DL 文献的取舍（对本阶段）

| 优先级 | 做法 | 理由 |
|---|---|---|
| P0 | 手工特征表 + walk-forward 规则选池 | 对齐「用户定规则」；可解释、可改 |
| P1 | 相关聚类 / PCA 风格桶 | 控制同质化，服务组合 fit |
| P2 | 轻量 embedding（日频序列上的小型 LSTM/TCN） | 为后续排序或规则提供相似度 |
| P3 | 截面 DNN / Sharpe-loss 小模型 | 对照实验，非默认交付 |
| P4 | DIN/DMN、Cafe-GCN、DSCRL 级端到端 RL | 研究扩展，非课程主线 |

---

## 5. 建议的分阶段路线

> 目标始终是：**支撑用户自定义选 agent 规则**；DL 是可选增强，不是第一交付物。

### Phase A — 轻量 EDA（本阶段主战场）

- 校验 `cum_ot_pnl` 单调性 / 重置、缺失、异常跳变；
- 分布：`bar_pnl` 稀疏度、活跃比例、long vs short；
- 路径图：累计 PnL、回撤、滚动波动；
- 粗相关热图与层次聚类；
- 输出：数据字典 + 已知陷阱清单（零 bar、尺度、极值）。

**验收**：能回答「哪些 agent 几乎不活跃？哪些高度共线？全样本 Top Sharpe 是否集中在同一簇？」

### Phase B — 特征表（规则引擎的输入）

对每个 agent × 每个 rebalance 日，生成 trailing 特征，例如：

- 收益/风险：mean PnL、vol、Sharpe、Sortino、MDD、Calmar；
- 形状：skew、kurt、水下时间；
- 状态：高波动/下跌市条件 PnL；
- Fit：与池内平均相关、与标的收益相关；
- 活跃：活跃 bar 比例、平均活跃间隔。

**验收**：一张可 join 的 panel 表 + 用 2–3 条示例规则（如「Sharpe>θ 且 max corr<ρ 且危机窗 PnL>0」）跑通 walk-forward。

### Phase C —（以后）Embedding

- 在日频（或小时）`bar_pnl` 上训练小型序列编码器；
- 用途：风格聚类、多样性约束、异常 agent 检测、规则中的「距离」特征；
- 对比：手工特征距离 vs embedding 距离。

**验收**：embedding 聚类与相关聚类大体可解释；不要求交易超额。

### Phase D — 用户自定义选规则（产品形态）

- 规则 DSL 或配置文件：阈值 + 约束（相关性、long/short 配额、换手上限）；
- 回测报告：样本外权益、回撤、与等权基线对比、敏感性（θ、ρ）；
- 可选：用截面模型或偏好学习 **建议** 规则参数，但仍由用户确认。

**验收**：换规则不改训练代码即可复跑；主结论全部来自样本外。

---

## 6. References

每条含可点击完整 URL。必列源已全部纳入；其后为可选补充。

### 必列文献 / 来源

1. Saly-Kaufmann, A., Wood, K., Calliess, J.-P., & Zohren, S. (2026). *Deep Learning for Financial Time Series: A Large-Scale Benchmark of Risk-Adjusted Performance*.  
   https://arxiv.org/html/2603.01820

2. Liu, T., Roberts, S., & Zohren, S. (2023). *Deep Inception Networks: A General End-to-End Framework for Multi-asset Quantitative Strategies*.  
   https://arxiv.org/html/2307.05522

3. Wu, W., Chen, J., Yang, Z. (Ben), & Tindall, M. L. (2020/2021). *A Cross-Sectional Machine Learning Approach for Hedge Fund Return Prediction and Selection*. *Management Science*.  
   https://doi.org/10.1287/mnsc.2020.3696

4. Towards AI. *Preference Learning and Deep Reinforcement Learning (TD3) for Multi-Manager Portfolio Strategy*.  
   https://pub.towardsai.net/preference-learning-and-deep-reinforcement-learning-td3-for-multi-manager-portfolio-strategy-5eaee64a7bc3

5. Khubiyev, K., Semenov, M., Podlipnova, I., & Khubieva, D. (2025). *Finance-Grounded Optimization For Algorithmic Trading*.  
   https://arxiv.org/html/2509.04541v2

6. SEB Global Quant Team. *10 Fallacies When Selecting CTAs*. *The Hedge Fund Journal*.  
   https://thehedgefundjournal.com/10-fallacies-when-selecting-ctas/

7. Swedroe, L. (综述 Handy & Meksi 等). *Hindsight and Survivorship Biases in Managed Futures*（Alpha Architect）.  
   https://alphaarchitect.com/survivorship-biases/

8. Liu, R., Huang, H., Ruf, J., Liu, H., & Wu, Q. (2025). *Context-Aware Frequency-Embedding Networks for Spatio-Temporal Portfolio Selection*（Cafe-GCN）. SIAM SDM.  
   https://researchonline.lse.ac.uk/id/eprint/126929/3/CAFE_GCN_for_SIAM_DM.pdf

9. *A Novel Portfolio Selection Method via Deep Reinforcement Learning*（DSCRL）. *Systems* 14(3), 292.  
   https://www.mdpi.com/2079-8954/14/3/292

### 可选补充

10. Lim, B., Zohren, S., & Roberts, S. (2019). *Enhancing Time Series Momentum Strategies Using Deep Neural Networks*（Deep Momentum Networks）.  
    https://arxiv.org/html/1904.04912v3

11. Clenow, A. F. *Following the Trend: Diversified Managed Futures Trading*（CTA / 趋势跟踪实务框架）. Wiley 产品页：  
    https://www.wiley.com/en-us/Following+the+Trend%3A+Diversified+Managed+Futures+Trading-p-9781118410844

12. Clenow / Following the Trend — CTA 系统概述（公开说明页）：  
    https://www.followingthetrend.com/the-trading-system/

13. Wood, K., Giegerich, S., Roberts, S., & Zohren, S. 相关工作见 Momentum Transformer 等（可由 DMN/DIN 文献内引用链继续追踪）：  
    https://arxiv.org/html/2307.05522

---

## 7. 一页纸结论（给后续 comprehensive）

1. **问题是 agent selection / 组合 fit，不是标的价格预测。**  
2. **先做 EDA + 特征表 + walk-forward 规则**；DL embedding / 截面 DNN / Sharpe-loss / RL 按需后置。  
3. **主指标不要只看全样本 Sharpe**；必须看相关结构、危机/高波动条件表现、活跃度口径与样本外衰减。  
4. 文献最直接可迁移的是：**截面收益衍生特征 + ML（Wu et al.）** 与 **风险调整目标对齐（DMN/DIN / finance-grounded loss）**；端到端 RL（Cafe-GCN、DSCRL）作进阶对照即可。

---

*文档维护：Sauma Capital 课程项目调研笔记。实现细节以仓库代码与 comprehensive 阶段计划为准。*
