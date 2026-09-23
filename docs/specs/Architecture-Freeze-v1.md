# 交易方法论代码化 · Architecture Freeze v1.0

> 状态：Architecture Frozen
> 下一阶段：Phase 0 — Rule Specification & Project Skeleton
> 核心原则：**最小化、结构清晰、易于扩展，但不为未来不存在的问题提前设计。**

---

# 1. 产品定位

这是一个**个人交易辅助决策系统**。

它的第一目标不是：

* 自动交易
* 高频交易
* 完整量化回测
* 自动发现交易策略
* 自动识别所有技术形态

而是：

> **把个人交易方法论结构化、程序化，并生成一份可检查、可解释、可追溯的交易备忘录。**

V1 的最小闭环：

```text
Market Data
     ↓
Features
     ↓
Manual / Confirmed Structures
     ↓
Vetoes
     ↓
Setups
     ↓
Markdown Report
```

输入：

```text
Ticker + Analysis As-of
```

输出：

```text
交易备忘录
```

---

# 2. 七条工程纪律

原来的六条纪律保留，并继续增加：

### 1. 最小化

能用 Python 原生能力解决的问题，不引入额外框架。

---

### 2. 规则优先

交易方法论是系统的核心资产。

代码服务于规则，而不是反过来让规则迁就代码。

---

### 3. 可测试

每一条进入运行时的交易规则，都应该能够被独立测试。

---

### 4. 可解释

系统输出的不仅是：

```text
BUY
```

而应该能够说明：

```text
为什么产生 Candidate
为什么通过 / 未通过 Veto
使用了哪些数据
使用了哪些 Feature
```

---

### 5. 人机协作

机器负责：

```text
计算
检查
筛选
提醒
```

人负责：

```text
确认结构
判断上下文
最终决策
```

---

### 6. 不过度设计

禁止：

```text
PluginManager
Dynamic Loading
Lifecycle Framework
Event Bus
Dependency Injection Framework
Repository Pattern
复杂 ORM
```

除非未来真实需求证明它们必要。

---

### 7. Easy to Change

> **稳定的是模型和交易规则；可变化的是数据源和算法实现。**

换数据源：

```text
IBKR → Yahoo → Polygon
```

不应该修改：

```text
Veto
Setup
Advice
```

换 Feature：

```text
Volume A → Volume B
```

不应该修改交易规则本身。

---

# 3. Architecture Boundary

最终架构冻结为：

```text
                    ┌──────────────────┐
                    │     Report       │
                    └────────▲─────────┘
                             │
                    ┌────────┴─────────┐
                    │      Setups      │
                    └────────▲─────────┘
                             │
                    ┌────────┴─────────┐
                    │      Vetoes      │
                    └────────▲─────────┘
                             │
                    ┌────────┴─────────┐
                    │    Structures    │
                    └────────▲─────────┘
                             │
                    ┌────────┴─────────┐
                    │    Features      │
                    └────────▲─────────┘
                             │
                    ┌────────┴─────────┐
                    │    Adapters      │
                    └──────────────────┘

                         Journal
                         Config
                         Models
                         Rules
                         Sources
                         横切
```

依赖方向：

```text
Report
  ↓
Setups
  ↓
Vetoes
  ↓
Structures
  ↓
Features
  ↓
Adapters
```

任何业务层：

> **不得直接依赖具体数据源。**

例如：

```python
# ❌ 禁止
from ib_async import ...

# ❌ 禁止
if provider == "ibkr":
    ...

# ❌ 禁止
df["rsi_6"]
```

---

# 4. Protocol：只给真正可变的东西

最终保留：

```python
class MarketDataSource(Protocol):
    def daily(self, ticker, start, end) -> Bars:
        ...


class OptionChainSource(Protocol):
    def chain(self, ticker, expiry, as_of) -> Chain:
        ...


class CalendarSource(Protocol):
    def next_earnings(self, ticker) -> date | None:
        ...

    def is_opex_friday(self, d: date) -> bool:
        ...


class Feature(Protocol):
    name: str

    def transform(
        self,
        bars: Bars,
    ) -> FeatureResult:
        ...


class ValuationSource(Protocol):
    def anchor(self, ticker: str, as_of: datetime) -> ValuationAnchor:
        ...
```

---

## 不再强制所有东西 Plugin 化

尤其是：

```text
Zone
Trendline
Fib
Platform
Volume Node
```

这些属于系统的**基础结构计算**。

直接使用普通 Python module/function/class。

只有真正具有独立生命周期、未来可能独立启用/关闭的复杂结构，才进入：

```text
structure/plugins/
```

例如：

```text
flag
wave
```

---

# 5. Feature 数据边界

这里按照你的决定冻结：

> **系统内部不使用 pandas DataFrame 作为跨层数据结构。**

Pandas 不作为架构依赖。

Feature 可以完全使用：

```text
dict
list
tuple
dataclass
Pydantic
```

---

## 推荐的数据结构

例如：

```python
@dataclass(frozen=True)
class FeatureValue:
    name: str
    value: float | int | bool | str | None


@dataclass(frozen=True)
class FeatureResult:
    ticker: str
    as_of: datetime
    values: dict[str, FeatureValue]
```

或者对于更复杂的数据：

```python
class FeatureFrame(BaseModel):
    ticker: str
    as_of: datetime
    values: dict[str, Any]
```

关键不是具体选择哪一个，而是：

> **Feature 输出必须是明确的数据对象，而不是一个隐含 schema 的 DataFrame。**

因此：

```text
Feature
   ↓
FeatureResult
   ↓
Veto / Structure / Setup
```

而不是：

```text
Feature
   ↓
DataFrame
   ↓
字符串列名
```

---

# 6. Core Models

最终跨层模型保持小而稳定。

```text
Bar
Bars

OptionQuote
Chain

Fundamental

FeatureResult

Zone
Line
StructureHit

PatternHit
VolumeView
BreakVerdict

Candidate
RuleResult
Advice

Band68
```

同时新增：

```text
AnalysisContext
SourceRef
```

---

# 7. Analysis Context

冻结为：

```python
@dataclass(frozen=True)
class AnalysisContext:
    ticker: str

    as_of: datetime

    bars: Bars

    features: FeatureResult

    structures: list[StructureHit]

    journal: JournalSlice | None

    config: Config

    data_sources: dict[str, str]
```

原则：

> `ctx` 是只读上下文，不是万能服务容器。

Plugin / Feature / Veto / Setup：

```text
可以读取 ctx
```

但是：

```text
不能通过 ctx 拉数据
不能修改 ctx
不能自己创建数据库连接
不能自己调用 IBKR
```

---

# 8. `as_of` 正式成为一级概念

这是本次 Architecture Freeze 新增的重要原则。

每一次分析都有：

```text
analysis_as_of
```

例如：

```text
2026-09-23 10:30:00
```

系统必须尽可能保证：

> 分析只使用 `as_of` 时点已经可获得的信息。

因此：

```text
Bars
OptionChain
Fundamental
Calendar
Valuation
Journal
```

都应该能够追溯到对应的时间语义。

未来做回测时，可以直接复用这个概念。

---

# 9. Data Source Provenance

每份报告应该能够告诉用户：

```text
Market Data: IBKR
Options: IBKR
Calendar: Yahoo
Valuation: YAML
```

如果发生 fallback：

```text
Market Data: Yahoo
Fallback: IBKR unavailable
```

也必须被记录。

因此：

```python
data_sources = {
    "market": "ibkr",
    "options": "ibkr",
    "calendar": "yahoo",
}
```

进入 `AnalysisContext` / Report metadata。

---

# 10. Rule 与交易方法论

这是整个项目最重要的部分。

规则分成：

```text
Rule
Veto
Setup
Advice
```

但是：

> **Rule 本身不是代码。**

规则首先存在于：

```text
docs/rules_spec.md
```

代码只是规则的 executable implementation。

---

# 11. Rule Provenance

这是本次 Architecture Freeze 新增的第二个重要部分。

因为你的知识来源真实存在于：

```text
语音日志
LLM 整理后的 Summary
讨论
报告
交易复盘
```

所以必须能够回答：

> “这个规则是从哪里来的？”

---

## 推荐文件结构

我建议：

```text
docs/
├── rules_spec.md
│
├── sources/
│   ├── voice/
│   │   ├── 2026-08-12-trading-review.md
│   │   ├── 2026-08-15-volume-discussion.md
│   │   └── ...
│   │
│   ├── summaries/
│   │   ├── 2026-08-12-trading-review-summary.md
│   │   ├── 2026-08-15-volume-discussion-summary.md
│   │   └── ...
│   │
│   ├── reports/
│   │   ├── ...
│   │
│   └── discussions/
│       ├── ...
│
├── adr/
│   └── 001-easy-to-change.md
│
└── examples/
    ├── ...
```

这里我建议**原始材料和 LLM 整理材料分开**。

例如：

```text
sources/
├── voice/
└── summaries/
```

这样永远不会混淆：

```text
原始思想
```

和：

```text
AI 对原始思想的解释
```

---

# 12. Source 文件命名

推荐：

```text
YYYY-MM-DD-short-description.md
```

例如：

```text
2026-08-12-trading-review.md
2026-08-15-volume-discussion.md
2026-08-20-buy-point-review.md
```

Summary：

```text
2026-08-12-trading-review-summary.md
```

---

# 13. Summary 文件建议格式

以后你的 LLM 结构化整理，可以统一成：

```markdown
# Trading Review — 2026-08-12

## Summary

...

## Candidate Rules

### R-XXX

...

## Existing Rules Discussed

- R03
- R11

## Questions / Ambiguities

...

## Source

- ../voice/2026-08-12-trading-review.md
```

这里特别重要的是：

> **Summary 可以提出 Rule，但不能自动把 Rule 变成 confirmed rule。**

最终还是人工确认。

---

# 14. Rule Lifecycle

冻结为：

```text
Raw Source
    ↓
Summary
    ↓
Candidate Rule
    ↓
Discussion
    ↓
Confirmed Rule
    ↓
Implementation
    ↓
Test
```

因此：

```text
语音
```

不是代码。

```text
LLM Summary
```

也不是代码。

最终进入系统的是：

```text
Confirmed Rule
```

---

# 15. `rules_spec.md`

最终它是整个系统的**方法论 Source of Truth**。

建议结构：

```markdown
# Trading Rules

## 1. Principles

...

## 2. Veto Rules

### R01
...

### R02
...

## 3. Setup Rules

### S01
...

## 4. Structure Rules

...

## 5. Advice Rules

...

## 6. State Machine

...

## 7. Rule Provenance

...
```

每条规则尽可能包含：

```text
ID
Definition
Inputs
Condition
Output
Evidence
Source
Status
Test Case
Implementation
```

---

# 16. Rule 状态

建议只有：

```text
draft
confirmed
implemented
deprecated
```

不要设计更多状态。

其中：

```text
draft
```

可以存在于 Source / Summary 中。

真正进入 runtime 的只能是：

```text
confirmed
implemented
```

---

# 17. Veto

Veto 是风险控制，不是可替换的“投资风格”。

因此：

```python
class Veto(Protocol):
    id: str

    def evaluate(
        self,
        ctx: AnalysisContext,
    ) -> RuleResult:
        ...
```

18 条规则固定。

可以实验性 disable，但：

> **实验配置和正常运行配置必须区分。**

默认：

```yaml
vetoes:
  disabled: []
```

正常 CLI：

```bash
tradesys analyze META
```

实验：

```bash
tradesys experiment META --disable-veto r11
```

第一版甚至可以先不实现 `experiment`。

核心思想保留即可。

---

# 18. Setup

Setup 不再追求复杂的 Plugin Framework。

可以简单实现为：

```python
def evaluate_s01(ctx) -> list[Candidate]:
    ...
```

然后：

```python
SETUPS = {
    "s01": evaluate_s01,
    "s02": evaluate_s02,
}
```

如果未来真的出现复杂 Setup，再演化成 Protocol。

---

# 19. Candidate

Candidate 是非常重要的业务对象。

```text
Candidate
├── setup_id
├── entry
├── stop
├── target
├── rr
├── grade
└── evidence
```

原则：

> Candidate 必须可解释。

不能只产生：

```text
BUY META
```

必须能够解释：

```text
Setup:
    S02

Entry:
    ...

Stop:
    ...

Target:
    ...

Why:
    ...

Supporting evidence:
    ...

Veto:
    passed / rejected
```

---

# 20. Report

V1 只输出 Markdown。

报告结构：

```text
Trading Memo
│
├── Analysis Metadata
│   ├── ticker
│   ├── as_of
│   ├── data sources
│   └── configuration
│
├── Market Overview
│
├── Features
│
├── Structures
│
├── Veto Results
│
├── Setup Candidates
│
├── Advice / Reminder
│
└── System Metadata
    ├── enabled features
    ├── enabled setups
    ├── disabled vetoes
    └── stub modules
```

这样一份报告本身就是一个**可审计的交易决策记录**。

---

# 21. Architecture 不包含的东西

明确冻结：

V1 不做：

```text
❌ 自动下单
❌ Telegram
❌ Web UI
❌ React
❌ FastAPI
❌ Plugin Manager
❌ Dynamic Loading
❌ Event Bus
❌ Agent
❌ RAG
❌ Vector DB
❌ Knowledge Graph
❌ 完整回测系统
❌ 分时系统
❌ 全板块扫描
```

这些都可以未来做。

但：

> **它们现在不属于产品核心。**

---

# 22. 技术栈

最终冻结：

```text
Python 3.12

Pydantic
Typer
Pytest
Ruff
DuckDB
SQLite
```

原则：

```text
Markdown > Database
Python > Framework
Function > Class
Config > Code Change
Protocol > Concrete Dependency
```

---

# 23. 数据存储

### Market Data

```text
DuckDB
```

用于：

```text
行情缓存
历史数据
未来回测
```

---

### Journal

```text
SQLite
```

用于：

```text
交易日志
人工确认
状态
复盘
```

---

### Methodology

```text
Markdown
```

用于：

```text
Rules
Sources
Summaries
ADRs
```

这个划分我建议长期保持。

---

# 24. 最终工程结构

综合这次修改，我建议冻结为：

```text
tradesys/
│
├── config/
│   └── config.yaml
│
├── src/
│   └── tradesys/
│       │
│       ├── models.py
│       ├── protocols.py
│       ├── engine.py
│       │
│       ├── adapters/
│       │   ├── ibkr.py
│       │   ├── yahoo.py
│       │   └── fake.py
│       │
│       ├── features/
│       │   ├── volume.py
│       │   ├── breakout.py
│       │   ├── candles.py
│       │   ├── rsi.py
│       │   ├── divergence.py
│       │   └── streak.py
│       │
│       ├── structure/
│       │   ├── zones.py
│       │   ├── trendlines.py
│       │   ├── fib.py
│       │   ├── platforms.py
│       │   └── plugins/
│       │       └── flag.py
│       │
│       ├── vetoes/
│       │   ├── r01.py
│       │   ├── r02.py
│       │   └── ...
│       │
│       ├── setups/
│       │   ├── s01.py
│       │   ├── s02.py
│       │   ├── s03_bull_flag.py
│       │   └── ...
│       │
│       ├── journal/
│       │
│       └── report/
│           └── markdown.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── docs/
│   │
│   ├── rules_spec.md
│   │
│   ├── sources/
│   │   ├── voice/
│   │   ├── summaries/
│   │   ├── reports/
│   │   └── discussions/
│   │
│   ├── adr/
│   │   └── 001-easy-to-change.md
│   │
│   └── examples/
│
└── README.md
```

---

# 25. 最终 Dependency Rule

这是整个架构最重要的一张图：

```text
                 ┌─────────────┐
                 │   Report    │
                 └──────┬──────┘
                        │
                 ┌──────▼──────┐
                 │   Setups    │
                 └──────┬──────┘
                        │
                 ┌──────▼──────┐
                 │   Vetoes    │
                 └──────┬──────┘
                        │
                 ┌──────▼──────┐
                 │ Structures  │
                 └──────┬──────┘
                        │
                 ┌──────▼──────┐
                 │  Features   │
                 └──────┬──────┘
                        │
                 ┌──────▼──────┐
                 │  Protocol   │
                 └──────┬──────┘
                        │
              ┌─────────▼─────────┐
              │     Adapters      │
              └───────────────────┘
```

任何箭头都不能反过来。

尤其：

```text
Veto → IBKR        ❌
Setup → Yahoo      ❌
Report → yfinance  ❌
```

只能：

```text
Veto → Model / Context
Setup → Model / Context
Adapter → Protocol
```

---

# 26. Phase 0

Architecture Freeze 之后，下一阶段不再设计架构。

Phase 0 只做四件事情：

### ① 建立项目骨架

```text
models.py
protocols.py
engine.py
config.yaml
tests/
```

---

### ② 建立规则规范

把现有真实材料整理成：

```text
docs/rules_spec.md
```

包括：

```text
18 Vetoes
V1 Setups
核心原语
状态机
68%
买点
结构定义
```

---

### ③ 建立 Source Library

把你现有的：

```text
原始语音转录
LLM Summary
报告
讨论
```

放入：

```text
docs/sources/
```

并建立 provenance。

---

### ④ 建立最小测试框架

最终目标不是：

> “代码运行起来。”

而是：

> **每条交易规则都有一个明确的输入 → 输出定义。**

例如：

```text
Input:
    price
    fib_618
    close

Rule:
    close < fib_618

Output:
    veto = true
```

这才是之后 Phase 1–6 真正的基础。

---

# 27. Architecture Freeze 的最终原则

最后，我建议把整个项目压缩成下面这句话：

> **这是一个把个人交易方法论从非结构化知识转换成可测试规则，并利用真实市场数据生成可解释交易备忘录的最小决策系统。**

技术上：

> **Models define the language. Protocols define the boundaries. Adapters provide the data. Rules define the methodology. Code executes the rules. Markdown records the result.**

而在工程上，我们坚持：

> **先让方法论正确，再让架构优雅；先让 V1 可用，再让系统可扩展。**