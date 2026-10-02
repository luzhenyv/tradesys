# Playbook · 技术面（technical）

> 方法论 Source of Truth：自然语言规则 + 可执行的 rule 块。代码只提供工具，执行器按本文件调用工具（`docs/DESIGN.md`）。
> 运行：`tradesys run playbooks/technical.md < snapshot.json`
> 版本：v0.4（全部规则 `confirmed`；已加 rule 块的规则见文末）

## 阅读约定

- **ID**：`P-*` 原语，`V01–V18` 不买原则（EP301 顺序），`S01–S09` 买点（EP302 顺序），`A-*` 提醒。
- **Source**：`EP301§R05` = 第 301 期第 5 条，`EP302§B3` = 第 302 期买点 3。Source ID 见 `docs/DESIGN.md` §8，对应文件为 `docs/sources/{voice,summaries}/2026-09-23-<id小写>-*.md`。
- **Status**：全部已 `confirmed`（已人工核对 voice 原文）。以后修改任何规则，需先改回 `draft`，重新核对后再确认。
- **Voice 核对**：`✔` 表示已在 voice 原文中找到依据；`待核对` 表示目前只依据 summary。
- **Impl**（DESIGN §9，MVP 够用即可）：
  - `full`：完整实现
  - `simple`：近似算法，结果 `review=True`，报告标"⚠ 近似算法，需人工复核"
  - `stub`：占位，返回 MANUAL
  - `YAML`：结构由人在 `data/structures/<TICKER>.yaml` 中标注，无结构时返回 MANUAL；人在 `absent` 中确认不存在的结构（`zone / trendline / neckline / flag`），相关规则判为不适用（False）。旗形线每种只保留一条；顶层 `exchange:` 为人工确认的交易所代码，供历史回放
- **rule 块**：规则的可执行部分（语法见 DESIGN §4）。阈值就写在 rule 块里，注释标注参数名与状态（`已裁决` 用户决定 / `source` 原文给出 / `默认值` 待实盘校准）。正文中的 `veto.max_stop_pct` 等是参数的说明性名字。没有 rule 块的规则尚未实现，执行器跳过。
- **结果状态**：`PASS / VETO / WARN / MANUAL / UNAVAILABLE`（DESIGN §3）。
- **时点**：所有规则在 `session_date`（最近一个已收盘交易日）上求值，记为 **T**；T-1 为前一交易日。

---

# 1. Principles

以下原则约束所有规则的写法，不直接对应代码。

| # | 原则 | Source |
| --- | --- | --- |
| 1 | **单条件一票否决**。命中任一 V 规则即不买，不做"虽然…但是…"的多条件自我合理化 | EP301 |
| 2 | **宁可错过，绝不做错** | EP301, EP124 |
| 3 | **收盘价是唯一真值**。破位、突破、新低、新高一律以常规时段收盘价判定；盘中刺破与盘前盘后价格不作为判定依据 | EP272, EP189, EP150 |
| 4 | **盈亏比至少 1:1，最好 1:1.5 以上**。脱离盈亏比谈胜率没有意义 | EP301§R14, EP302 |
| 5 | **结构位置第一，K 线形态第二**。脱离支撑阻力谈形态无效 | EP124 |
| 6 | **成交量验真**。放量形成的形态 / 突破 / 破位才有效；缩量的有待验证 | EP010, EP124 |
| 7 | 高胜率买点的现实上限约 60–70%，不存在 80–90% 的"神化买点"。仅作认知背景，不入代码 | EP302 |
| 8 | **规则服务于实盘**。不为某只股票硬找旗形、头肩顶；图上没有的结构，人在 YAML `absent` 中声明，相关规则即不适用 | 用户裁决 2026-10-02 |
| 9 | **不知道等于不买**。已实现的判定规则无法判断（MANUAL / UNAVAILABLE）时，不给出买入结论 | 用户裁决 2026-10-02 |

---

# 2. Primitives

原语是 V / S 规则共同使用的判定积木。每个原语只有一个实现，规则不得自行重写。

### P-TREND 趋势方向

- **Impl**：simple（MA20 近似）
- **Definition**：判定 T 日所处的短期趋势。
- **Condition**：
  - `down`：`close[T] < MA20[T]` 且 `MA20[T] < MA20[T-5]`
  - `up`：`close[T] > MA20[T]` 且 `MA20[T] > MA20[T-5]`
  - 其他：`sideways`
- **Source**：EP302 voice（"低点不断在创新低……收盘价不断的在创新低，这是很明显的下跌趋势"）。MA20 口径为默认实现，待校准。
- **Status**：confirmed

### P-SWING 摆动点

- **Impl**：simple（k=2 分形）
- **Definition**：局部高点 / 低点，用于趋势线、旗形、背离。
- **Condition**：`high[t]` 高于左右各 `swing.k` 根 K 线的 high 即为 swing high；low 同理。
- **Default**：`swing.k = 2`
- **Status**：confirmed

### P-NEWLOW / P-NEWHIGH 近期新低 / 新高

- **Impl**：full
- **Condition**：
  - 近期新低：`close[T] < min(close[T-N .. T-1])`
  - 近期新高：`close[T] > max(close[T-N .. T-1])`
  - `N = recent.lookback_days`（默认 20）
- **Evidence**：同时输出"收盘价为 K 日新低 / 新高"的实际 K 值（向前数到第一个更低 / 更高收盘价为止）。
- **Source**：EP301§R01 voice ✔（"和近期的收盘价对比，不是要和历史上最低价去对比"）
- **Status**：confirmed

### P-VOL 量能状态

- **Impl**：full
- **Definition**：
  - `vs_prev[T] = vol[T] / vol[T-1]`
  - `vs_ma5[T] = vol[T] / mean(vol[T-5 .. T-1])`（不含当日）
- **Condition**：
  - `shrink`：`vs_prev < volume.shrink_ratio` 且 `vs_ma5 < volume.shrink_ratio`
  - `expand`：`vs_prev > volume.expand_ratio` 且 `vs_ma5 > volume.expand_ratio`
  - 其他：`neutral`
- **OpEx 折扣**：T 为月度期权交割周五（`is_opex_friday`）时，`expand` 在 evidence 中标注"OpEx 放量，有效性打折"（EP249）。不改变状态。
- **Source**：EP010（前一日对比 + 均量对比）、EP301§R04 voice ✔（"和前5天比……和成交量的5日均线比"）、EP249
- **Status**：confirmed

### P-ZONE 支撑阻力区间

- **Impl**：YAML（不自动识别）
- **Definition**：`Zone(low, high, kind)`，支撑阻力是**区间**而非单点。
- **来源**：只来自 `data/structures/<TICKER>.yaml`（DESIGN §6）。人在画区间时参考成交密集区、横盘平台（EP249：连续 2–5 日窄幅横盘）、前高前低；V1 不自动识别。
- **Rule**：单一均线 / 单一趋势线 / 单一前低点的有效性打折（EP272），报告中注明。
- **Status**：confirmed

### P-BREAK 突破 / 破位判定（BreakVerdict）

- **Impl**：full（对 YAML 结构判定）
- **Definition**：对 Zone 或 Line 输出 `intact / broken / false_break / reclaimed`。
- **Condition**（以支撑区间 `[low, high]` 为例）：
  - 盘中 `low[T] < zone.low` 但 `close[T] ≥ zone.low` → `false_break`（盘中刺破无效）
  - `close[T] < zone.low` → `broken`，区间极性翻转为**阻力**
  - 已 `broken` 后，只有 `close > zone.high` 才算 `reclaimed`（收复）。反弹到区间内部仍视为阻力测试
  - 阻力区间镜像：`close > zone.high` → 突破，极性翻转为支撑
  - Line：`close[T]` 与 `line(T)` 比较
- **附加**：记录破位 / 突破当日的量能状态（放量破位 = 有效；缩量破位 = 有待观察，EP010 法则三）。
- **Source**：EP272（100–120 区间案例）、EP010、EP150
- **Test Case**（EP272）：
  - 支撑 100–120；盘中 99，收盘 100.5 → `false_break`
  - 收盘 95 → `broken`
  - 次日收盘 105 → 仍为 `broken`（在阻力区内反抽）
  - 之后收盘 121 → `reclaimed`
- **Status**：confirmed

### P-FIB 斐波那契回撤

- **Impl**：simple（摆动点取自 YAML；缺省用近 60 日最低收盘 → 最高收盘）
- **Definition**：对一段上涨（swing low → swing high）计算 38.2 / 50 / 61.8% 回撤位。
- **Rule**：回撤守在 61.8% 之上为良性回撤；**收盘价**跌破 61.8% → 上涨结构失效（EP150、EP301§R03）。
- **Status**：confirmed

### P-CANDLE K 线形态与有效性排序

- **Impl**：simple（V1 只实现锤子线、看涨吞没、流星线的一级判定；其余形态 stub）
- **Definition**：输出 `PatternHit(name, tier, volume_ok, neutral)`。
- **止跌形态排序（高 → 低）**：锤子线 > 看涨吞没 > 启明星 > 倒锤子线 > 看涨孕线
- **见顶形态排序（高 → 低）**：流星线 > 上吊线 > 看跌吞没 > 黄昏之星 > 看跌孕线
- **几何要件**：

| 形态 | 要件 |
| --- | --- |
| 锤子线 | 下影线 ≥ 2 × 实体；上影线极短或无；出现在下跌中 |
| 看涨吞没 | T-1 阴线；T 阳线实体完全覆盖 T-1 实体。一级：T 开盘 < T-1 low 且收盘 > T-1 high（全包络） |
| 启明星 | 大阴线 + 星线（小实体，影线长于实体）+ 大阳线；第三根实体上沿超过第一根实体中点；实体间有重叠，不可大幅跳空 |
| 倒锤子线 | 上影线 ≥ 2 × 实体；下影线极短或无；出现在下跌中 |
| 看涨孕线 | T-1 大阴线；T 小阳线（含影线）完全位于 T-1 实体内 |

- **强制条件**：
  - 锤子线、吞没、启明星第三根**必须放量**（P-VOL = `expand`），否则 `volume_ok = false`，有效性降级。
  - 形态当日收盘价为近期新低（P-NEWLOW）→ `neutral = true`，需再观察 1–2 个交易日（EP124、EP301§R01、EP302§B7）。
  - 孕线始终视为中性预警。
- **"极短影线"阈值**：`candle.short_shadow_ratio`（影线 ≤ 全日振幅的该比例，默认 0.1）。
- **Source**：EP124（细分变体排序见 summary §三）。启明星、倒锤子线、孕线及见顶序列的其余形态在 V1 为 stub，报告提示人工看图
- **Status**：confirmed

### P-RSI / P-DIVERGENCE

- **Impl**：P-RSI full；P-DIVERGENCE simple（最近两个摆动点）
- **P-RSI**：Wilder RSI，周期 `rsi.periods = [6, 24]`，不使用 12（EP301§R15、EP302§B9）。
- **P-DIVERGENCE**：
  - 顶背离：最近两个 swing high 中，价格高点抬高（或持平），RSI-6 对应高点降低
  - 底背离：最近两个 swing low 中，价格低点降低（或持平），RSI-6 与 RSI-24 对应低点均抬高
  - 两个 swing 点间隔 ≤ `divergence.max_gap_days`（默认 30）
- **Status**：confirmed

### P-BAND68 期权 68% 波动区间

- **Impl**：full
- **Definition**（EP189 七步法）：
  1. 到期日：`band68.expiry`（默认下一个月度交割日；若财报在到期前，报告标注）
  2. `C` = T 日常规时段收盘价
  3. `K` = 距 C 最近的行权价；`|K − C| / C > band68.max_strike_gap_pct`（2%）→ `UNAVAILABLE`
  4. `X = call_ask(K) + put_ask(K)`，**必须用 Ask**
  5. `K > C` → `X' = X − (K − C)`；`K < C` → `X' = X + (C − K)`
  6. `Band68 = [C − X', C + X']`
- **as_of**：无法获得 T 日期权链 → `UNAVAILABLE`，不得用当日期权链替代（DESIGN §6）。
- **Test Case**：
  - TSLA：C=164.9，K=165，call 6.30 + put 6.00 → X=12.30，X'=12.20 → **[152.7, 177.1]**
  - NVDA：C=880，K=880，call 29.0 + put 27.1 → **[823.9, 936.1]**
- **Status**：confirmed

---

# 3. Veto Rules

Kind：`context` = `evaluate(ctx)`；`candidate` = `evaluate(ctx, candidate)`；`reminder` = 次日提醒。

## 3.1 下跌过程（V01–V10）

### V01 收盘价创近期新低

- **Impl**：full
- **Kind**：context
- **Condition**：P-NEWLOW 成立
- **Output**：VETO。evidence 包括"收盘价为 K 日新低"。
- **Automation**：auto
- **Source**：EP301§R01 · Voice 核对 ✔
- **Test Case**：20 日收盘最低 100，T 收盘 99.5 → VETO；T 收盘 100.2 → PASS
```rule
kind: veto
when:
  - new_low: {n: 20}          # recent.lookback_days · 默认值，待实盘校准
```
- **Status**：confirmed

### V02 刚跌破强支撑下沿

- **Impl**：YAML（无结构 → MANUAL）
- **Kind**：context
- **Condition**：存在支撑 Zone 在最近 `recent.break_days`（默认 2）个交易日内 P-BREAK = `broken`，且至今未 `reclaimed`
- **Output**：VETO。evidence 包括原支撑区间（现为阻力）与破位日。
- **Automation**：auto（依赖 YAML 中的 Zone）
- **Source**：EP301§R02 · Voice 核对 ✔（"刚出现这种情况的，或者是出现一两天"）
- **Test Case**：支撑 100–120，T-1 收盘 99 → VETO
```rule
kind: veto
when:
  - zone_broken_within: {kind: support, days: 2}   # recent.break_days · 默认值
```
- **Status**：confirmed

### V03 刚跌破上行趋势线 / 61.8% / 顶部颈线

- **Impl**：YAML（无结构 → MANUAL；Fib 部分 simple）
- **Kind**：context
- **Condition**：最近 `recent.break_days` 个交易日内，以下任一对象出现 P-BREAK = `broken`：
  - 上行趋势线
  - 大结构 Fib 61.8%
  - M 顶 / 头肩顶颈线
- **Output**：VETO
- **Automation**：auto（趋势线 / 颈线来自 YAML）
- **Source**：EP301§R03 · Voice 核对 ✔
```rule
kind: veto
when:
  - line_broken_within: {kind: trendline, days: 2, side: below}   # recent.break_days · 默认值
```

```rule
kind: veto
when:
  - line_broken_within: {kind: neckline, days: 2, side: below}
```

```rule
kind: veto
trust: review
when:
  - fib_broken: {level: 0.618, days: 2}   # P-FIB simple · 近 60 日
```
- **Status**：confirmed

### V04 缩量反弹

- **Impl**：full
- **Kind**：context
- **Condition**（任一）：
  1. `close[T] > close[T-1]` 且 P-VOL[T] = `shrink`
  2. 最近 5 日收盘价整体上行（`close[T] > close[T-5]`），同时成交量逐日萎缩、量能 MA5 拐头向下（`MA5vol[T] < MA5vol[T-1]`）
- **Output**：VETO
- **Automation**：auto
- **Source**：EP301§R04 · Voice 核对 ✔
```rule
kind: veto
when:
  - close_up: {n: 1}                 # 收盘价高于前一日 · source
  - volume_state: {state: shrink}
```

```rule
kind: veto
when:
  - close_up: {n: 5}                 # 近 5 日收盘整体上行 · source
  - volume_declining: {n: 5}         # 成交量逐日萎缩 · source
  - volume_ma5_turning_down: {}
```
- **Status**：confirmed

### V05 止损无法确定或超出承受力

- **Impl**：full
- **Kind**：candidate
- **Condition**：
  - `candidate.stop is None` → VETO（止损无法确定）
  - `(entry − stop) / entry > veto.max_stop_pct`（10%）→ VETO
- **Output**：VETO / PASS。evidence 包括止损幅度百分比。
- **Automation**：auto
- **Source**：EP301§R05 · Voice 核对 ✔（"有的朋友觉得10%止损不大，那你没问题，你可以买"）
- **Test Case**（EP301）：
  - 支撑 100–120，entry 119，stop 100 → 16% → VETO
  - entry 109，stop 100 → 8.3% → PASS
```rule
kind: veto
scope: candidate
when:
  - stop_wider_than: {pct: 0.10}   # veto.max_stop_pct · 已裁决
```
- **Status**：confirmed

### V06 所属板块前一日跌幅前 10%

- **Impl**：stub（MANUAL）
- **Kind**：context
- **Condition**：T 日个股跌幅在所属板块成分股中排名前 10%（30 只取前 3，50 只取前 5）
- **Output**：MANUAL（V1 不做板块扫描）。报告提示用户自查。
- **Automation**：manual
- **Source**：EP301§R06 · Voice 核对 ✔
```rule
kind: manual
ask: T-1 日该股跌幅是否位列所属板块成分股前 10%？（V1 不做板块扫描，请自查）
```
- **Status**：confirmed

### V07 持续下跌且财报前异常放量加速

- **Impl**：full（"无利空消息"部分 MANUAL）
- **Kind**：context
- **Condition**（全部满足）：
  - P-TREND = `down`
  - 距下一次财报 ≤ `v07.earnings_window_days`（默认 2）个交易日
  - `close[T] / close[T-1] − 1 ≤ −v07.min_drop_pct`（默认 3%）
  - P-VOL[T] = `expand`
- **Output**：VETO。"无明显利空消息"一项无法计算，evidence 中提示人工确认。
- **Automation**：partial
- **Source**：EP301§R07 · Voice 核对 ✔（"财报就是明天后天……突然间开始异常下跌，而且还放量了"）。`min_drop_pct` 为默认值，待校准。
```rule
kind: veto
say: 请确认无明显利空消息
when:
  - trend: {direction: down}              # P-TREND simple · 默认实现
  - days_to_earnings: {max: 2}            # v07.earnings_window_days · 默认值
  - drop_pct: {min: 0.03}                 # v07.min_drop_pct · 默认值，待实盘校准
  - volume_state: {state: expand}
```
- **Status**：confirmed

### V08 刚被打止损

- **Impl**：stub（MANUAL，Journal 引入前）
- **Kind**：context
- **Condition**：该标的在 `v08.cooldown_days`（默认 5）个交易日内有止损记录
- **Output**：V1 为 MANUAL（Journal 未实现）；Journal 引入后改为 auto
- **Automation**：manual
- **Source**：EP301§R08 · Voice 核对 ✔。`cooldown_days` 为默认值（原文"数日"）。
```rule
kind: manual
ask: 最近 5 个交易日内是否在该股上被打过止损？（Journal 未实现，请自查）
```
- **Status**：confirmed

### V09 不熟悉基本面、仅因跌幅大而"看似便宜"

- **Impl**：stub（MANUAL）
- **Kind**：context
- **Output**：MANUAL（报告固定提问："你是否长期跟踪过该公司基本面？"）
- **Automation**：manual
- **Source**：EP301§R09 · Voice 核对 ✔
```rule
kind: manual
ask: 你是否长期跟踪过该公司基本面？若只是因为跌幅大而觉得便宜，不买。
```
- **Status**：confirmed

### V10 小市值 / OTC / 社群热度

- **Impl**：full（OTC / 市值）+ stub（社群热度）
- **Kind**：context
- **Condition**：
  - 非 NYSE / NASDAQ 主板（OTC）→ VETO
  - 市值 < `universe.min_market_cap`（50 亿美元）→ WARN（不否决，由用户决定）
  - 大跌后社群热度异常 → MANUAL（见 V10b）
  - `Fundamental` 缺失 → UNAVAILABLE
- **Automation**：partial
- **Source**：EP301§R10、EP302 · Voice 核对 ✔（"100亿以内的相对来讲都缺乏一些稳定性"）
```rule
kind: veto
when:
  - exchange_not_in: {codes: [NYQ, NYS, NMS, NGM, NCM, NAS, ASE, PCX]}  # 主板 · 已裁决
```

```rule
kind: warn
when:
  - market_cap_below: {usd: 5000000000}  # universe.min_market_cap · source 50 亿
```

- **Status**：confirmed

### V10b 大跌后社群热度异常

- **Impl**：stub（从 V10 拆出：与市值 WARN 同属一段时会被 if / elif 遮蔽，而小市值时最需要问）
- **Source**：EP301§R10
```rule
kind: manual
ask: 大跌后社群热度是否异常？（V1 不做社群数据，请自查）
```

## 3.2 上涨过程（V11–V16）

### V11 缩量创新高

- **Impl**：full
- **Kind**：context
- **Condition**：P-NEWHIGH 成立且 P-VOL[T] = `shrink`
- **Output**：VETO
- **Automation**：auto
- **Source**：EP301§R11 · Voice 核对 ✔
```rule
kind: veto
when:
  - new_high: {n: 20}         # recent.lookback_days · 默认值，待实盘校准
  - volume_state: {state: shrink}
```
- **Status**：confirmed

### V12 突破后悬空、远离支撑

- **Impl**：YAML（无结构 → MANUAL）
- **Kind**：candidate
- **Condition**：`(entry − nearest_support.high) / entry > v12.max_distance_pct`
  - `nearest_support` 为 entry 下方最近的支撑区间
  - `v12.max_distance_pct` 默认 10%，与 `veto.max_stop_pct` 取值相同但独立配置
- **Output**：VETO
- **Automation**：auto
- **Note**：与 V05 的区别在于，V05 看候选自带的 stop，V12 看结构支撑的距离。止损设得紧、但下方没有结构支撑时，V12 仍然否决。
- **Source**：EP301§R12 · Voice 核对 ✔（"大涨百分之十几……远离了支撑，中间悬空状态的……不能买"，SNOW +16% 案例）
```rule
kind: veto
scope: candidate
when:
  - far_from_support: {pct: 0.10}   # v12.max_distance_pct · 已裁决
```
- **Status**：confirmed

### V13 突破前阻力、但开盘直接顶入下一强阻力下沿

- **Impl**：YAML（无结构 → MANUAL）
- **Kind**：candidate
- **Condition**（全部满足）：
  - T 日突破了一个阻力区间（P-BREAK 突破）
  - entry 上方存在下一个阻力区间 R2
  - `(R2.low − entry) / entry < v13.min_room_pct`（默认 2%）
- **Output**：VETO
- **Automation**：auto
- **Source**：EP301§R13 · Voice 核对 ✔
- **Test Case**：价格 75，阻力 80–90 与 100–110；跳空开盘 99 → VETO
```rule
kind: veto
scope: candidate
when:
  - zone_broken_within: {kind: resistance, days: 2}
  - tight_to_resistance: {pct: 0.02}   # v13.min_room_pct · 默认值
```
- **Status**：confirmed

### V14 盈亏比不足

- **Impl**：full
- **Kind**：candidate
- **Condition**：`rr = (target − entry) / (entry − stop)`
  - `rr < veto.min_rr`（1.0）→ VETO
  - `veto.min_rr ≤ rr < veto.preferred_rr`（1.5）→ WARN
  - `target is None`（上方无结构阻力）→ MANUAL，提示人工设定目标
- **Automation**：auto
- **Source**：EP301§R14、EP302 · Voice 核对 ✔（"你20块钱的止损上方至少要涨20块钱的预期，你才能够实现1:1"）
- **Test Case**（EP301）：entry 125，stop 100，target 142 → rr 0.68 → VETO
```rule
kind: veto
scope: candidate
when:
  - rr_below: {x: 1.0}        # veto.min_rr · 已裁决
```

```rule
kind: warn
scope: candidate
when:
  - rr_below: {x: 1.5}        # veto.preferred_rr · 已裁决
```
- **Status**：confirmed

### V15 RSI-6 > 90

- **Impl**：full
- **Kind**：context
- **Condition**：`RSI6[T] > v15.rsi_fast_max`（90）
- **Output**：VETO
- **Automation**：auto
- **Source**：EP301§R15 · Voice 核对 ✔
```rule
kind: veto
when:
  - rsi_above: {period: 6, x: 90}    # v15.rsi_fast_max · source
```
- **Status**：confirmed

### V16 RSI 超买区顶背离

- **Impl**：simple（依赖 P-DIVERGENCE）
- **Kind**：context
- **Condition**：`RSI6[T] > v16.rsi_overbought`（80）且 P-DIVERGENCE 顶背离成立
- **Output**：VETO
- **Automation**：auto
- **Source**：EP301§R16 · Voice 核对 ✔
```rule
kind: veto
trust: review
when:
  - rsi_above: {period: 6, x: 80}        # v16.rsi_overbought · source
  - divergence: {kind: top, max_gap: 30, k: 2}
```
- **Status**：confirmed

## 3.3 特殊场景（V17–V18）

盘后分析模式下无法判断，作为次日执行提醒出现在报告 Advice 区，见 A-V17 / A-V18。

---

# 4. Setup Rules

## 4.1 通用约定

- 每个 Setup 输出 `list[Candidate]`，字段为 `entry / stop / target / rr / grade / evidence`。
- **entry** 默认为触发日 T 的收盘价（盘后分析，作为次日计划参考价）。
- **target** 默认为 entry 上方最近阻力区间的 `low`；没有则为 `None`（V14 → MANUAL）。
- **stop** 按各 Setup 定义，统一预留 `stop.buffer_pct`（默认 1%）以防扫损（EP150）。
- **grade**：
  - `A`：形态一级 + 量能确认，且未使用 simple 近似
  - `B`：满足条件，但形态非一级或用到 simple 近似（`review=True`）
  - `C`：形态 `neutral`
- 所有 Candidate 都会经过 candidate vetoes（V05、V12、V13、V14）。

### S01 放量突破强阻力 → 缩量回踩突破区间

- **Impl**：YAML（无结构 → MANUAL）
- **Condition**：
  1. 最近 `s01.lookback_days`（默认 20）内，某阻力 Zone 被放量突破（P-BREAK 突破且当日 P-VOL = `expand`）
  2. 之后回踩进入该 Zone，回踩期间量能 `shrink` 或 `neutral`，且收盘未跌破 `zone.low`
  3. 触发（二选一）：
     - A：T 日在区间内出现止跌形态（P-CANDLE）
     - B：T 日出现放量阳线（`close > open` 且 `expand`）
- **Stop**：`zone.low × (1 − stop.buffer_pct)`
- **Source**：EP302§B1 · Voice 核对 ✔（案例：AMD 638–680 区间）
```rule
kind: setup
when:
  - retest_breakout: {lookback: 20}   # s01.lookback_days · 默认值
  - stop_candle: {}
entry: {session_close: {}}
stop: {buffered_zone_low: {lookback: 20, pct: 0.01}}
target: {nearest_resistance: {}}
```

```rule
kind: setup
when:
  - retest_breakout: {lookback: 20}
  - green_expand: {}
entry: {session_close: {}}
stop: {buffered_zone_low: {lookback: 20, pct: 0.01}}
target: {nearest_resistance: {}}
```
- **Status**：confirmed

### S02 下行趋势线放量突破 → 缩量回踩不破

- **Impl**：YAML（无结构 → MANUAL）
- **Condition**：
  1. 下行趋势 Line 在最近 `s02.lookback_days`（默认 20）内被放量突破
  2. 此后每日收盘均在 Line 之上
  3. T 日缩量，且 `(close − line(T)) / close ≤ s02.near_line_pct`（默认 3%）
- **Stop**：`line(T) × (1 − stop.buffer_pct)`
- **Note**：激进模式（突破当日直接买）不实现。
- **Source**：EP302§B2 · Voice 核对 ✔
```rule
kind: setup
when:
  - retest_line: {kind: trendline, side: above, lookback: 20, slope: down, near_pct: 0.03}
  - volume_state: {state: shrink}
entry: {session_close: {}}
stop: {buffered_line: {kind: trendline, side: above, lookback: 20, slope: down, pct: 0.01}}
target: {nearest_resistance: {}}
```
- **Status**：confirmed

### S03 上升旗形放量突破 A 线

- **Impl**：YAML（旗杆与 A/B 线都由人画，不自动识别旗形）
- **Condition**（EP150）：
  1. 旗杆：YAML 中的 `flag_pole`（p1 = 杆底，p2 = 杆顶），期间平均量能高于杆底前 20 日均量
  2. 旗面：杆顶之后；YAML 中的 `flag_upper`（A 线）与 `flag_lower`（B 线），由人画出向下通道
  3. 旗面平均量能 < 旗杆平均量能；旗面内无持续放量大阴线
  4. 旗面最低收盘价 ≥ 旗杆 Fib 61.8%
  5. T 日放量阳线收盘 > A 线
- **Stop**：`B(T) × (1 − stop.buffer_pct)`
- **Target**：T1 = 旗杆顶；T2 = entry + (旗杆顶 − 旗杆底)。Candidate.target 取 T1，T2 写入 evidence。
- **Note**：B 线左侧买点（EP150）暂不实现，作为未来的 S03b。
- **Source**：EP302§B3、EP150 · Voice 核对 ✔
```rule
kind: setup
when:
  - flag_break: {pre: 20}     # s03.pre_pole_days · source「其前 20 日」
  - green_expand: {}
entry: {session_close: {}}
stop: {buffered_flag_lower: {pct: 0.01}}
target: {flag_pole_high: {}}
```
- **Status**：confirmed

### S04 W 底 / 头肩底颈线突破 → 回踩不破

- **Impl**：YAML（颈线由 YAML 给出）
- **Condition**：
  1. 颈线（YAML 中 `kind: neckline` 的 Line）在最近 `s04.lookback_days`（默认 20）内被放量突破
  2. 此后收盘价未跌回颈线下方（以收盘 / 开盘价为准，忽略影线）
  3. T 日 `low` 触及颈线 `± s04.touch_pct`（默认 2%），且收盘在颈线之上
- **Stop**：`neckline(T) × (1 − stop.buffer_pct)`
- **分时**：原文"分时主动买盘强抵抗"只作为 A-INTRADAY 备忘，不参与判定。
- **Source**：EP302§B4 · Voice 核对 ✔
```rule
kind: setup
when:
  - retest_line: {kind: neckline, side: above, lookback: 20, touch_pct: 0.02}
entry: {session_close: {}}
stop: {buffered_line: {kind: neckline, side: above, lookback: 20, pct: 0.01}}
target: {nearest_resistance: {}}
```
- **Status**：confirmed

### S05 强势连阳后首次阴线回踩 MA5 / MA10

- **Impl**：simple
- **Condition**：
  1. T 日之前连续收涨 ≥ `s05.min_streak` 日（默认 5）
  2. T 日为连涨后的**第一根**收跌 K 线（`close[T] < close[T-1]`）
  3. `low[T] ≤ MA5[T]`（或 MA10），且 `close[T] ≥` 该均线
- **排除**：连涨后连续多日阴跌才慢慢靠近均线 → 不成立。第 2 条已保证。
- **Stop**：`low[T] × (1 − stop.buffer_pct)`
- **Note**：原文强调此类止损常偏大，V05 / V14 会自然过滤。
- **Source**：EP302§B5 · Voice 核对 ✔（"第一次下跌收跌，它就回踩到了最近的一条MA……连续几个阴跌跌下来，慢慢摸到均线，无效"）。`min_streak` 为默认值。
```rule
kind: setup
trust: review
when:
  - up_streak: {n: 5}                 # s05.min_streak · 默认值
  - first_down: {}
  - pullback_to_ma: {n: 5}
entry: {session_close: {}}
stop: {buffered_low: {pct: 0.01}}     # stop.buffer_pct · 默认值
target: {nearest_resistance: {}}
```

```rule
kind: setup
trust: review
when:
  - up_streak: {n: 5}
  - first_down: {}
  - pullback_to_ma: {n: 10}
entry: {session_close: {}}
stop: {buffered_low: {pct: 0.01}}
target: {nearest_resistance: {}}
```
- **Status**：confirmed

### S06 极度缩量后放量看涨吞没

- **Impl**：simple
- **Condition**：
  1. P-TREND ∈ {`down`, `sideways`}（下跌中或下跌后横盘）
  2. T-1：`vs_prev < s06.dry_ratio` 且 `vs_ma5 < s06.dry_ratio`（默认 0.6，"极度缩量"）
  3. T：一级看涨吞没（实体包裹 T-1 全部实体与影线），P-VOL = `expand`，上影线 ≤ `candle.short_shadow_ratio`
- **Stop**：`low[T] × (1 − stop.buffer_pct)`
- **Source**：EP302§B6 · Voice 核对 ✔
```rule
kind: setup
trust: review
when:
  - trend: {direction: down}
  - volume_dry: {ratio: 0.6, offset: 1}          # s06.dry_ratio · 默认值
  - bullish_engulfing: {short_shadow_ratio: 0.1}   # 只认一级吞没 · source
  - volume_state: {state: expand}
entry: {session_close: {}}
stop: {buffered_low: {pct: 0.01}}
target: {nearest_resistance: {}}
```

```rule
kind: setup
trust: review
when:
  - trend: {direction: sideways}
  - volume_dry: {ratio: 0.6, offset: 1}
  - bullish_engulfing: {short_shadow_ratio: 0.1}   # 只认一级吞没 · source
  - volume_state: {state: expand}
entry: {session_close: {}}
stop: {buffered_low: {pct: 0.01}}
target: {nearest_resistance: {}}
```
- **Status**：confirmed

### S07 缩量新低后放量锤子线

- **Impl**：simple
- **Condition**：
  1. P-TREND = `down`
  2. T-1：P-NEWLOW 成立且 P-VOL = `shrink`
  3. T：锤子线，P-VOL = `expand`
- **Grade**：T 日收盘仍为近期新低 → `C`（中性，等待 1 个交易日）。此时 V01 也会否决。
- **Stop**：`low[T] × (1 − stop.buffer_pct)`
- **Source**：EP302§B7、EP124 · Voice 核对 ✔
```rule
kind: setup
trust: review
when:
  - trend: {direction: down}
  - new_low: {n: 20, offset: 1}
  - volume_state: {state: shrink, offset: 1}
  - hammer: {}
  - volume_state: {state: expand}
entry: {session_close: {}}
stop: {buffered_low: {pct: 0.01}}
target: {nearest_resistance: {}}
```
- **Status**：confirmed

### S08 板块突破日龙头放量大阳

- **Impl**：stub（MANUAL）
- **Output**：不产生 Candidate，报告中为 MANUAL 提示（V1 不做板块数据）
- **Source**：EP302§B8 · Voice 核对 ✔
```rule
kind: manual
ask: 今日所属板块指数是否突破？该股是否为放量实体大阳突破最近阻力的龙头？（V1 不做板块数据，请自查）
```
- **Status**：confirmed

### S09 上行回撤不破 61.8% + RSI 超卖 + 底背离 + 止跌形态

- **Impl**：simple
- **Condition**（全部满足）：
  1. 大结构上行，回撤收盘价始终在 Fib 61.8% 之上
  2. 最近 `divergence.max_gap_days` 内 `RSI6 < s09.rsi_oversold`（默认 20）
  3. P-DIVERGENCE 底背离（RSI-6 与 RSI-24）
  4. T 日在支撑区域出现止跌形态（P-CANDLE，不要求排序）
- **Stop**：`fib_618 × (1 − stop.buffer_pct)`
- **Target**：回撤起点的 swing high
- **Note**：voice 原文"超卖是RSI大于80"为口误，按惯例取 RSI-6 < 20，已确认。
- **Source**：EP302§B9 · Voice 核对 ✔（发现口误）
```rule
kind: setup
trust: review
when:
  - fib_holds: {level: 0.618}
  - rsi_below_within: {period: 6, x: 20, days: 30}
  - divergence: {kind: bottom, max_gap: 30, k: 2}
  - stop_candle: {}
entry: {session_close: {}}
stop: {fib_stop: {level: 0.618, pct: 0.01}}
target: {impulse_high: {}}
```
- **Status**：confirmed

---

# 5. Advice Rules

Advice 只提醒，不影响结论（`kind: advice`，DESIGN §4）。命中时 `say` 与工具证据进入报告「提醒」。

### A-V17 盘前盘后异动不参与

- **Source**：EP301§R17、EP272
```rule
kind: advice
say: 非财报的盘前盘后大涨大跌不参与，以常规时段开盘为准
```

### A-V18 开盘半小时不下单

- **Source**：EP301§R18
```rule
kind: advice
say: 美东 9:30–10:00 不下单
```

### A-EARN 财报临近

- **Source**：EP301§R07、EP189。到期日前有财报时，Band68 含财报波动。
```rule
kind: advice
say: 财报临近，Band68 含财报波动
when:
  - days_to_earnings: {max: 5}     # a_earn.highlight_days · 默认值
```

### A-BAND68 Band68 区间

- **Source**：EP189（算法见 P-BAND68）
```rule
kind: advice
when:
  - band68_range: {max_strike_gap_pct: 0.02}   # band68.max_strike_gap_pct · source
```

### A-BAND68-SUP Band68 下沿触及支撑

- **Source**：EP189
```rule
kind: advice
say: Band68 下沿可能跌破最近支撑
when:
  - band68_edge: {against: support, max_strike_gap_pct: 0.02}
```

### A-BAND68-RES Band68 上沿超出阻力

- **Source**：EP189
```rule
kind: advice
say: Band68 上沿可能超出最近阻力
when:
  - band68_edge: {against: resistance, max_strike_gap_pct: 0.02}
```

### A-BAND68-FIB Band68 下沿低于 Fib 61.8%

- **Source**：EP189（期权在定价破位）
```rule
kind: advice
say: Band68 下沿低于 Fib 61.8%，期权在定价破位
when:
  - band68_edge: {against: fib, level: 0.618, max_strike_gap_pct: 0.02}
```

### A-TOP 见顶形态

- **Source**：EP124、EP302§B1 案例
```rule
kind: advice
say: 见顶形态（流星线），当天不宜抄底 / 追高
when:
  - shooting_star: {short_shadow_ratio: 0.1}
```

### A-INTRADAY 分时图备忘

- **Source**：EP095、EP111、EP161（未入库）
```rule
kind: advice
say: 分时图备忘待 EP095 / EP111 / EP161 入库
```

**推迟到 V2**（需要持仓数据）：

- A-TP：三维止盈体系与短期强弱四原则（EP249）
- A-LEFT：左侧建仓未满即反弹的应对（EP292）

---

# 6. Provenance Index

| Source | 规则 |
| --- | --- |
| EP010 | P-VOL, P-BREAK |
| EP124 | P-CANDLE, S07, A-TOP |
| EP150 | P-FIB, S03, `stop.buffer_pct` |
| EP189 | P-BAND68, A-BAND68, A-EARN |
| EP249 | P-VOL（OpEx 折扣）, P-ZONE（平台）；A-TP（V2） |
| EP272 | P-BREAK, P-ZONE, Principle 3, A-V17 |
| EP301 | V01–V18, Principles 1–2 |
| EP302 | S01–S09, Principles 4, 7, V10 市值 |
| EP292 | A-LEFT（V2） |
| EP095 / EP111 / EP161 | A-INTRADAY（未入库） |

## 后续工作

- 实盘校准 rule 块中注释为"默认值"的参数，校准后改为"已裁决"。
- 为其余规则补上 rule 块（见 `docs/plans/phase-1.md`）。已加：V01–V16、V10b、S01–S09、A-*。
