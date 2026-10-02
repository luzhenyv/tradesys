# tradesys

个人交易助手：把自然语言的投资方法论变成可执行、可追溯的判断。

对一只美股，在某个盘后时点，回答「明天能不能买」：先写想法理由（I），再逐条检查不买原则（V）、识别买点（S）、给出提醒（A），并说明理由与需要人工确认的事项。

## 核心功能

- **规则即数据**：方法论写在 `playbooks/technical.md`，每条规则 = 原文条件 + 来源 + 案例 + 可执行的 `rule` 块。换风格只换 playbook。
- **小工具组合**：`tradesys/tools/` 中的纯函数（新低、量能、RSI、结构破位、K 线形态、Band68…）由 rule 块按名字组合调用。
- **一只股票一份档案**：`data/tickers/<TICKER>.yaml` 写人画的结构（支撑阻力区间、趋势线、颈线、旗形）与人的回答，机器只判定。
- **不用未来数据**：任意 as_of 回放日线；基本面、财报日、期权链只取当天。
- **CLI 管道，JSON 进出**：每一步可单独运行，将来由 agent 用同一组命令编排。

当前范围：美股主板个股、只做多、日线、盘后；数据源 yfinance。

## 快速开始

```bash
uv sync
uv run tradesys fetch AMD | uv run tradesys run playbooks/technical.md | uv run tradesys report
```

| 命令 | 作用 |
| --- | --- |
| `tradesys fetch AMD [--as-of 2026-10-01T17:00 --tz America/New_York]` | 取数 → Snapshot JSON（唯一的网络 I/O） |
| `tradesys run PLAYBOOK < snap.json` | 运行全部规则 → RunOutput JSON |
| `tradesys report < run.json` | Markdown 备忘录 |
| `tradesys tool new_low --arg n=20 < snap.json` | 单独运行一个工具 → Check JSON |
| `tradesys tools` | 列出全部工具 |

开发：

```bash
uv run pytest -q                              # 离线测试；联网测试加 -m network
uv run ruff check . && uv run ruff format .
```

## 文档

| 文件 | 内容 |
| --- | --- |
| `CLAUDE.md` | 开发守则 |
| `docs/DESIGN.md` | 系统设计：分层、数据对象、rule 块语法、工具约定、数据约束 |
| `docs/WORKFLOW.md` | 一只股票从想法到记录的流程；盯盘管道与本地日志 |
| `playbooks/technical.md` | 交易规则：原则、想法（I）、不买（V）、买点（S）、提醒（A） |
| `playbooks/technical-primitives.md` | 规则共用的原语定义（P-*） |
| `docs/sources/` | 原始材料与 Source ID |
| `docs/plans/` | 阶段计划；当前：`phase-2.md` |
| `docs/archive/` | 已被取代的旧文档，只读 |

## 目录

```text
playbooks/          规则（数据）
tradesys/tools/     工具：纯函数 Snapshot → Check
tradesys/run.py     执行器：解析 rule 块并调用工具，不含规则
tradesys/report.py  Markdown 备忘录
tradesys/adapters/  取数（yahoo）与档案 YAML 读取
data/tickers/       档案：一只股票一个 YAML
tests/unit/         测试（规则案例通过真实 playbook 运行）
```
