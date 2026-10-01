# Phase 1 — 第一份可用的交易备忘录

> 状态：① 已完成；② 起未开始。
> 目标：`tradesys fetch META | tradesys run playbooks/technical.md | tradesys report` 输出完整的交易备忘录。
> 约束：遵守 `docs/DESIGN.md`。每一步先在 playbook 中写好 rule 块，缺什么工具再补什么工具；执行器只在 rule 块语法确实不够用时才改。

每一步结束时 `uv run pytest -q` 与 `uv run ruff check .` 都通过。

## ① 取数：yfinance ✅（2026-10-01）

- `tradesys/adapters/yahoo.py`：`fetch_snapshot(ticker, as_of)` → Snapshot。唯一的网络 I/O，pandas 只在此文件内出现。
- CLI：`tradesys fetch TICKER [--as-of 2026-09-30T17:00] [--expiry monthly|weekly]`。单次约 3 秒。
- as_of 约束：
  - 日线可回溯任意日期；as_of 晚于当前时间直接报错（防止把未收盘的日线当作已收盘）。
  - 基本面、财报日、期权链只有"现在"的数据，只在 as_of 为今天时获取，否则为空 → 相关规则 UNAVAILABLE。
  - 期权链还要求今天已收盘（收盘价与期权报价同属一天）。默认取下一个月度交割日，只保留收盘价 ±10% 的行权价。
- 测试：转换函数用手工 DataFrame（含 EP189 TSLA 经期权链算出 Band68）；两个真实取数测试标记 `network`，默认跳过，`uv run pytest -m network` 运行。
- 行情缓存：暂不需要（单次约 3 秒）。

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
