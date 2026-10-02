# tradesys · 工作流（草案）

> 状态：讨论稿（2026-10-02），确认后作为 Phase 2 的设计依据。
> 与 `docs/DESIGN.md` 的关系：DESIGN 讲「规则怎么变成可执行的判断」；本文讲「一个买入念头怎么一步步变成决定」。工具层与 playbook 规则不因本文改变。

---

## 0. 原则（重申）

1. **尽可能简洁。** 够用即可。
2. **不增加复杂度，不增加概念，除非万不得已。** 新概念先尝试用已有概念表达；每加一个，最好同时删掉一个。
3. **Unix：靠组合，不写大而全的函数。** 小工具、纯函数、JSON 进出；文件就是接口（人、脚本、agent 都编辑同一份文本）。
4. **规则是数据，代码是工具，执行器是通用的。** 代码不出现规则 ID；换风格 = 换 playbook。
5. **不知道 = 问你。** 判定规则无法判断时不给买入结论，而是变成一个待回答的问题（「不知道等于不买」的可操作形式）。
6. **场景不进工具。** 「盘后问明天能不能买」只是用来走通流程的场景；工具不知道自己处在哪个阶段。
7. **复杂的先空着，提醒人填。** 结构、近似算法、主观判断，系统没把握的，留空并提问；将来再由确定性脚本出 proposal，人或 agent 复核。

---

## 1. 一只股票的流程

```
想法 ──→ 审查 ──→ 计划 ──→ 盯盘 ──→ 执行 ──→ 记录
```

| 阶段 | 回答 | 用到的规则 | 结果 |
| --- | --- | --- | --- |
| 想法 | 为什么想买？消息从哪来？ | 「想法理由」规则（必填） | 一句话理由 + 来源 |
| 审查 | 这只股票现在值得考虑吗？ | 上下文 V（V01–V04、V06–V11、V15、V16） | 通过 / 否决（原因）/ 待回答 |
| 计划 | 怎么买？ | 候选 V（V05、V12–V14）；S01–S09 给出建议买点 | 计划：entry / stop / target / 过期日 |
| 盯盘 | 机会来了吗？还安全吗？ | 每个盘后：S 规则作触发器，复跑机器项 | 可执行 / 暂停（原因）/ 过期 |
| 执行 | 明天开盘怎么做？ | advice（V17、V18、Band68 等） | 提醒；下单由人完成 |
| 记录 | 当时为什么这样决定？ | — | 日志一行（含不买） |

- **审查一次性做完**；盯盘期间每个盘后只复跑机器算的项。人工回答按有效期决定是否重新问。
- **同一组规则，不同阶段只是编排不同。** S 规则在「计划」里是推荐，在「盯盘」里是触发器；工具不变。
- **暂停由机器判断，作废由人决定。** 盯盘期间任一判定规则否决或未知 → 计划显示「暂停」并列出原因；否决解除后自动恢复。
- **计划有过期日**（默认 20 个交易日）。过期后显示「过期」，续期或作废由人决定；人也可以随时作废。

---

## 2. 答案从哪来

清单上每一项只有三种来源，不另设机制：

| 来源 | 例子 | 交互 |
| --- | --- | --- |
| 机器算 | V01、V04、V11、V15、V10 交易所 / 市值 | 直接给结论 |
| 人画，机器判 | 区间、趋势线、颈线、旗形（V02、V03、V12、V13、S01–S04） | 人在档案中画；缺失或过期 → 提问 |
| 人回答 | V06、V07「有无利空」、V08、V09 清单、V10b、想法理由 | 缺失或过期 → 提问 |

近似规则（V16 背离、V03 Fib、S05–S07、S09）保持现状（`trust: review`，只作参考）；过于复杂的，降级为「人回答」。将来优化算法时再升级。

---

## 3. 档案：一只股票一个文件

`data/tickers/<TICKER>.yaml`（由现在的 `data/structures/<TICKER>.yaml` 改名扩充）。人写，机器只读；agent 将来也编辑这份文件。

```yaml
ticker: AMD

idea:                          # 必填
  reason: 数据中心 GPU 订单超预期
  source: news                 # news | research | chart | impulse
  at: 2026-10-01

facts:                         # 人的回答：值 + 确认日；有效期由读取它的 rule 块决定
  v07.no_bad_news:   {value: true, at: 2026-10-01}
  v09.business:      {value: true, at: 2026-09-15}
  v09.last_earnings: {value: true, at: 2026-09-15}

zones: [...]                   # 与现在相同；confirmed_at 起 20 个交易日后视为过期，需复核
lines: [...]
absent: [...]

plans:
  - id: p1
    entry: 520
    stop: 500
    target: 600                # 可省略 → V14 提问
    at: 2026-10-01
    expires: 2026-10-29        # 省略 = at + 20 个交易日
    status: active             # active | cancelled；「暂停」「过期」由机器算，不存
```

- **watchlist = `data/tickers/` 目录里的文件。** 不另设清单。
- **计划 = 现有的 `Candidate` + 过期日 + 状态。** 进入运行时与 setup 产出的候选走同一条路（V05、V12–V14）。
- **采纳系统建议 = 把建议的 entry / stop / target 抄进 `plans`。** 不需要专门的命令。

---

## 4. 人工回答的有效期（默认值）

有效期写在读取该回答的 rule 块里（阈值写在 rule 块里，与现在一致），人可直接改 playbook。

| 回答 | 默认有效期 | 理由 |
| --- | --- | --- |
| 想法理由 | 不过期 | 计划本身会过期 |
| V09 基本面清单 | 到下次财报（无财报日则 63 个交易日 ≈ 一季度） | 基本面按财报季更新 |
| V07 无明显利空 | 1 个交易日 | 消息面变化快 |
| V06 板块跌幅前 10% | 1 个交易日 | 只针对 T 日 |
| V08 近期被止损 | 1 个交易日 | Journal 自动化前的过渡 |
| V10b 社群热度 | 5 个交易日 | 约一周 |
| 结构（区间 / 线 / absent） | 20 个交易日 | 约一个月复核一次 watchlist |

---

## 5. V09 基本面熟悉度清单

把「是否熟悉基本面」这一定性问题拆成可数的项。每项是 / 否；全部回答后，满足项数 < `min` → 否决。任一项未回答或过期 → 提问。项目可以在 playbook 中增删。

| key | 问题 |
| --- | --- |
| `v09.business` | 能用一句话说清主营业务与主要收入来源 |
| `v09.revenue_mix` | 知道最大两个业务板块的营收占比 |
| `v09.last_earnings` | 读过最近一次财报 / 电话会要点 |
| `v09.growth` | 知道最近 4 个季度营收与 EPS 的同比方向 |
| `v09.margin` | 知道毛利率趋势（升 / 平 / 降） |
| `v09.guidance` | 知道管理层最新指引 |
| `v09.competitors` | 能说出 2 个主要竞争对手 |
| `v09.catalyst` | 知道下一个催化剂或风险事件 |
| `v09.tracked` | 已跟踪该公司满 3 个月 |

默认 `min: 7`（9 项中至少 7 项），待实盘校准。

---

## 6. 对现有系统的改动（概念账）

**删去的概念**

- `kind: manual` / `kind: todo`：改为普通的 `veto` 块，用 `fact` 工具读取人的回答；块上写 `ask:` 作为未知时的提问。
- `trust: memo`：随 manual / todo 一起消失。advice 靠 `kind` 区分即可。
- 报告「规则覆盖」章节：开发者视角，移出备忘录。

**新增的概念**

- **人工回答（facts）**：值 + 确认日。由两个小工具读取：
  - `fact: {key, is, ttl}`：单个回答；缺失或过期 → None（提问）。
  - `checklist: {keys, min, ttl}`：一组回答计数；用于 V09，将来也用于估值清单。
- **计划的生命周期**：只多两个字段（`expires`、`status`），其余复用 `Candidate`。

**不变的**

- 工具层、Snapshot 取数、as_of 约束、结构判定、setup 语法、`trust: review`、advice、CLI 的 `fetch / run / report`。

示例（V09 与 V07 改写后）：

```rule
kind: veto
ask: 请填写基本面熟悉度清单（v09.*）
when:
  - checklist: {keys: [v09.business, v09.revenue_mix, v09.last_earnings, v09.growth, v09.margin, v09.guidance, v09.competitors, v09.catalyst, v09.tracked], min: 7, ttl: earnings}
```

```rule
kind: veto
ask: 是否有明显利空消息？（回答 v07.no_bad_news）
when:
  - trend: {direction: down}
  - days_to_earnings: {max: 2}
  - drop_pct: {min: 0.03}
  - volume_state: {state: expand}
  - fact: {key: v07.no_bad_news, is: false, ttl: 1}
```

---

## 7. 报告：档案视图

报告只回答「现在该做什么」，按以下顺序：

1. **结论**（一行）：先写想法理由 / 不买（原因）/ 待回答 N 项 / 审查通过，尚无计划 / 计划 p1 可执行 / 计划 p1 暂停（原因）/ 计划 p1 已过期。
2. **待回答**：每项给出要填写的 key 与提问。
3. **计划**：每个计划的状态、价格、rr、命中的 V。
4. **系统建议买点**：S 规则产出的候选（含「参考」级别），供抄入 `plans`。
5. **提醒**：advice。

---

## 8. 编排

不新增命令，现有三段管道加上档案文件即可：

```bash
tradesys fetch AMD | tradesys run playbooks/technical.md | tradesys report playbooks/technical.md

# 盯盘：对 watchlist 逐个运行
for f in data/tickers/*.yaml; do t=$(basename "$f" .yaml); tradesys fetch "$t" | tradesys run playbooks/technical.md | tradesys report playbooks/technical.md; done
```

- `fetch` 读入档案（想法、回答、结构、计划），与现在读结构一样，过滤过期项。
- **记录**：`run` 的输出追加为日志的一行（`data/journal/<TICKER>.jsonl`）。只追加，不修改；不买也记。
- 将来的 agent 做同样的事：读报告里的「待回答」，向人提问，把回答写进档案，再跑一遍。

---

## 9. Roadmap（伏笔）

- **估值清单**（下一阶段）：与 V09 同样的 `checklist` 形式，判断估值偏高或偏低；作为新的人工核对项加入 playbook。
- **结构 proposal 脚本**：确定性脚本生成区间、趋势线等 `status: proposed` 条目，人或 agent 复核后确认。
- **Journal 驱动**：V08 由日志自动判定；积累历史后校准 rule 块中的「默认值」参数。
- **agent / skill**：用同一组 CLI 与档案文件完成「提问 → 填写 → 重跑」循环。
- **近似算法升级**：Fib 摆动点、背离等，从 `review` 升级为判定。
