# Phase 1 — 第一份可用的交易备忘录

> 状态：①–⑥ 已完成。
> 目标：`tradesys fetch META | tradesys run playbooks/technical.md | tradesys report playbooks/technical.md` 输出完整的交易备忘录。
> 约束：遵守 `docs/DESIGN.md`。每一步先在 playbook 中写好 rule 块，缺什么工具再补什么工具；执行器只在 rule 块语法确实不够用时才改。

每一步结束时 `uv run pytest -q` 与 `uv run ruff check .` 都通过。

## ① 取数：yfinance ✅（2026-10-01）

- `tradesys/adapters/yahoo.py`：`fetch_snapshot(ticker, as_of)` → Snapshot。唯一的网络 I/O，pandas 只在此文件内出现。
- CLI：`tradesys fetch TICKER [--as-of 2026-09-30T17:00] [--tz Asia/Shanghai] [--expiry monthly|weekly]`。单次约 3 秒。
- as_of 约束：
  - 系统内部统一使用 UTC 时间（`Snapshot.as_of` 为 UTC aware datetime）。CLI 提供 `--tz` / `--timezone`（默认 UTC）供用户输入当地时间。美股交易日判定与 Yahoo 取数转换为美东时间（ET）。
  - 日线可回溯任意日期；as_of 晚于当前时间直接报错（防止把未收盘的日线当作已收盘）。
  - 基本面、财报日、期权链只有"现在"的数据，只在 as_of 为今天时获取，否则为空 → 相关规则 UNAVAILABLE。
  - 期权链还要求今天已收盘（收盘价与期权报价同属一天）。默认取下一个月度交割日，只保留收盘价 ±10% 的行权价。
- 测试：转换函数用手工 DataFrame（含 EP189 TSLA 经期权链算出 Band68）；两个真实取数测试标记 `network`，默认跳过，`uv run pytest -m network` 运行。
- 行情缓存：暂不需要（单次约 3 秒）。

## ② 只需行情的规则 ✅（2026-10-02）

| 规则 | 工具 |
| --- | --- |
| V04 缩量反弹 | `close_up`、`volume_state`、`volume_declining`、`volume_ma5_turning_down`（两个 veto 块 = OR） |
| V07 财报前放量下跌 | `trend`（P-TREND，simple）、`days_to_earnings`、`drop_pct`、`volume_state` |
| V10 OTC / 市值 | `exchange_not_in`（veto）、`market_cap_below`（warn）、社群热度 manual 块 |
| V15 RSI-6 > 90 | `rsi_above` |

主板白名单写在 V10 rule 块：NYQ/NYS/NMS/NGM/NCM/NAS/ASE/PCX。缺 fundamental / 财报日 → UNAVAILABLE。不改执行器。

## ③ 结构（YAML） ✅（2026-10-02）

- `adapters/structures.py`：读取 `data/structures/<TICKER>.yaml`，`confirmed_at ≤ session_date`，`status: proposed` 跳过；多余键忽略。`fetch` 挂到 Snapshot。
- 工具：`zone_broken_within`、`line_broken_within`、`far_from_support`、`tight_to_resistance`。无结构 → MANUAL。
- 规则：V02、V03（趋势线 + 颈线；Fib 留 ④）；V12、V13（scope: candidate）。
- 手写范例：`data/structures/AMD.yaml`。`strength` 只存档。`kind` 由人指定。
- 执行器：`call()` 只给声明了 `candidate` 的工具传入候选，以便 V13 组合上下文工具。

## ④ Setups 与 simple 原语

### ④a 语法 + 不依赖 YAML 的 Setup ✅（2026-10-02）

- DESIGN §4：`kind: setup` + `entry`/`stop`/`target` 工具取 `Check.value`。每条最多 1 个 Candidate。
- `run()` 返回 `RunOutput(results, candidates)`：先跑 setup，再跑其余规则。
- 原语：P-SWING、P-FIB（60 日）、P-DIVERGENCE、P-CANDLE（锤子 / 一级吞没 / 流星）。
- 规则：V16、V03 Fib、S05、S06、S07。S08 已是 manual。
- `new_low` / `volume_state` 增加可选 `offset`。

### ④b YAML Setup ✅（2026-10-02）

- S01–S04、S09。when 与 stop 共用查找函数（最近一次符合的 Zone/Line）。不写 `setups/s03.py`。
- 无 YAML：S01–S04 → MANUAL。S09 用 Fib 61.8% 当支撑，不依赖 YAML。
- `check_all`：setup 块 `hit=None` 优先于 False（缺结构时不因另一工具 False 而变成 PASS）；veto / warn 改为 Kleene（见 ⑥）。

## ⑤ 报告 ✅（2026-10-02）

- `render(out)` → Markdown。结论只看 `trust: decide`（⑥ 起「不知道等于不买」）。
- 章节（⑥ 后，过渡形态）：结论 + 原因、判定（上下文 VETO/WARN + 每个 decide 候选的 存活 / 否决 / 待确认）、待确认（阻断买入）、未能评估的买点、参考（近似）、规则覆盖、提醒（来自 playbook 的 `kind: advice`）。
- `RunOutput.snapshot` 随 run 输出，故 `fetch | run | report PLAYBOOK` 可串联。`report PLAYBOOK` 也可直接读 Snapshot。

## ⑥ Review 修复 ✅（2026-10-02）

依据 Phase 1 peer review：

- **结论**：不知道等于不买。headline 为 `买（long）/ 不买 · 否决 / 不买 · 待确认 N 项 / 不买 · 无买点`；每个 decide 候选都列出并标注 存活 / 否决 / 待确认（review #1 #2）。
- **执行器**：未知的块不终止判断（#5）；veto / warn 用 Kleene（#6）；未知结果保留块的 trust；新增 `kind: todo` / `kind: advice`；`RuleResult.kind`；注入候选 id 冲突报错。
- **结构**：YAML `absent` 声明不存在的结构 → 不适用；S03 旗杆改为人画 `flag_pole`，去掉近似标记（#3）；`line_broken_within` 无线时诚实返回 None。
- **报告**：trust 决定结论，review 只展示「⚠ 近似」（#4）；Advice 改为 playbook 中的 `kind: advice` 条目与 `band68_edge` 工具（#7）；去掉 V/S 前缀假设，以「规则覆盖」章节取代「备忘 / 未实现」。
- **数据**：期权链条件改为「session_date 收盘后尚无新开盘」（#8）；NYSE 2025–2027 休市表、交易日计数、Good Friday OpEx。
- **Low**：V10b 社群热度独立成条；`bullish_engulfing` 去掉无效的 tier；`fib_broken` 在破位窗口之前取上涨段；retest 公共骨架合并。
- **预算**：DESIGN §9 有意上调为约 ≤ 2200 行（#9）。

## 不在 Phase 1

- 行情缓存、Journal、`experiment` 命令。
- 任何 agent / skill 代码（只保证 CLI 可被编排）。

## 完成标准

- 对任意一只主板股票运行三段管道，得到完整的备忘录。
- playbook 中 V01–V16、S01–S09 都有 rule 块，并有用原始案例写的测试。
- `grep` 代码中不出现任何规则 ID。
- 包规模在预算之内（约 ≤ 2200 行，DESIGN §9）。
