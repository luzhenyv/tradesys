# 系统设计

> 描述当前代码。开发原则见 `CLAUDE.md`；命令见 `README.md`；计划中的改动见 `docs/plans/`。

## 1. 分层

```text
playbooks/*.md      规则：自然语言原文 + 可执行的 rule 块（数据）
tradesys/tools/     工具：纯函数，Snapshot → Check
tradesys/run.py     执行器：解析 rule 块，调用工具，汇总 RunOutput（不含任何规则）
tradesys/report.py  RunOutput → Markdown（只按 status / trust / kind 归类）
tradesys/adapters/  取数（yahoo、fake）与档案 YAML；唯一的 I/O
tradesys/cli.py     薄壳：fetch / run / report / tool / tools，JSON 进出
```

依赖只有一个方向：playbook → 工具名 → 工具。工具不知道 playbook，执行器不知道任何具体规则。

## 2. 数据对象

全部为 frozen dataclass（`models.py`），经 `serialize.py` 与 JSON 互转。

| 对象 | 内容 |
| --- | --- |
| `Snapshot` | 一只股票在 as_of 时点的全部输入：bars（截至 session_date）、zones、lines、absent、expired、facts、fundamental、next_earnings、chain、sources |
| `Fact` | 人的回答：value（布尔、数字或文本）、at（回答日期） |
| `Candidate` | 候选买点：entry、stop、target、grade、evidence；`rr` 为计算属性 |
| `Check` | 工具输出：`hit`（True / False / None）、evidence、`review`（近似算法）、`missing`（缺数据）、`value`（setup 取价）、`grade` |
| `RuleResult` | 规则结果：rule_id、title、status、evidence、candidate_id、review、trust、kind |
| `RunOutput` | results、candidates（setup 产出 + CLI 注入）、snapshot、idle（无候选而未运行的候选规则） |

`RuleStatus`：`PASS / VETO / WARN / MANUAL`（无法判断）/ `UNAVAILABLE`（缺数据）。

## 3. Playbook 格式

- 一份 Markdown。每条规则是一个 `### ID 标题` 段落：条件、来源（附 voice 引文）、案例，以及若干 ```rule 块。没有 rule 块的段落不执行。
- **ID**：`I` 想法、`V` 不买原则（EP301 顺序），`S` 买点（EP302 顺序），`A-*` 提醒，`P-*` 原语（定义在 `*-primitives.md`，不执行）。
- **阈值写在 rule 块里**，注释标注状态：`已裁决`（用户决定）/ `source`（原文给出）/ `默认值`（待实盘校准）。
- **时点**：规则在 `session_date`（最近一个已收盘交易日）上求值，记为 T。
- **实现等级**由 rule 块本身体现：普通块 = 完整实现；`trust: review` = 近似算法；依赖结构的工具在无结构时返回 MANUAL；人的回答由 `fact` / `checklist` 读取，缺失或过期 → 未知。

## 4. rule 块语法与执行语义

```yaml
kind: veto              # veto | warn | setup | advice
scope: candidate        # 可选：对每个候选买点运行一次
trust: review           # 可选：decide（默认）| review
when:                   # 工具列表，AND
  - new_high: {n: 20}
  - volume_state: {state: shrink}
say: 提醒文本            # 可选：命中时放在 evidence 最前
ask: 提问               # 可选：块未知时放在 evidence 首位
```

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

## 5. 结论

只看 `trust: decide`：

- `不买 · 否决`：上下文 VETO，或全部候选被 VETO。
- `买（long）`：存在候选，上下文与该候选的全部 decide 规则都是 PASS / WARN。
- `不买 · 待确认 N 项`：存在候选，但有可能导致 VETO 的 decide 规则未知。
- `不买 · 无买点`。

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
- 回答由两个工具读取（`tools/answer.py`）：
  - `fact: {key, is | min | max, ttl}`：回答满足条件 → True；不给条件时只要求已回答（有 → False）。
  - `checklist: {keys, min, ttl}`：为「是」的项数 < min → True。
  - 缺失或过期 → None（提问，evidence 写明要回答的 key）。`ttl` 为交易日数：回答日到 T 少于 ttl 才有效（`ttl: 1` = 只对当次 T 有效）；省略则不过期。

## 9. 边界

- 范围：美股主板个股、只做多、日线、盘后、Markdown 备忘录。
- 不做：自动下单、Web UI、插件、事件总线、数据库、RAG、完整回测、分时、全板块扫描、止盈与持仓、做空、agent 代码。
- 推迟：行情缓存。
