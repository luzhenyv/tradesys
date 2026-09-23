# 交易方法论代码化 · Architecture Freeze v1.1

> 状态：Architecture Frozen
> 下一阶段：Phase 0 — Rule Specification & Project Skeleton
> 核心原则：**最小化、结构清晰、易于扩展，但不为未来不存在的问题提前设计。**

### v1.1 变更摘要

对照 `docs/sources/` 中的真实规则复核后修订：

1. Veto 拆为 **context / candidate / reminder** 三类，Veto 与 Setup 为平级模块，执行顺序由 engine 决定（§3、§17）。
2. `RuleResult` 增加 `warn` / `manual` / `unavailable` 状态：`warn` 不阻断、由用户决定；后两者承认部分规则无法自动计算（§6、§17）。
3. V1 冻结为**盘后分析**，`as_of` 解析为最近一个已完成交易日（§8）。
4. 新增人工确认结构的存储格式（§10）。
5. Protocol 全部带 `as_of`；新增 `FundamentalSource`；`is_opex_friday` 移出 Protocol（§4）。
6. Feature 输出改为类型化结果，允许序列（§5）。
7. 规则 ID 改为 `V01–V18` / `S01–S09` / `P-*` / `A-*`；Source 使用稳定 ID（§12、§15）。
8. 新增阈值裁决表，记录原始材料之间的冲突；已裁决：盈亏比 1.0 否决 / 1.5 警告、单笔止损 10%、市值 50 亿美元仅警告（§16）。
9. 分时图内容（EP095 / EP111 / EP161）只作为备忘提醒，不转化为代码（§0、§19）。
10. 新增第 8 条纪律"MVP 够用即可"：结构由人在 YAML 中画、机器只判定；实现分 full / simple / stub 三级；数据源只接 yfinance；代码规模软预算（§2、§10、§24）。

---

# 0. V1 范围

| 维度 | V1 |
| --- | --- |
| 市场 | 美股主板（NYSE / NASDAQ）个股 |
| 方向 | 只做多（买点 + 不买原则） |
| 周期 | 日线 |
| 时点 | 盘后分析，为下一交易日制定计划 |
| 输入 | `Ticker + as_of` |
| 输出 | Markdown 交易备忘录 |

不在 V1 范围：做空、期权策略（Sell Put / Covered Call）、日内交易与分时图计算、止盈管理（需要持仓数据，见 §19）。

分时图知识（EP095 / EP111 / EP161）只作为**备忘提醒**出现在报告中（加仓 / 减仓时的注意事项），不转化为代码规则（见 §19）。

---

# 1. 产品定位

这是一个**个人交易辅助决策系统**。

它的第一目标不是自动交易、高频交易、完整量化回测、自动发现策略或自动识别所有技术形态，而是：

> **把个人交易方法论结构化、程序化，并生成一份可检查、可解释、可追溯的交易备忘录。**

V1 最小闭环：

```text
Market Data
    ↓
Features
    ↓
Structures (YAML，人工标注)
    ↓
Context Vetoes
    ↓
Setups → Candidates
    ↓
Candidate Vetoes
    ↓
Markdown Report
```

---

# 2. 七条工程纪律

### 1. 最小化

能用 Python 原生能力解决的问题，不引入额外框架。

### 2. 规则优先

交易方法论是系统的核心资产。代码服务于规则，而不是让规则迁就代码。

### 3. 可测试

每一条进入运行时的交易规则，都必须能够被独立测试。

### 4. 可解释

系统输出必须说明：

```text
为什么产生 Candidate
为什么通过 / 未通过 Veto
哪些规则无法自动判断、需要人工确认
使用了哪些数据与 Feature
```

### 5. 人机协作

机器负责：计算、检查、筛选、提醒。
人负责：确认结构、判断上下文、回答 manual 检查项、最终决策。

### 6. 不过度设计

禁止：PluginManager、Dynamic Loading、Lifecycle Framework、Event Bus、Dependency Injection Framework、Repository Pattern、复杂 ORM。除非未来真实需求证明它们必要。

### 7. Easy to Change

> **稳定的是模型和交易规则；可变化的是数据源和算法实现。**

- 换数据源（IBKR → Yahoo → Polygon）不修改 Veto / Setup / Advice。
- 换 Feature 算法（Volume A → Volume B）不修改交易规则，只要输出类型不变。

### 8. MVP 够用即可

第一版只追求"够用"，严格控制代码规模与复杂度。

- **结构由人画，机器只判定**。Zone、趋势线、颈线、旗形 A/B 线全部来自 `data/structures/<TICKER>.yaml`（§10），V1 不做自动识别。没有 YAML 结构时，依赖结构的规则返回 `MANUAL`，提示"请在 YAML 中标注结构"。
- **实现等级**。rules_spec 中每条规则标注 `Impl`：
  - `full`：算法简单、确定，按规则完整实现
  - `simple`：近似算法，结果 `review=True`，报告标"⚠ 近似算法，需人工复核"
  - `stub`：占位，直接返回 `MANUAL` 并附一句提示
- **一个真实数据源**。V1 只接 yfinance（外加测试用的 fake），IBKR 推迟到 V1.x。
- **规模软预算**。`src/` 约 ≤ 1500 行；每个 V / S 规则文件约 ≤ 50 行。超出时先简化或降级为 `stub`，再考虑加代码。

---

# 3. Architecture Boundary

需要区分两张图：**import 依赖图**（谁可以 import 谁）与**执行顺序**（engine 按什么顺序调用）。

## 3.1 Import 依赖图

```text
            ┌──────────────────────────────────────────┐
            │                 engine.py                │  唯一的编排者
            └──┬──────┬───────┬───────┬───────┬────────┘
               │      │       │       │       │
          adapters features structure vetoes setups  report
               │      │       │       │       │       │
               └──────┴───────┴───┬───┴───────┴───────┘
                                  ▼
                       models.py · protocols.py · config
```

规则：

- `vetoes/`、`setups/`、`report/` 只能 import `models`、`config` 以及纯计算模块（`features/`、`structure/`），**彼此平级、互不 import**。
- `adapters/` 只 import `models` / `protocols`，并且是**唯一**可以 import 第三方数据库（ib_async、yfinance 等）的地方。
- 只有 `engine.py` 同时知道 adapters 和业务层。

禁止：

```python
# ❌ 业务层 import 数据源
from ib_async import ...

# ❌ 业务层按 provider 分支
if provider == "ibkr": ...

# ❌ 字符串列名访问特征
features["rsi_6"]
```

## 3.2 执行顺序（engine）

```text
1. resolve as_of → session_date
2. adapters 拉取数据（bars / chain / calendar / fundamental）
3. features  ← bars
4. structures ← bars + features + confirmed structures (YAML)
5. ctx = AnalysisContext(...)
6. context vetoes      evaluate(ctx)
7. setups              evaluate(ctx) → list[Candidate]
8. candidate vetoes    evaluate(ctx, candidate)
9. reminders           evaluate(ctx)
10. report             render(ctx, results, candidates)
```

即使第 6 步已经产生 veto，第 7–8 步仍然执行，报告中完整展示（便于复盘："如果没有 V01，会产生什么 Candidate"）。最终结论由 Veto 结果决定。

---

# 4. Protocol：只给真正可变的东西

所有数据源方法都必须接受 `as_of`，adapter 不得返回 `as_of` 时点之后才可获得的数据。

```python
class MarketDataSource(Protocol):
    def daily(self, ticker: str, start: date, end: date) -> Bars:
        """end 为 session_date（含），不得返回未完成交易日。"""


class OptionChainSource(Protocol):
    def chain(self, ticker: str, expiry: date, as_of: datetime) -> Chain | None:
        """无法提供 as_of 时点的历史期权链时返回 None。"""


class CalendarSource(Protocol):
    def next_earnings(self, ticker: str, as_of: datetime) -> date | None: ...


class FundamentalSource(Protocol):
    def snapshot(self, ticker: str, as_of: datetime) -> Fundamental | None:
        """市值、交易所、所属板块。"""


class ValuationSource(Protocol):
    def anchor(self, ticker: str, as_of: datetime) -> ValuationAnchor | None: ...


class Feature(Protocol):
    name: str

    def transform(self, bars: Bars) -> FeatureOutput: ...
```

说明：

- `is_opex_friday(d)` 是纯日期计算，放在 `calendar_utils.py`，不属于 Protocol。
- IBKR / Yahoo 均无法提供历史期权链。`as_of` 早于当日时，`chain()` 返回 `None`，Band68 标记为 `unavailable`，**不得用今天的期权链替代**。

## 不强制所有东西 Plugin 化

Zone、Line、Fib 属于基础结构，直接使用普通 Python function / dataclass。V1 不做 Platform、Volume Node、旗形、波浪的自动识别（§2.8）。

---

# 5. Feature 数据边界

> **系统内部不使用 pandas DataFrame 作为跨层数据结构。**

## 5.1 类型化输出

每个 Feature 返回自己的 frozen dataclass，由 `FeatureSet` 以**属性**（而非字符串键）聚合：

```python
@dataclass(frozen=True)
class RsiResult:
    fast: tuple[float, ...]      # RSI-6 序列，与 bars 对齐
    slow: tuple[float, ...]      # RSI-24 序列


@dataclass(frozen=True)
class VolumeResult:
    vs_prev: tuple[float, ...]   # 当日量 / 前一日量
    vs_ma5: tuple[float, ...]    # 当日量 / 前 5 日均量（不含当日）
    ma5: tuple[float, ...]
    state: tuple[VolumeState, ...]  # shrink / expand / neutral，规则见 §16


@dataclass(frozen=True)
class FeatureSet:
    rsi: RsiResult
    volume: VolumeResult
    candles: CandleResult
    streak: StreakResult
```

- 允许序列：背离、连阳、缩量判断都需要历史，而不是单个标量。
- 换算法只要保持输出类型不变，业务层不受影响。
- Feature 之间的依赖（例如背离依赖 RSI）不在 `features/` 内解决，背离属于 `structure/`，输入为 `Bars + FeatureSet`。

## 5.2 dataclass vs Pydantic

冻结为：

- **领域模型：`@dataclass(frozen=True)`**
- **Pydantic 只用于 config.yaml 与 confirmed structures YAML 的加载校验**

---

# 6. Core Models

每个模型给出一行定义和产出层。

| 模型 | 定义 | 产出层 |
| --- | --- | --- |
| `Bar` / `Bars` | 单日 OHLCV / 按日期升序的不可变序列 | adapters |
| `OptionQuote` / `Chain` | 单个合约（strike、type、bid、**ask** 必填）/ 某到期日的期权链 | adapters |
| `Fundamental` | 市值、交易所、板块 | adapters |
| `ValuationAnchor` | 估值区间（低估 / 合理 / 高估边界） | adapters（YAML） |
| `FeatureSet` | §5.1 | features |
| `Zone` | 价格区间 `[low, high]`，带 kind（support / resistance），来自 YAML | structure |
| `Line` | 趋势线 / 颈线（两点定义，可在任意日期求值） | structure |
| `FibLevels` | 某段涨幅的回撤位（38.2 / 50 / 61.8） | structure |
| `BreakVerdict` | 对某 Zone / Line 的判定：`intact / broken / false_break`，**以收盘价为准**（EP272） | structure |
| `PatternHit` | K 线形态命中 + 有效性排序（EP124），V1 只实现 3 种形态 | structure |
| `StructureHit` | 以上结构对象的统一包装，带 evidence | structure |
| `Candidate` | §18 | setups |
| `RuleResult` | 见下 | vetoes / reminders |
| `Band68` | ATM straddle 推导的 68% 区间 `[L, H]` + 到期日（EP189） | `band68.py` |
| `AnalysisContext` | §7 | engine |

```python
class RuleStatus(StrEnum):
    PASS = "pass"                # 规则判断通过
    VETO = "veto"                # 命中，否决
    WARN = "warn"                # 命中警告阈值，不否决，由用户决定
    MANUAL = "manual"            # 需要人工判断（系统无法计算）
    UNAVAILABLE = "unavailable"  # 本应自动计算，但数据缺失


@dataclass(frozen=True)
class RuleResult:
    rule_id: str                 # "V01"
    status: RuleStatus
    reason: str                  # 人可读的解释
    evidence: tuple[str, ...]    # 使用的数值 / 结构
    candidate_id: str | None     # candidate veto 时填写
    review: bool = False         # simple 实现产生的结果，需人工复核
```

---

# 7. Analysis Context

```python
@dataclass(frozen=True)
class AnalysisContext:
    ticker: str
    as_of: datetime
    session_date: date                 # 最近一个已完成交易日
    bars: Bars
    features: FeatureSet
    structures: tuple[StructureHit, ...]
    fundamental: Fundamental | None
    next_earnings: date | None
    band68: Band68 | None
    journal: JournalSlice | None       # V1 可为 None，见 §21
    config: Config
    data_sources: Mapping[str, str]
```

原则：

> `ctx` 是只读上下文，不是万能服务容器。

Feature / Structure / Veto / Setup 可以读取 ctx，但不能通过 ctx 拉数据、修改 ctx、自己创建数据库连接或调用 IBKR。

---

# 8. `as_of` 与 session_date

每一次分析都有 `as_of`，系统必须保证：

> 分析只使用 `as_of` 时点已经可获得的信息。

## V1 冻结规则：盘后分析

原始材料明确：**收盘价是唯一真值**（EP272「收盘定盘为唯一真理」，EP189「收盘价为唯一真值」）。V01、V04、V11 及 S02、S04、S07 都以收盘价判断。

因此：

- `session_date` = `as_of` 之前（含）最近一个**已收盘**的常规交易日。
- 盘中 `as_of`（例如 10:30）解析为**前一交易日**，永远不使用未完成的日线。
- 盘前盘后价格不参与任何计算。

所有数据（Bars、Chain、Fundamental、Calendar、Valuation、Journal、Confirmed Structures）都必须能追溯到对应的时间语义。未来做回测时直接复用。

---

# 9. Data Source Provenance

每份报告记录实际使用的数据源与 fallback：

```python
data_sources = {
    "market": "yahoo",
    "options": "yahoo",
    "calendar": "yahoo",
    "fundamental": "yahoo",
    "valuation": "yaml",
    "structures": "data/structures/META.yaml",
}
```

发生 fallback 时记录为 `"market": "yahoo (fallback: ibkr unavailable)"`。该字典进入 `AnalysisContext` 与报告 metadata。

---

# 10. 人工确认结构（Confirmed Structures）

结构（支撑阻力区间、趋势线、颈线、旗形 A/B 线）**由人在 YAML 中标注，机器只做判定**（§2.8）。YAML 可 diff、可复盘：

```yaml
# data/structures/META.yaml（格式示例；trendline 数值为虚构）
ticker: META
zones:
  - id: z-638-680
    kind: support
    low: 638
    high: 680
    confirmed_at: 2026-09-19
    note: 宽幅区间，可拆为 638–656 / 656–680（EP302 买点1 案例）
    source: EP302
lines:
  - id: downtrend-2026q3
    kind: trendline
    points: [[2026-07-10, 790.0], [2026-08-28, 720.0]]
    confirmed_at: 2026-09-01
```

规则：

- 只有 `confirmed_at <= session_date` 的条目参与分析（遵守 as_of）。
- 结构类规则（V02、V03、V12、V13、S01–S04）在没有对应 YAML 结构时返回 `MANUAL`，提示"请在 YAML 中标注结构"。
- `lines` 的 `kind` 可取 `trendline / neckline / flag_upper / flag_lower`；旗形由 `flag_upper`（A 线）与 `flag_lower`（B 线）两条线表示。

V1 通过直接编辑 YAML 完成确认，不提供 CLI。

---

# 11. Rule 与交易方法论

规则分为：

```text
P-*  Primitive   基础原语（区间、破位判定、相对量能、K 线排序）
V*   Veto        不买原则（EP301）
S*   Setup       买点（EP302）
A-*  Advice      提醒 / 建议
```

> **Rule 本身不是代码。**

规则首先存在于 `docs/rules_spec.md`，代码只是规则的 executable implementation。

---

# 12. Rule Provenance

知识来源：语音日志、LLM 整理的 Summary、讨论、交易复盘。系统必须能回答：

> "这个规则是从哪里来的？"

## 12.1 目录结构

```text
docs/sources/
├── voice/        原始语音转录（原始思想）
└── summaries/    LLM 整理（AI 对原始思想的解释）
```

原始材料与 LLM 材料永远分开。`reports/`、`discussions/` 等目录在出现真实内容时再建。

## 12.2 Source ID

每个来源分配一个**稳定 ID**，规则只引用 ID。

文件命名：`YYYY-MM-DD-<id小写>-<中文短名>.md`，summary 追加 `-summary`，voice 与 summary 同 stem。文件名日期为整理日期（当前统一为 2026-09-23），不是讲座日期。

| Source ID | 主题 | 文件 stem |
| --- | --- | --- |
| EP010 | 成交量与价格关系 | `2026-09-23-ep010-成交量与价格关系` |
| EP124 | K 线见顶止跌形态有效性排序 | `2026-09-23-ep124-K线见顶止跌形态排序` |
| EP150 | 旗形整理 | `2026-09-23-ep150-旗形整理进出场` |
| EP189 | 期权 68% 波动范围 | `2026-09-23-ep189-期权推算波动范围` |
| EP249 | 止盈与短期强弱预警 | `2026-09-23-ep249-止盈与短期强弱预警` |
| EP272 | 开盘价收盘价与支撑压力 | `2026-09-23-ep272-开收盘价与支撑压力` |
| EP292 | 左侧建仓未满即反弹 | `2026-09-23-ep292-左侧建仓未满即反弹` |
| EP301 | 买点避雷 18 条 | `2026-09-23-ep301-18条不买原则` |
| EP302 | 胜率最高的 9 种买点 | `2026-09-23-ep302-9种高胜率买点` |

被引用但尚未入库：EP095、EP111、EP161（均为盘中分时图与分时信息）。未来补充 voice 与 summary。由于 V1 不做日内交易，这三期**只进入 A-INTRADAY 备忘提醒，不产生代码规则**。

引用格式：`EP301§R05`（第 301 期第 5 条）、`EP302§B3`（第 302 期买点 3）、`EP189§SOP`。

## 12.3 Summary frontmatter

每个 summary 的 `src:`（或 `source:`）指向仓库内的语音文件相对路径：

```yaml
src: ../voice/2026-09-23-ep301-18条不买原则.md
```

---

# 13. Summary 使用规则

> **Summary 可以提出 Rule，但不能把 Rule 变成 confirmed rule。**

LLM 摘要会增加原文没有的修辞与机理解释（例如"随后必然伴随剧烈均值回归"）。因此：

> **`confirmed` 规则的 Condition 必须能在 voice 原文中找到依据；只出现在 summary 中的内容最多是 `draft`。**

---

# 14. Rule Lifecycle

```text
Raw Source (voice)
    ↓
Summary                  ┐
    ↓                    │  status = draft
Candidate Rule           │
    ↓                    │
Discussion               ┘
    ↓
Confirmed Rule           status = confirmed
    ↓
Implementation + Test    status = implemented
```

语音不是代码，LLM Summary 也不是代码。最终进入系统的只有 Confirmed Rule。

## Rule 状态

```text
draft        来源中提出，尚未确认（包含 Candidate / Discussion 阶段）
confirmed    已人工确认，有 voice 依据
implemented  已实现且有测试
deprecated   废弃（保留记录）
```

进入 runtime 的只能是 `confirmed` / `implemented`。

---

# 15. `rules_spec.md`

整个系统的**方法论 Source of Truth**。

```markdown
# Trading Rules

## 1. Principles
## 2. Primitives (P-*)
## 3. Veto Rules (V01–V18)
## 4. Setup Rules (S01–S09)
## 5. Advice Rules (A-*)
## 6. Parameters（§16 阈值表的裁决结果）
## 7. Provenance Index
```

每条规则包含：

```text
ID              V05
Name            止损无法确定或幅度超出承受力
Kind            context | candidate | reminder
Definition      ...
Inputs          Candidate.entry, Candidate.stop, config.max_stop_pct
Condition       (entry - stop) / entry > max_stop_pct
Output          VETO / PASS
Automation      auto | manual | partial
Evidence        报告中展示的数值
Source          EP301§R05（voice 原文位置）
Status          draft | confirmed | implemented | deprecated
Test Case       输入 → 期望输出（优先取自原始材料中的案例）
Implementation  src/tradesys/vetoes/v05.py
```

## 15.1 ID 映射

- `V01–V18`：与 EP301 的 18 条顺序一一对应。
- `S01–S09`：与 EP302 的 9 个买点顺序一一对应。

## 15.2 Veto 分类总表

| ID | 名称 | Kind | 所需数据 | V1 自动化 |
| --- | --- | --- | --- | --- |
| V01 | 收盘价创近期新低 | context | bars | auto |
| V02 | 刚破强支撑下沿且逼近阻力 | context | structures | auto |
| V03 | 刚破趋势线 / 61.8% / 颈线 | context | structures | auto |
| V04 | 缩量反弹 | context | bars, volume | auto |
| V05 | 止损无法确定或过宽（> `max_stop_pct`） | candidate | candidate | auto |
| V06 | 板块内前一日跌幅前 10% | context | 板块成分股行情 | **manual**（V1 不做板块扫描） |
| V07 | 阴跌且财报前异常放量加速 | context | bars, calendar | auto |
| V08 | 刚被打止损 | context | journal | manual（Journal 引入前） |
| V09 | 不熟悉基本面、仅因跌幅大 | context | 人的判断 | **manual** |
| V10 | 大跌后社群热议的小盘 / OTC | context | fundamental | partial：OTC → VETO（已确认）；市值 < `min_market_cap` → **WARN**（不否决）；社群热度 manual |
| V11 | 缩量创新高 | context | bars, volume | auto |
| V12 | 突破后悬空远离支撑 | candidate | candidate, structures | auto |
| V13 | 突破即撞下一强阻力下沿 | candidate | candidate, structures | auto |
| V14 | 盈亏比不足 | candidate | candidate | auto：rr < `min_rr` → VETO；`min_rr` ≤ rr < `preferred_rr` → WARN |
| V15 | RSI-6 > 90 | context | features | auto |
| V16 | RSI > 80 且顶背离 | context | features, structure | auto |
| V17 | 盘前盘后非财报消息大涨大跌 | reminder | 盘前盘后数据、新闻 | manual |
| V18 | 开盘前半小时不下单 | reminder | — | 固定提醒 |

V17、V18 在盘后分析模式下无法判断，作为**次日执行提醒**出现在报告的 Advice 区，ID 保持不变。

## 15.3 Setup 总表

| ID | 买点 | 关键结构 / 条件 | 备注 |
| --- | --- | --- | --- |
| S01 | 放量突破强阻力 → 缩量回踩 | Zone, BreakVerdict, 相对量能, PatternHit | |
| S02 | 下行趋势线放量突破 → 缩量回踩不破 | Line, 收盘价 | |
| S03 | 上升旗形放量突破 | YAML 中的 A/B 线, Fib 61.8% | EP150 |
| S04 | W 底 / 头肩底颈线突破回踩 | Line（颈线）, 收盘价 | 分时抵抗仅作为 A-INTRADAY 备忘，不参与判定 |
| S05 | 强势连阳首次阴跌触 MA5 / MA10 | streak, MA | |
| S06 | 极度缩量后放量看涨吞没 | candles, 相对量能 | |
| S07 | 缩量新低后放量锤子线 | candles, EP124 排序 | |
| S08 | 板块突破日龙头放量大阳 | 板块指数行情 | V1 manual（同 V06） |
| S09 | 回撤不破 61.8% + RSI 超卖 + 底背离 + 止跌形态 | Fib, RSI, 背离, PatternHit | |

---

# 16. 阈值裁决表

原始材料之间存在冲突或缺失定义。每一项都是 `config.yaml` 参数，由人裁决后写入 `rules_spec.md §6`，并附来源。

| 参数 | 冲突 / 缺失 | 来源 | 状态 |
| --- | --- | --- | --- |
| `veto.min_rr` | **1.0**：盈亏比低于 1:1 → VETO | EP301§R14, EP302 | 已裁决 |
| `veto.preferred_rr` | **1.5**：1:1 ≤ 盈亏比 < 1:1.5 → WARN | EP301§R14, EP302 | 已裁决 |
| `veto.max_stop_pct` | **0.10**：单笔止损幅度 `(entry - stop) / entry` 超过 10% → VETO（原材料示例为 5%–8%，按个人计划取 10%） | EP301§R05 | 已裁决 |
| `universe.min_market_cap` | **50 亿美元**：低于阈值 → WARN，不否决，最终由用户决定（EP301 / EP302 的 100 亿、200 亿仅作参考） | EP301§R10, EP302 | 已裁决 |
| `recent.lookback_days` | **默认 20**（约一个月）：当日收盘价 < 前 20 个交易日的最低收盘价 → VETO。只比收盘价，不比历史最低价（EP301 voice："和近期的收盘价对比，不是要和历史上最低价去对比"）。报告同时给出"收盘价为 N 日新低"的实际 N，供人工对照 K 线 | EP301§R01 | 默认值，待实盘校准 |
| `volume.baseline` | **同时比较前一日与 MA5**（MA5 取前 5 日，不含当日）。`vs_prev` 与 `vs_ma5` 都 < `shrink_ratio`（默认 1.0）→ 缩量；都 > `expand_ratio`（默认 1.0）→ 放量；两者方向不一致 → 中性。报告同时展示两个比值 | EP010, EP301§R04 | 已裁决 |
| `s09.rsi_oversold` | **默认 20**（RSI-6 < 20 为超卖，按惯例）。注意：EP302 voice 原文说"超卖是 RSI 大于 80"，疑为口误（>80 是超买，见 V16），summary 未反映该问题 | EP302§B9 | 默认值，voice 口误待确认 |
| `v15.rsi_fast_max` | 90 | EP301§R15 | 明确 |
| `v16.rsi_overbought` | 80 | EP301§R16 | 明确 |
| `rsi.periods` | 6 / 24（去掉 12） | EP301§R15, EP302§B9 | 明确 |
| `band68.max_strike_gap_pct` | 2% | EP189 | 明确 |
| 参考胜率 | EP302 说 60–70%；EP124 说 70–80% | — | 仅文档，不入 config |

---

# 17. Veto

Veto 是风险控制，不是可替换的"投资风格"。单条件一票否决（EP301）。

```python
class ContextVeto(Protocol):
    id: str
    def evaluate(self, ctx: AnalysisContext) -> RuleResult: ...


class CandidateVeto(Protocol):
    id: str
    def evaluate(self, ctx: AnalysisContext, candidate: Candidate) -> RuleResult: ...
```

- 18 条规则**全部列出**，自动化程度见 §15.2。`manual` 与 `unavailable` 不等于 `pass`，报告中以人工检查清单呈现。
- `WARN` 不阻断：报告中高亮展示，决定权在用户。
- 最终结论：任一 `VETO` → 不买；无 `VETO` 但存在 `manual` 未确认项 → "待人工确认"；其余情况下有 `WARN` 时结论附带警告列表。

实验配置与正常运行配置必须区分：

```yaml
vetoes:
  disabled: []
```

```bash
tradesys analyze META                        # 正常
tradesys experiment META --disable-veto v11  # 实验（V1 可不实现）
```

---

# 18. Setup 与 Candidate

Setup 使用普通函数：

```python
def evaluate_s01(ctx: AnalysisContext) -> list[Candidate]: ...

SETUPS = {
    "S01": evaluate_s01,
    "S02": evaluate_s02,
}
```

如果未来真的出现复杂 Setup，再演化成 Protocol。

```python
@dataclass(frozen=True)
class Candidate:
    id: str
    setup_id: str            # "S01"
    entry: float
    stop: float | None       # None → V05 必然 VETO
    target: float | None
    rr: float | None
    grade: str
    evidence: tuple[str, ...]
```

Candidate 必须可解释：Setup、Entry、Stop、Target、Why、Supporting evidence，以及每条 candidate veto 的结果。

---

# 19. Advice

V1 的 Advice 只包含**不依赖持仓**的提醒：

- A-V17 / A-V18：次日执行提醒（盘前盘后消息、开盘半小时不下单）
- A-EARN：距财报的交易日数
- A-BAND68：68% 区间与关键结构的对齐（L 是否跌破强支撑 / 61.8%，H 是否超出强阻力，EP189）
- A-INTRADAY：分时图备忘（EP095 / EP111 / EP161），加仓 / 减仓时的盘中注意事项。**固定文本，来自 rules_spec，不做任何计算**

EP249 的止盈体系需要持仓数据，**推迟到 V2**，届时 Journal 增加持仓表。

---

# 20. Report

V1 只输出 Markdown：

```text
Trading Memo
├── Analysis Metadata      ticker, as_of, session_date, data sources, config
├── Conclusion             不买 / 待人工确认 / 存在候选买点
├── Market Overview
├── Features
├── Structures             YAML 结构及其 BreakVerdict
├── Veto Results           pass / veto / warn / manual / unavailable
├── Warnings               所有 warn 项（不阻断，由用户决定）
├── Manual Checklist       所有 manual / unavailable 项
├── Setup Candidates       含 candidate veto 结果
├── Advice / Reminder
└── System Metadata        enabled features / setups, disabled vetoes, simple / stub 规则清单
```

报告本身是一份**可审计的交易决策记录**。

---

# 21. 数据存储

| 数据 | V1 存储 | 用途 |
| --- | --- | --- |
| 行情缓存 | DuckDB | 日线缓存、历史数据、未来回测 |
| Confirmed Structures | YAML（`data/structures/`） | 人工确认的结构 |
| Valuation | YAML | 估值锚 |
| Journal | **V1 不实现**；实现 V08 或 V2 止盈时引入 SQLite | 止损记录、持仓、复盘 |
| Methodology | Markdown | Rules、Sources、Summaries、ADRs |

---

# 22. Architecture 不包含的东西

V1 不做：

```text
❌ 自动下单         ❌ Telegram        ❌ Web UI / React / FastAPI
❌ Plugin Manager   ❌ Dynamic Loading ❌ Event Bus
❌ Agent / RAG / Vector DB / Knowledge Graph
❌ 完整回测系统     ❌ 分时系统        ❌ 全板块扫描
❌ 止盈管理 / 持仓   ❌ 做空与期权策略
```

它们现在不属于产品核心。

---

# 23. 技术栈

```text
Python 3.12
Pydantic      仅 config / YAML 校验
Typer         CLI
PyYAML        YAML 读取
DuckDB        行情缓存
Pytest
Ruff

adapters 专用：yfinance（IBKR / ib_async 推迟到 V1.x）
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

# 24. 工程结构

```text
tradesys/
├── config/
│   └── config.yaml
├── data/
│   ├── structures/            人工确认结构 YAML
│   └── valuation/
├── src/tradesys/
│   ├── models.py
│   ├── protocols.py
│   ├── config.py
│   ├── engine.py
│   ├── calendar_utils.py      is_opex_friday, session_date
│   ├── band68.py
│   ├── adapters/
│   │   ├── yahoo.py           行情、期权链、财报日、市值
│   │   └── fake.py            测试用
│   ├── features/
│   │   ├── volume.py
│   │   ├── candles.py
│   │   ├── rsi.py
│   │   ├── moving_average.py
│   │   └── streak.py
│   ├── structure/
│   │   ├── zones.py           加载 YAML 结构 + BreakVerdict（收盘定盘）
│   │   ├── fib.py
│   │   └── divergence.py
│   ├── vetoes/
│   │   ├── v01.py … v18.py
│   ├── setups/
│   │   ├── s01.py … s09.py
│   ├── advice/
│   │   └── reminders.py
│   └── report/
│       └── markdown.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/
│   ├── rules_spec.md
│   ├── specs/
│   ├── sources/
│   │   ├── voice/
│   │   └── summaries/
│   ├── adr/
│   │   └── 001-easy-to-change.md
│   └── examples/
└── README.md
```

---

# 25. Phase 0

Architecture Freeze 之后不再设计架构。Phase 0 只做四件事：

### ① 项目骨架

`models.py`、`protocols.py`、`engine.py`（空流程）、`config.yaml`、`adapters/fake.py`、`tests/`。

### ② 规则规范

整理 `docs/rules_spec.md`：P-* 原语、V01–V18、S01–S09、A-*，完成 §16 阈值裁决。

### ③ Source Library

- 为 `docs/sources/` 建立 §12.2 的 Source ID 索引。
- 修正 summary frontmatter 的 `src:` 路径。
- 规则条目引用 Source ID。

### ④ 最小测试框架

目标不是"代码运行起来"，而是：

> **每条交易规则都有一个明确的输入 → 输出定义。**

优先使用原始材料中的案例作为 golden test，例如 EP189 TSLA：

```text
Input:   close=164.9, strike=165, call_ask=6.30, put_ask=6.00
Rule:    X = 12.30; K > C → X' = X - (K - C) = 12.20
Output:  Band68 = [152.7, 177.1]
```

---

# 26. 最终原则

> **这是一个把个人交易方法论从非结构化知识转换成可测试规则，并利用真实市场数据生成可解释交易备忘录的最小决策系统。**

技术上：

> **Models define the language. Protocols define the boundaries. Adapters provide the data. Rules define the methodology. Code executes the rules. Markdown records the result.**

工程上：

> **先让方法论正确，再让架构优雅；先让 V1 可用，再让系统可扩展。**
