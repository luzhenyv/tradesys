# tradesys · 设计

> 取代 `docs/archive/Architecture-Freeze-v1.md`（2026-10-01）。
> 一句话：**规则是数据，代码是工具，执行器是通用的。**

---

## 1. 目标

把自然语言的投资哲学变成可执行、可解释、可追溯的判断。对一只股票，在某个时点，给出"哪些规则命中、为什么、哪些需要人工确认"。

- **代码依赖规则，规则不依赖代码。** 规则写在 playbook 里；换投资风格（技术面 → 价值投资 → 波段）是换一份 playbook，不改执行器。
- **小工具，靠组合解决复杂任务。** 不为任何复杂任务写全能函数。
- **编排者可替换。** 现在由执行器 / 脚本编排；将来交给 agent + skill，甚至 sub-agent。工具与 playbook 不随之改变。
- **简单优先。** 不轻易增加复杂度；够用即可（§9）。

## 2. 四层

```text
playbooks/*.md      规则：自然语言原文 + 可执行的 rule 块（数据）
tradesys/tools/     工具：纯函数，Snapshot → Check（代码）
tradesys/run.py     执行器：读 playbook，按 rule 块调用工具，汇总结果（不含任何规则）
tradesys/cli.py     薄壳：每个工具、执行器都能单独从命令行调用，JSON 进出
```

依赖方向只有一个：playbook → 工具名 → 工具。工具不知道 playbook，执行器不知道任何具体规则。

## 3. 数据对象

全部为 frozen dataclass（`tradesys/models.py`），经 `tradesys/serialize.py` 与 JSON 互转。

| 对象 | 含义 |
| --- | --- |
| `Snapshot` | 某只股票在 as_of 时点的全部输入：bars（截至 session_date）、zones、lines、fundamental、next_earnings、chain、sources |
| `Candidate` | 候选买点：entry、stop、target、grade、evidence；`rr` 为计算属性 |
| `Check` | 一个工具的输出：`hit`（True / False / None）、evidence、review、missing |
| `RuleResult` | 一条规则的结果：rule_id、title、status、evidence、candidate_id、review |
| `RunOutput` | 一次运行：`results` + `candidates`（setup 产出及 CLI 注入） |

`RuleStatus`：`PASS / VETO / WARN / MANUAL / UNAVAILABLE`。
- `WARN` 不阻断，由用户决定。
- `MANUAL`（系统无法判断）与 `UNAVAILABLE`（缺数据）不等于 `PASS`，报告中列为人工检查清单。
- 结论：任一 VETO → 不买；否则存在 MANUAL / UNAVAILABLE → 待人工确认；否则附带 WARN 列表。

## 4. Playbook 与 rule 块

一个 playbook 是一份 Markdown。每条规则是一个 `### ID 标题` 段落，自然语言写原文、来源、案例；可执行部分写在段内的 ```rule 块（YAML）：

```yaml
kind: veto              # veto | warn | manual
scope: candidate        # 可选：对每个候选买点运行一次
when:                   # 列表中全部工具 hit=True 才命中（只有 AND）
  - new_high: {n: 20}           # 参数名 · 状态（已裁决 / source / 默认值）
  - volume_state: {state: shrink}
```

- **一段可以有多个 rule 块，按顺序判断，首个命中的块决定结果**（相当于 if / elif）。都不命中 → PASS。例：V14 先 `veto rr_below 1.0`，再 `warn rr_below 1.5`。
- **任一工具返回 `hit=None`** → 停止判断，状态为 MANUAL（缺数据时为 UNAVAILABLE）。
- **`kind: manual`** 只写 `ask: 提问`，不需要任何代码。
- **没有 OR、没有表达式语言。** 需要 OR 就拆成两个 rule 块，或写成一个工具。
- **阈值写在 rule 块里**，就在规则原文旁边。不另设配置文件。
- **没有 rule 块的规则** = 尚未实现，执行器跳过。
- **`kind: setup`**（产生 Candidate）。`when` 与 veto 相同（AND）。命中后用工具取价：

```yaml
kind: setup
when:
  - first_down: {}
  - pullback_to_ma: {n: 5}
entry: {session_close: {}}
stop: {buffered_low: {pct: 0.01}}
target: {nearest_resistance: {}}     # 没有阻力则 value=None，仍产出
```

  多个 setup 块 = if / elif，每条规则最多 1 个 Candidate。entry 失败则不产出；stop / target 可为 None。
  `Check.value` 为价格；`Check.grade` 若有则用之，否则 `review=True` → `B`，否则 `A`。
  执行器先跑全部 setup，再跑其余规则（含 `scope: candidate`）。`run` 返回 `RunOutput(results, candidates)`。

## 5. 工具

- 签名：`tool(snap, **args) -> Check`；`scope: candidate` 的工具为 `tool(snap, candidate, **args)`。
- 纯函数：不做 I/O，不读全局状态。I/O 只在 adapters（取数）与 CLI。
- 在 `tradesys/tools/__init__.py` 的 `TOOLS` 字典中注册；不做动态加载。
- 每个文件约 ≤ 50 行。docstring 首行写它实现的原语 ID 与来源（如 `P-NEWLOW · EP301§R01`），`tradesys tools` 据此列出说明，供 agent 发现。
- 可复用的计算（如 `extreme`、`volume_ratios`、`band68`、`break_verdict`）写成普通函数放在同一文件，工具只做一层包装。
- **新增工具的门槛**：某条规则需要、且无法由已有工具组合得到。

## 6. 时点与数据约束

- **统一使用 UTC 时间**：系统内部所有时点（`Snapshot.as_of`、`Chain.as_of`、序列化 JSON）一律使用带时区的 UTC 时间。`tradesys fetch` 提供 `--tz` / `--timezone`（默认 UTC）允许用户按当地时区（如 `Asia/Shanghai`、`Asia/Tokyo`）输入时点，在 CLI 边界转换为 UTC。
- **盘后分析**：`as_of` 先转为美东时间（ET），解析为 `session_date` = 最近一个已收盘的常规交易日（`calendar_utils.make_snapshot`）；盘中 as_of 取前一交易日，永不使用未完成日线。
- **收盘价是唯一真值**：破位、突破、新低、新高一律以常规时段收盘价判定（EP272）。
- **as_of 无未来数据**：adapter 不得返回 as_of 之后才可获得的数据。yfinance 的基本面、财报日、期权链只有"现在"的值，所以只在 as_of 为今天时获取，否则为空 → `missing` → UNAVAILABLE；不得用今天的数据冒充过去。
- **结构由人画**：支撑阻力区间、趋势线、颈线、旗形 A/B 线来自 `data/structures/<TICKER>.yaml`，机器只判定，不自动识别。`tradesys fetch` 按 `confirmed_at ≤ session_date` 载入；`status: proposed` 的条目不进入 Snapshot（手写省略 status = 已确认）。`strength` / `note` / `source` 等多余键忽略，供人阅读与将来「生成 + 复核」。无结构时相关规则 MANUAL，不是 UNAVAILABLE。

## 7. 编排

现在：

```bash
tradesys fetch META > snap.json                     # 唯一 I/O
tradesys run playbooks/technical.md < snap.json     # → RunOutput JSON（含 snapshot）
tradesys report playbooks/technical.md < snap.json  # 或接 RunOutput / Snapshot
tradesys tool new_low --arg n=20 < snap.json        # 单独运行任一工具
tradesys tools                                      # 列出工具
```

管道：`tradesys fetch META | tradesys run playbooks/technical.md | tradesys report playbooks/technical.md`。`report` 也可直接读 Snapshot（内部先 run）。

将来：agent 读 playbook 原文，用同一组 CLI 命令调用工具、组合判断；也可把 `fetch / run / report` 写成 skill。不需要改工具和 playbook。

## 8. 来源（Sources）

原始材料在 `docs/sources/voice/`（原文）与 `docs/sources/summaries/`（LLM 整理）。规则只引用稳定的 Source ID，如 `EP301§R05`（第 301 期第 5 条）、`EP302§B3`（第 302 期买点 3）。文件命名 `2026-09-23-<id小写>-<中文短名>.md`，summary 追加 `-summary`。

| Source ID | 主题 |
| --- | --- |
| EP010 | 成交量与价格关系 |
| EP124 | K 线见顶止跌形态有效性排序 |
| EP150 | 旗形整理 |
| EP189 | 期权 68% 波动范围 |
| EP249 | 止盈与短期强弱预警 |
| EP272 | 开盘价收盘价与支撑压力 |
| EP292 | 左侧建仓未满即反弹 |
| EP301 | 买点避雷 18 条 |
| EP302 | 胜率最高的 9 种买点 |

未入库：EP095、EP111、EP161（分时），只作备忘提醒，不产生代码。

规则以 voice 原文为准：`confirmed` 规则的条件必须能在 voice 中找到依据；只出现在 summary 中的内容最多是 `draft`。

## 9. 简单的边界（MVP）

- **实现等级**（playbook 中每条规则的 `Impl`）：`full` 完整实现；`simple` 近似算法，Check 带 `review=True`，报告标"⚠ 近似算法，需人工复核"；`stub` / `manual` 只写 ask，不写代码。
- **规模**：`tradesys/` 包约 ≤ 1500 行，工具文件约 ≤ 50 行。超出时先简化或降级为 manual。
- **一个真实数据源**：yfinance（`adapters/yahoo.py`），外加测试用 fake。
- **V1 范围**：美股主板个股、只做多、日线、盘后，输出 Markdown 备忘录。
- **V1 不做**：自动下单、Web UI、插件机制、事件总线、数据库 ORM、RAG / 向量库、完整回测、分时系统、全板块扫描、止盈与持仓、做空与期权策略、任何 agent 代码（只保证 CLI 可被编排）。
- **推迟决定**：行情缓存（DuckDB）、Journal（SQLite）。

## 10. 测试

- 测试名写明原始案例，如 `test_v05_ep301_entry119_stop100_vetoes_and_entry109_passes`。
- 规则案例通过真实 playbook 运行（`tests/unit/test_run.py`），这样测的是"规则 + 工具"，而不是代码里的另一份规则。
- 工具的纯函数部分单独测试。
