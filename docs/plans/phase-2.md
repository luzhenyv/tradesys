# Phase 2 — 从「一次判断」到「一只股票的档案」

> 状态：⓪–⑤ 已完成，⑥ 起待实施（2026-10-02）。
> 目标：实现 `docs/WORKFLOW.md`。10-01 盘后问「AMD 明天能买吗」，系统列出待回答的问题；人只编辑档案文件、重复运行同一条管道，最终得到「计划可执行 / 暂停 / 过期」的结论。
> 约束：遵守 `CLAUDE.md`。不新增 CLI 命令；不增加概念，除非万不得已（每步写明概念账）；工具层、取数、结构判定不动。每步在同一提交里更新受影响的文档（DESIGN、WORKFLOW、README、playbook）。

每一步结束时 `uv run pytest -q` 与 `uv run ruff check .` 都通过。

**预算**：包现为 2241 行（⑤ 后，**超出约 40**；上限约 2200）。⑦ 已在 ③–⑤ 做完。

## 已定决策（2026-10-02）

| # | 问题 | 决定 |
| --- | --- | --- |
| 1 | 档案目录 | `data/structures/` → `data/tickers/` |
| 2 | V09 清单 | 9 项（见 ③），`min: 7` |
| 3 | 日志内容 | 只保存事后无法重新获取的数据：结论与规则结果、当次档案（回答、结构、计划）、当天才有的数据（基本面、财报日、期权报价）；日线可重新下载，不保存 |
| 4 | 结构过期 | 以 WORKFLOW 为准：`confirmed_at` 起 20 个交易日后过期，需复核 |
| 5 | S08 | 由 `fact` 回答，作为普通 setup |
| 6 | 想法规则 | playbook 新增「想法」一节，`I01` |
| 7 | 回答的值 | 支持布尔（`is`）与数字阈值（`min` / `max`） |
| 8 | S08 止损 | 不设止损工具：V05 判「止损无法确定」。买点必须有止损，由人在计划中决定（可随时调整） |
| 9 | 入口 | 删除 `report` 读 Snapshot 与 `run --candidates`；命令为 `tradesys report < run.json` |
| 10 | 日志 | `data/journal/` 不进 git（已加入 `.gitignore`） |

## ⓪ 文档重构 ✅（2026-10-02）

- 每个主题只写在一处：README（介绍、命令、文档地图）、CLAUDE（开发守则）、DESIGN（系统设计，描述现状）、WORKFLOW（Phase 2 目标流程与档案格式）、`docs/sources/README.md`（Source ID）、playbook（交易规则）。
- playbook 871 → 546 行：原语拆到 `playbooks/technical-primitives.md`；每条规则只留 条件 / 来源 / 案例 / rule 块；删除阅读约定中的机制说明与出处索引。rule 块逐字不变（解析结果比对），只有两处有意修改：V06 提问「T-1 日」→「T 日」（voice：「前一交易日不要去碰它」，以买入日为准）；V10 标题去掉已拆出的「社群热度」。
- 修正与代码不符的旧描述：P-FIB「摆动点取自 YAML」、P-VOL `is_opex_friday`、P-CANDLE `PatternHit`。
- phase-1 压缩为结果摘要；CLAUDE 增加「archive 只读」「文档描述现状」。
- 顺带删除死代码：`rsi_below` 工具（无规则使用）、`kind: todo`（playbook 未使用）。

## ① 档案文件 ✅（2026-10-02）

- `data/structures/` → `data/tickers/`；`adapters/structures.py` → `adapters/dossier.py`（`load()` 返回 `Dossier`）；`yahoo.attach_structures` → `attach_dossier`。
- 载入 `facts`（`at ≤ session_date`），`Snapshot.facts: dict[str, Fact]`；`serialize` 支持 dict。
- 结构过期（DESIGN §8）：按类（zone / trendline / neckline / flag，含 absent）判断，一类中最旧条目超过 20 个交易日 → 整类不载入，记入 `Snapshot.expired`；工具提问「已过期，请复核」，报告头列出过期的类，`sources` 加 `expired=…`。
- 测试：`tests/unit/test_dossier.py`（回答载入、按类过期、AMD 档案过期前后、JSON 往返）。
- 与原计划的差异：
  - `idea` 不另设字段，载入为回答 `idea.reason` / `idea.source`（③ 的 I01 直接用 `fact` 读）。
  - 按类而不是按条过期：避免新旧结构混在一起判断（比如过期的支撑不载入，V12 却误判「悬空」）。
  - `Snapshot.structures_confirmed` 由 `expired` 取代。
  - `plans` 留到 ④ 载入。
- 实跑影响：`AMD.yaml` 于 08-20 确认，至 10-01 已超过 20 个交易日，全部结构过期，需人复核后更新 `confirmed_at`。
- 概念账：+ `Fact`（即 ② 的「人工回答」，提前定义）；− `structures_confirmed`；`Structures` 改名 `Dossier`。

## ② 人工回答工具 ✅（2026-10-02）

- `tools/answer.py`：`fact: {key, is | min | max, ttl}`、`checklist: {keys, min, ttl}`（语义见 DESIGN §8）。缺失或过期 → None（提问，`missing=False`）；`fact` 的未知参数直接报错（`iss: true` 不会悄悄变成「只要求已回答」）。
- 测试：`tests/unit/test_answer.py`（ttl 边界含次日早上补写、数字阈值、无条件、清单 6/9 与 7/9、`is` 经 rule 块传入）。
- 与原计划的差异：
  - 去掉 `ttl: earnings`：取不到历史财报日，无法判断两次回答之间是否发生过财报；V09 直接写 `ttl: 63`（约一季度），少一个概念。
  - `fact` 不给条件 = 只要求已回答（有 → False，无 → 提问）：I01 直接用它。
  - 修正 ① 的可见性：日期 ≤ T 的**下一个交易日**即可见（原为 ≤ T），否则上海早上补写的回答与结构会被丢掉；`calendar_utils.next_trading_day`。
- 概念账：+ `fact` / `checklist` 两个工具；`Fact` 已在 ① 定义。

## ③ 规则迁移：manual → 普通块 + `ask` + `fact` ✅（2026-10-02）

- 执行器：删除 `kind: manual` 与 `trust: memo`；任何块可写 `ask:`，块未知时 `ask` 作为提问放在 evidence 首位。advice 仅靠 `kind` 区分，不参与判定。
- playbook 新增「想法」一节：`I01 写下想法理由`，`fact` 读 `idea.reason`，缺失 → 提问。
- 改写（有效期为默认值，写在 rule 块的 `ttl`）：

| 规则 | 写法 | ttl |
| --- | --- | --- |
| V06 板块跌幅前 10% | `fact: {key: v06.sector_top_loser, is: true}` → VETO | 1 |
| V07 无明显利空 | 原四个条件 + `fact: {key: v07.no_bad_news, is: true}`（Kleene：其余条件成立时才提问） | 1 |
| V08 近期被止损 | `fact: {key: v08.stopped_out, is: true}` | 1 |
| V09 基本面熟悉度 | `checklist`（下表 9 项，`min: 7`） | 63（约一季度） |
| V10b 社群热度异常 | `fact: {key: v10b.social_hype, is: true}` | 5 |
| S08 板块龙头大阳 | setup：`fact: {key: s08.sector_breakout_leader, is: true}` + `green_expand`；entry 为收盘价；**不写 stop**（V05 否决，由人在计划中定止损）；target 为最近阻力 | 1 |

V09 清单（每项布尔，可在 playbook 中增删）：

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

- 测试（真实 playbook）：V09 6/9 → VETO、7/9 → PASS、缺 1 项 → 提问；V07 上涨中不提问；I01 缺理由 → 提问；S08 回答为真 → 产出无止损的建议，V05 否决。
- 与原计划的差异：
  - V07 用 `is: true`（计划表写成 `is: false`）。voice：「也没有什么太多的利空消息，这种情况不要买」→ 无明显利空才否决。
- 文档：DESIGN 去掉 `kind: manual` / `trust: memo`；README 补想法（I）。
- 概念账：− manual、− memo。包 2248 行。

## ④ 计划生命周期 ✅（2026-10-02）

- `Candidate` 新增 `expires: date | None`、`status: str = "active"`（setup 产出不填）。
- 档案 `plans` 载入为 Candidate，挂 `Snapshot.plans`；`run` 与 setup 产出合并。`cancelled` / 无 `at` / `at` 晚于 cutoff 不载入；`expires` 省略 = `at` + 20 个交易日。
- 「暂停」「过期」由 `report.plan_state` 计算，不存储：过期 = `session_date > expires`；暂停 = 该计划存在 decide 的 VETO 或未知 veto（含上下文规则）。
- 测试：过期边界；省略 expires = at+20；cancelled 不载入；V12 否决 → 暂停，靠近支撑 → 可执行。
- 同一提交做了 ⑦ 中与 ④ 无关的删除：规则覆盖 / `idle`、`report` 只读 RunOutput、CLI `--candidates`、`fetch --expiry weekly`。
- 概念账：计划 = Candidate + 两个字段；`Snapshot.plans` 为管道载体。包 2254 行。

## ⑤ 报告：档案视图 ✅（2026-10-02）

- 章节按 WORKFLOW §4：结论 → 待回答 → 计划 → 系统建议买点 → 提醒。删判定 / 待确认 / 未能评估 / 参考。
- 结论一行：先写想法理由 → 有计划则过期 / 暂停（原因）/ 可执行 → 无计划则不买（原因）/ 待回答 N 项 / 审查通过，尚无计划。setup 不再写成「买（long）」。
- 待回答：阻断的未知 veto（规则 ID + 提问 + key）。warn 未知不列入。
- 测试：七种 headline 各一例（真实 playbook）。
- ⑦ 结论分支：删 `verdict()` 与四种旧 headline。
- 概念账：− `verdict`、− 四种旧 headline。包 2241 行。

## ⑥ 日志

- 按 WORKFLOW §5：`tee >(jq -c 'del(.snapshot.bars)' >> data/journal/<TICKER>.jsonl)`。RunOutput 已包含决定 3 要保存的全部内容（snapshot 里的档案、基本面、财报日、期权链），只去掉日线。
- 不新增命令、不改代码；`data/journal/` 已加入 `.gitignore`（只在本地）。

## ⑦ 代码精简（依据 ⓪ 后的代码 review）

| 删除 | 原因 | 估计 |
| --- | --- | --- |
| `kind: manual`、`trust: memo`、`block_trust` 的分支 | ③ 已删 | −15 |
| 报告「规则覆盖」章节、`RunOutput.idle` | ④ 已删 | −30 |
| 报告的结论分支（`verdict` / `blockers` / 四种 headline） | ⑤ 已删 `verdict` 与旧 headline；`blockers` 留给 `plan_state` | 约 0（重写） |
| `report` 读 Snapshot 再内部 run 的路径，以及 `report` 的 PLAYBOOK 参数 | ④ 已删；`report` 只读 RunOutput | −10 |
| `run --candidates` | ④ 已删；档案 `plans` 是候选的唯一外部入口 | −8 |
| `fetch --expiry weekly` 与 `pick_expiry` 的 kind 参数 | ④ 已删 | −5 |

保留（考虑过，不删）：
- setup 块的「None 优先」：缺结构时提示请标注，而不是静默跳过。
- MANUAL 与 UNAVAILABLE 的区分：前者请人回答，后者请补数据。
- `Fundamental.sector`：V06 提问时可以显示所属板块。

## ⑧ 场景验收

- `tests/unit/test_workflow.py`，用 fake 行情 + 真实 playbook 走完整循环：
  1. 只有 ticker → 「先写想法理由」。
  2. 写入 idea → 「待回答 N 项」（V06 / V08 / V09 / V10b，V07 视行情）。
  3. 写入回答 → 「审查通过，尚无计划」，附系统建议买点。
  4. 写入 plan → 「计划 p1 可执行」。
  5. 次日行情触发 V12 → 「计划 p1 暂停（V12 …）」；再次日恢复。
  6. 超过 expires → 「计划 p1 已过期」。
- 实跑：在真实 AMD 档案上运行 WORKFLOW §5 的循环。
- 文档：去掉 WORKFLOW 的「Phase 2 目标」状态行；DESIGN 与 README 描述新现状。

## 不在 Phase 2

- 估值清单（与 V09 同样的 `checklist` 形式）、结构 proposal 脚本、agent / skill。
- 由日志驱动的 V08 自动化与参数校准。
- 近似算法升级（Fib、背离）。
- 执行时刻的检查（如用实际开盘价判 V13）。
- 行情缓存。

## 完成标准

- 只编辑档案文件、重复运行同一条管道，就能走完 ⑧ 的六个阶段。
- 执行器中不再有 `manual` / `memo`；每个未知结果都对应一个带 key 的提问。
- 代码中不出现规则 ID；包 ≤ 2200 行；pytest 与 ruff 通过。
