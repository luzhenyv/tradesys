# Phase 1 — 第一份可用的交易备忘录

> 状态：骨架已就绪（执行器、工具注册表、CLI、9 个 rule 块），以下步骤未开始。
> 目标：`tradesys fetch META | tradesys run playbooks/technical.md | tradesys report` 输出完整的交易备忘录。
> 约束：遵守 `docs/DESIGN.md`。每一步先在 playbook 中写好 rule 块，缺什么工具再补什么工具；执行器只在 rule 块语法确实不够用时才改。

每一步结束时 `uv run pytest -q` 与 `uv run ruff check .` 都通过。

## ① 取数：yfinance

- `tradesys/adapters/yahoo.py`：生成 Snapshot（bars、fundamental、next_earnings、chain）。唯一的网络 I/O。
- 期权链只在 as_of 为当日盘后时取，否则为 None。
- CLI 新增 `tradesys fetch TICKER [--as-of]`。
- 新增依赖 yfinance。网络测试标记为 `network`，默认跳过。
- 之后视速度决定是否加行情缓存。

## ② 只需行情的规则

| 规则 | 需要的新工具 |
| --- | --- |
| V04 缩量反弹 | `close_up`、`volume_ma5_turning_down` |
| V07 财报前放量下跌 | `trend`（P-TREND，simple）、`days_to_earnings`、`drop_pct` |
| V10 OTC / 市值 | `on_main_exchange`、`market_cap_below`（warn 块） |
| V15 RSI-6 > 90 | `rsi_above` |

V10 的社群热度部分写成 manual 块。

## ③ 结构（YAML）

- `adapters/structures.py`：读取 `data/structures/<TICKER>.yaml`，放入 Snapshot，只保留 `confirmed_at ≤ session_date` 的条目。
- 工具：`zone_broken_within`（包装 `break_verdict`）、`line_broken_within`。
- 规则：V02、V03；V12、V13（scope: candidate）。没有结构时工具返回 `hit=None` → MANUAL，提示"请在 YAML 中标注结构"。

## ④ Setups 与 simple 原语

- 先确定 `kind: setup` 的语法（`entry` / `stop` / `target` 的声明方式），写进 DESIGN §4。
- simple 原语：P-SWING、P-FIB、P-DIVERGENCE、P-CANDLE（锤子线、看涨吞没、流星线）。
- 规则：V16；S01–S07、S09。S08 已是 manual 块。

## ⑤ 报告

- `tradesys/report.py` 的 `render(results, snap)` → Markdown，按 DESIGN §3 的结论规则输出。
- 包含：结论、VETO / WARN、人工检查清单、候选买点、提醒（A-*、Band68）、未实现与 simple 规则清单。
- CLI 新增 `tradesys report`。

## 不在 Phase 1

- 行情缓存、Journal、`experiment` 命令。
- 任何 agent / skill 代码（只保证 CLI 可被编排）。

## 完成标准

- 对任意一只主板股票运行三段管道，得到完整的备忘录。
- playbook 中 V01–V16、S01–S09 都有 rule 块，并有用原始案例写的测试。
- `grep` 代码中不出现任何规则 ID。
- 包规模在预算之内。
