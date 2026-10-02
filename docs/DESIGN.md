# 系统设计

> 描述当前代码。开发原则见 `CLAUDE.md`；命令见 `README.md`；计划中的改动见 `docs/plans/`。

## 1. 分层

```text
playbooks/primitives.md  原语说明书（不执行）
playbooks/rules.md       规则库：原语的冻结组合，规则 = 节点（数据）
playbooks/technical.md   Workflow · 技术面（节点 ID 清单）
tradesys/tools/          原语实现：纯函数，Snapshot → Check
tradesys/run.py          执行器：读 workflow 或内嵌 rule 块，调用工具（不含任何规则）
tradesys/report.py       RunOutput → Markdown（档案视图：结论 / 待回答 / 计划 / 建议买点 / 提醒）
tradesys/adapters/       取数（yahoo、fake）与档案 YAML；唯一的 I/O
tradesys/cli.py          薄壳：fetch / run / report / tool / tools，JSON 进出
```

三层资产：原语（一个工具函数）→ 规则（冻结的原语组合，即节点）→ Workflow（策略 = 节点清单）。依赖只有一个方向：workflow → 规则 ID → 工具名 → 工具。工具不知道规则，执行器不知道任何具体策略。新策略先写清单；不够再拼规则；原语不够再补工具。

## 2. 数据对象

全部为 frozen dataclass（`models.py`），经 `serialize.py` 与 JSON 互转。

| 对象 | 内容 |
| --- | --- |
| `Snapshot` | 一只股票在 as_of 时点的全部输入：bars（截至 session_date）、zones、lines、absent、expired、facts、plans、fundamental、next_earnings、chain、sources |
| `Fact` | 人的回答：value（布尔、数字或文本；日期用 ISO）、at（回答日期） |
| `Candidate` | 候选买点：entry、stop、target、grade、evidence；计划另有 `expires`、`status`；`rr` 为计算属性 |
| `Check` | 工具输出：`hit`（True / False / None）、evidence、`review`（近似算法）、`missing`（缺数据）、`value`（setup 取价）、`grade` |
| `RuleResult` | 规则结果：rule_id、title、status、evidence、candidate_id、review、trust、kind |
| `RunOutput` | results、candidates（setup 产出 + 档案 plans）、snapshot |

`RuleStatus`：`PASS / VETO / WARN / MANUAL`（无法判断）/ `UNAVAILABLE`（缺数据）。

## 3. 规则与 Workflow

- **`rules.md`**：每个 `### ID 标题` 下的 ```rule 块是一条规则（节点）。参数、`kind`、`scope`、`trust` 冻结在规则里，workflow 不覆盖。没有 rule 块的段落不执行。
- **Workflow 文件**（`technical.md`、`left.md`）：散文 + ```workflow 的 `nodes` ID 列表。`run` 按清单到 `rules.md` 取节点。无 ```workflow 的文件仍按内嵌 rule 块执行（测试片段）。不引入节点图。
- **ID**：`I` 想法、`V` 不买、`S` 买点、`A-*` 提醒、`L` / `A-LEFT` 左侧、`P-*` 原语（`primitives.md`，不执行）。
- **阈值写在 rule 块里**，注释标注状态：`已裁决`（用户决定）/ `source`（原文给出）/ `默认值`（待实盘校准）。
- **时点**：规则在 `session_date`（最近一个已收盘交易日）上求值，记为 T。
- **实现等级**由 rule 块本身体现：普通块 = 完整实现；`trust: review` = 近似算法；依赖结构的工具在无结构时返回 MANUAL；人的回答由 `fact` / `checklist` 读取，缺失或过期 → 未知。各条对照 voice 的完成度见 `docs/rule-status.md`。

## 4. rule 块语法与执行语义

```yaml
kind: veto              # veto | warn | setup | advice
scope: candidate        # 可选：对每个候选买点各跑一次；省略则对整份 Snapshot 跑一次
trust: review           # 可选：decide（默认）| review
when:                   # 工具列表，AND
  - new_high: {n: 20}
  - volume_state: {state: shrink}
say: 提醒文本            # 可选：命中时放在 evidence 最前
ask: 提问               # 可选：块未知时放在 evidence 首位
```

- **`scope`**：省略 = 上下文，整只股票当天跑一次（如 V01 新低）。`candidate` = 对每个候选买点各跑一次（档案 `plans` + 当次 setup 产出）；需要该点的 entry/stop/target（如 V05 止损过宽）。没有候选时这类规则不跑。`scope` 不是审查/盯盘阶段。
- **块内 AND 用 Kleene 逻辑**：任一工具 False → 不命中；否则有 None → 未知。setup 块例外：有 None 即未知。
- **一条规则的多个块 = if / elif**：首个命中的块决定结果；都不命中 → PASS。
- **未知的块不终止判断**：记下后继续；后面有块命中就用它，否则报告未知（MANUAL，缺数据时 UNAVAILABLE）。例外：之前有未知的 veto 块时，只有后续命中的 veto 能取代它。
- **kind**：
  - `veto` / `warn`：命中 → VETO / WARN。
  - `setup`：命中后用 `entry` / `stop` / `target` 工具取 `Check.value`，产出至多一个 Candidate；entry 取不到则不产出。grade 取工具给出的，否则 `review` → B，否则 A。执行器先跑全部 setup，再跑其余规则。
  - `advice`：`when` 可省略（总是提醒）；只进报告「提醒」。
- **trust**：`decide` 计入结论；`review` 只作参考。advice 由报告按 `kind` 排除，不参与判定。`Check.review` 只用于展示「⚠ 近似」。
- **没有 OR、没有表达式语言**：需要 OR 就拆成两个块，或写成一个工具。
- **解析时校验**：kind 与键必须合法，必填项齐全；拼写错误直接报错。

## 5. 结论与报告

报告章节：结论 → 待回答 → 计划 → 系统建议买点 → 提醒。结论一行，优先级：

1. 档案无 `idea.reason` → `先写想法理由`
2. 有计划（`Candidate.expires` 有值）：`计划 p1 已过期` / `计划 p1 暂停（规则 ID 标题）` / `计划 p1 可执行`（过期优先；暂停原因取 `blockers` 首条）
3. 无计划 + 上下文 decide VETO → `不买（规则 ID 标题）`
4. 无计划 + 上下文阻断未知（decide 的 veto 为 MANUAL / UNAVAILABLE）→ `待回答 N 项`
5. 其余 → `审查通过，尚无计划`

setup 产出只进「系统建议买点」，不把结论写成买入。warn 未知不阻断。暂停 / 过期由 `plan_state` 计算，不存档。**可执行** = 计划未被否决且未过期（限价可以挂着），不是「今天收盘必须买」。有多条计划时结论只看第一条。

## 6. 工具

- 签名 `tool(snap, **args) -> Check`；`scope: candidate` 的工具为 `tool(snap, candidate, **args)`。阈值一律由 rule 块传入。
- 纯函数，不做 I/O。在 `tools/__init__.py` 的 `TOOLS` 中注册，不做动态加载。
- docstring 首行写原语 ID 与来源，`tradesys tools` 据此列出。
- 可复用的计算（`extreme`、`volume_ratios`、`band68`、`break_verdict`…）是同文件里的普通函数，工具只包一层。
- 新增工具的门槛：某条规则需要，且无法由已有工具组合得到。

## 7. 时点与数据约束

- **UTC**：内部时点一律为带时区的 UTC；`fetch --tz` 在 CLI 边界把当地时间转为 UTC。
- **session_date**：as_of 转美东时间后，取最近一个已收盘的常规交易日；盘中取前一交易日，不使用未完成日线。
- **收盘价是唯一真值**：破位、突破、新低、新高都用常规时段收盘价（EP272）。
- **无未来数据**：基本面、财报日、期权链只有「现在」的值，只在 as_of 为今天时获取，否则为空 → UNAVAILABLE。期权链还要求 session_date 收盘后尚无新的常规时段开盘。
- **交易日历**：`calendar_utils.NYSE_HOLIDAYS`（2025–2027，需逐年补充）；月度 OpEx 遇休市提前到周四。
- **数据源**：yfinance（`adapters/yahoo.py`），测试用 `adapters/fake.py`。

## 8. 档案 YAML

`data/tickers/<TICKER>.yaml`，一只股票一个文件。人写，机器只读；结构人画，机器只判定，不自动识别。

- `zones`（support / resistance 区间）、`lines`（trendline / neckline / flag_pole / flag_upper / flag_lower，两点定线）。
- 日期（`confirmed_at` / `at`）≤ T 的下一个交易日即载入：盘后到次日开盘前补写的内容属于对 T 的判断，回放时看不到更晚的内容。`status: proposed` 不载入；多余键（strength、note…）忽略。
- `absent: [{kind, confirmed_at}]`：人确认不存在的结构（zone / trendline / neckline / flag）→ 相关工具返回 False（不适用），而不是 None（请标注）。
- **结构按类过期**：zone / trendline / neckline / flag（含该类的 absent）中最旧的条目超过 20 个交易日（`dossier.STRUCTURE_TTL`），整类不载入，记入 `Snapshot.expired`；相关工具提问「已过期，请复核」，报告头列出过期的类。
- 每种旗形线只能有一条，多条 → MANUAL。
- 顶层 `exchange:`：人确认的交易所代码，只在取不到当天基本面时补上（历史回放）。
- `facts: {key: {value, at}}`：人的回答，载入为 `Snapshot.facts`；`idea: {reason, source, at}` 载入为 `idea.reason` / `idea.source`。
- `plans`：人写的买点，载入为 `Candidate` 挂到 `Snapshot.plans`，与 setup 产出走同一组候选规则。`cancelled` 不载入；`expires` 省略 = `at` + 20 个交易日。`status` 只存 `active` / `cancelled`；「暂停」「过期」由报告计算（过期 = `session_date > expires`；暂停 = 该计划有 decide 的 VETO 或未知 veto，含上下文规则）。
- 回答由两个工具读取（`tools/answer.py`）：
  - `fact: {key, is | min | max | within, ttl}`：`is` 相等；`min` / `max` 数字比较；`within: N` 则 value 为日期（`true` 表示用 `at`，`false` 表示没有），距 T 不足 N 个交易日 → True；无条件时只要求已回答（有 → False）。
  - `checklist: {keys, min, ttl}`：为「是」的项数 < min → True。
  - 缺失或过期 → None（提问，evidence 写明要回答的 key）。`ttl` 为交易日数：回答日到 T 少于 ttl 才有效（`ttl: 1` = 只对当次 T 有效）；省略则不过期。`within` 看的是 value 里的日期，回答本身不过期。

## 9. 边界

- 范围：美股主板个股、只做多、日线、盘后、Markdown 备忘录。
- 交易日志是本地 jsonl（`data/journal/`，不进 git），编排见 `docs/WORKFLOW.md` §5；不是系统对象。
- 不做：自动下单、Web UI、插件、事件总线、数据库、RAG、完整回测、分时、全板块扫描、止盈与持仓、做空、agent 代码。
- 推迟：行情缓存。
