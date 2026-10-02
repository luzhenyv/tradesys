# 交易方法论代码化 · Architecture Freeze v1.1

> **已归档（2026-10-01）**：被 `docs/DESIGN.md` 取代。仅作历史参考，不再维护。

> 状态：Architecture Frozen
> 阶段计划：`docs/plans/`（Phase 0 已完成，Phase 1 待开始）
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
8. 原始材料之间的阈值冲突全部裁决，结果记录在 rules_spec §6（§16）。
9. 分时图内容（EP095 / EP111 / EP161）只作为备忘提醒，不转化为代码（§0、§19）。
10. 新增第 8 条纪律"MVP 够用即可"：结构由人在 YAML 中画、机器只判定；实现分 full / simple / stub 三级；数据源只接 yfinance；代码规模软预算（§2、§10、§24）。
11. Phase 0 落地后同步：包目录为仓库根下的 `tradesys/`；`AnalysisContext` 用 `zones` / `lines` 取代 `structures`；`Candidate.rr` 改为计算属性（§7、§18、§24）。
12. 新增第 9 条纪律"Unix 哲学：小工具 + 调度"；取消 `FeatureSet` 与 `Feature` / `Valuation` Protocol，特征改为按需调用的纯函数；规则表与阈值表只保留在 rules_spec；阶段计划移至 `docs/plans/`（§2、§5、§15、§16）。

此后的变化以 git 历史为准，本摘要不再追加。

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

# 2. 九条工程纪律

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
- **规模软预算**。`tradesys/` 包约 ≤ 1500 行；每个 V / S 规则文件约 ≤ 50 行。超出时先简化或降级为 `stub`，再考虑加代码。

### 9. Unix 哲学：小工具 + 调度

系统是一组专门、短小的工具，而不是一个全能函数。

- **一个工具只做一件事**。工具是纯函数：输入数据、输出数据，不读全局状态、不做 I/O。I/O 只出现在 `adapters/` 与 CLI。
- **数据是通用接口**。工具之间只传 frozen dataclass，都能经 `serialize.py` 转为 JSON。任何一步的输出都可以落盘、查看，或交给下一步。
- **调度与计算分离**。`engine.py` 只负责按顺序调用工具，不写规则逻辑；规则逻辑只在各自的工具文件里。
- **为 agent 编排预留，但不提前建设**。现阶段由 engine 调度；CLI 子命令可单独调用并用 JSON 串联。将来由 skill / agent 直接编排这些子命令，现在不写任何 agent 代码。
- **文档先行**。新工具先在 rules_spec / AF 有条目，再写代码；工具文件 docstring 首行引用条目 ID。
- **拆分有上限**。只在确实需要单独调用或单独测试时才拆成新工具，不为拆而拆；仍受 §2.8 约束。

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
I/O（adapters / 文件）
1. fetch_bars / chain / calendar / fundamental   ← adapters
2. load_structures                               ← data/structures/<TICKER>.yaml

纯函数（工具）
3. ctx = make_context(bars, as_of, ...)          as_of → session_date，截取 bars
4. context vetoes      vNN.evaluate(ctx)         特征由规则按需调用 features/ 纯函数
5. setups              sNN.evaluate(ctx) → list[Candidate]
6. candidate vetoes    vNN.evaluate(ctx, candidate)
7. reminders           advice(ctx)
8. result = AnalysisResult(ctx, results, candidates, advice)
9. render_markdown(result)
```

即使第 4 步已经产生 veto，第 5–6 步仍然执行，报告中完整展示（便于复盘："如果没有 V01，会产生什么 Candidate"）。最终结论由 Veto 结果决定。

engine 只做这里列出的调度（§2.9），不包含任何规则判断。I/O 只在第 1–2 步；第 3–9 步都是纯函数，每一步的输出都可以序列化为 JSON。

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

```

Protocol 只用于数据源边界。规则与特征是普通函数，用类型别名描述签名即可（§17）。

说明：

- `is_opex_friday(d)` 是纯日期计算，放在 `calendar_utils.py`，不属于 Protocol。
- IBKR / Yahoo 均无法提供历史期权链。`as_of` 早于当日时，`chain()` 返回 `None`，Band68 标记为 `unavailable`，**不得用今天的期权链替代**。

## 不强制所有东西 Plugin 化

Zone、Line、Fib 属于基础结构，直接使用普通 Python function / dataclass。V1 不做 Platform、Volume Node、旗形、波浪的自动识别（§2.8）。

---

# 5. Feature 数据边界

> **系统内部不使用 pandas DataFrame 作为跨层数据结构。**

## 5.1 特征是按需调用的纯函数

每个特征是 `features/` 中的一个纯函数，输入 `Bars`（或其序列）与配置，返回自己的 frozen dataclass 或简单值。不设中央的 `FeatureSet`，也不预先计算后塞进 ctx：规则需要哪个特征就调用哪个，报告展示特征时也调用同一组函数。日线只有约 250 根，重复计算的成本可以忽略。

```python
@dataclass(frozen=True)
class RsiResult:
    fast: tuple[float, ...]      # RSI-6 序列，与 bars 对齐
    slow: tuple[float, ...]      # RSI-24 序列


@dataclass(frozen=True)
class VolumeResult:
    vs_prev: tuple[float | None, ...]   # 当日量 / 前一日量
    vs_ma5: tuple[float | None, ...]    # 当日量 / 前 5 日均量（不含当日）
    state: tuple[VolumeState, ...]      # shrink / expand / neutral，规则见 rules_spec P-VOL


def volume(bars: Bars, cfg: VolumeConfig) -> VolumeResult: ...
def rsi(closes: tuple[float, ...], period: int) -> tuple[float, ...]: ...
```

- 允许序列：背离、连阳、缩量判断都需要历史，而不是单个标量。
- 换算法只要保持输出类型不变，业务层不受影响。
- 特征之间的依赖（例如背离依赖 RSI）由调用方组合：`structure/divergence.py` 自己调用 `rsi()`。

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
| `VolumeResult` 等 | 各特征函数的输出（§5.1） | features |
| `Zone` | 价格区间 `[low, high]`，带 kind（support / resistance），来自 YAML | structure |
| `Line` | 趋势线 / 颈线（两点定义，可在任意日期求值） | structure |
| `FibLevels` | 某段涨幅的回撤位（38.2 / 50 / 61.8） | structure |
| `BreakVerdict` | 对某 Zone / Line 的判定：`intact / broken / false_break`，**以收盘价为准**（EP272） | structure |
| `PatternHit` | K 线形态命中 + 有效性排序（EP124），V1 只实现 3 种形态 | structure |
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
    bars: Bars                         # 截止 session_date；特征按需从 bars 计算
    config: Config
    data_sources: Mapping[str, str]
    zones: tuple[Zone, ...] = ()       # 来自 YAML（§10）
    lines: tuple[Line, ...] = ()       # 来自 YAML（§10）
    fundamental: Fundamental | None = None
    next_earnings: date | None = None
    band68: Band68 | None = None
    journal: object | None = None      # JournalSlice，V1 未实现，见 §21
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

所有数据（Bars、Chain、Fundamental、Calendar、Journal、Confirmed Structures）都必须能追溯到对应的时间语义。未来做回测时直接复用。

---

# 9. Data Source Provenance

每份报告记录实际使用的数据源与 fallback：

```python
data_sources = {
    "market": "yahoo",
    "options": "yahoo",
    "calendar": "yahoo",
    "fundamental": "yahoo",
    "structures": "data/structures/AMD.yaml",
}
```

发生 fallback 时记录为 `"market": "yahoo (fallback: ibkr unavailable)"`。该字典进入 `AnalysisContext` 与报告 AMDdata。

---

# 10. 人工确认结构（Confirmed Structures）

结构（支撑阻力区间、趋势线、颈线、旗形 A/B 线）**由人在 YAML 中标注，机器只做判定**（§2.8）。YAML 可 diff、可复盘：

```yaml
# data/structures/AMD.yaml（格式示例；trendline 数值为虚构）
ticker: AMD
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
## 6. Parameters（全部可配置阈值，与 config.yaml 一一对应）
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
Implementation  tradesys/vetoes/v05.py
```

## 15.1 ID 映射与规则清单

- `V01–V18`：与 EP301 的 18 条顺序一一对应；`S01–S09`：与 EP302 的 9 个买点一一对应。
- 每条规则的 Kind、所需数据、Impl 等级只记录在 rules_spec 条目中，本文件不重复列表。
- V17、V18 在盘后分析模式下无法判断，作为次日执行提醒出现在报告的 Advice 区，ID 保持不变。

---

# 16. 阈值

原始材料之间的阈值冲突已全部裁决。参数、默认值、含义与来源只记录在 rules_spec §6，并与 `config/config.yaml` 一一对应；本文件不重复。

---

# 17. Veto

Veto 是风险控制，不是可替换的"投资风格"。单条件一票否决（EP301）。

```python
# engine.py：每条规则是 vetoes/vNN.py 中的 evaluate 函数，用字典注册
ContextVeto = Callable[[AnalysisContext], RuleResult]
CandidateVeto = Callable[[AnalysisContext, Candidate], RuleResult]
```

- 18 条规则**全部列出**，自动化程度见 rules_spec 各条目的 `Impl` 字段。`manual` 与 `unavailable` 不等于 `pass`，报告中以人工检查清单呈现。
- `WARN` 不阻断：报告中高亮展示，决定权在用户。
- 最终结论：任一 `VETO` → 不买；无 `VETO` 但存在 `manual` 未确认项 → "待人工确认"；其余情况下有 `WARN` 时结论附带警告列表。

实验配置与正常运行配置必须区分：

```yaml
vetoes:
  disabled: []
```

```bash
tradesys analyze AMD                        # 正常
tradesys experiment AMD --disable-veto v11  # 实验（V1 可不实现）
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
    target: float | None     # None → V14 返回 MANUAL
    grade: str
    evidence: tuple[str, ...] = ()

    @property
    def rr(self) -> float | None:
        """(target − entry) / (entry − stop)；缺 stop / target 时为 None。"""
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
├── Analysis AMDdata      ticker, as_of, session_date, data sources, config
├── Conclusion             不买 / 待人工确认 / 存在候选买点
├── Market Overview
├── Features
├── Structures             YAML 结构及其 BreakVerdict
├── Veto Results           pass / veto / warn / manual / unavailable
├── Warnings               所有 warn 项（不阻断，由用户决定）
├── Manual Checklist       所有 manual / unavailable 项
├── Setup Candidates       含 candidate veto 结果
├── Advice / Reminder
└── System AMDdata        enabled features / setups, disabled vetoes, simple / stub 规则清单
```

报告本身是一份**可审计的交易决策记录**。

---

# 21. 数据存储

| 数据 | V1 存储 | 用途 |
| --- | --- | --- |
| 行情缓存 | **推迟**：Phase 1 ①完成后视 yfinance 速度再定（候选 DuckDB） | 日线缓存、历史数据、未来回测 |
| Confirmed Structures | YAML（`data/structures/`） | 人工确认的结构 |
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
DuckDB        行情缓存（推迟，见 §21）
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
│   └── structures/            人工确认结构 YAML
├── pyproject.toml             uv 项目，Python 3.12
├── tradesys/                  Python 包（不使用 src/ 布局）
│   ├── models.py
│   ├── protocols.py
│   ├── config.py
│   ├── engine.py              只调度（§2.9）
│   ├── serialize.py           dataclass ⇄ JSON，工具间通用接口
│   ├── cli.py                 Phase 1 ⑥
│   ├── calendar_utils.py      is_opex_friday, session_date
│   ├── band68.py
│   ├── adapters/
│   │   ├── yahoo.py           行情、期权链、财报日、市值
│   │   └── fake.py            测试用
│   ├── features/
│   │   ├── volume.py
│   │   ├── price.py           近期新低 / 新高
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
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── CLAUDE.md                  开发守则入口
├── docs/
│   ├── rules_spec.md
│   ├── specs/
│   ├── plans/                 阶段计划（phase-0.md、phase-1.md）
│   ├── sources/
│   │   ├── voice/
│   │   └── summaries/
│   ├── adr/
│   │   └── 001-easy-to-change.md
│   └── examples/
└── README.md
```

---

# 25. 最终原则

> **这是一个把个人交易方法论从非结构化知识转换成可测试规则，并利用真实市场数据生成可解释交易备忘录的最小决策系统。**

技术上：

> **Models define the language. Protocols define the boundaries. Adapters provide the data. Rules define the methodology. Code executes the rules. Markdown records the result.**

工程上：

> **先让方法论正确，再让架构优雅；先让 V1 可用，再让系统可扩展。**
