# 规则库

> 节点定义。参数、`kind`、`scope`、`trust` 冻结在此。原语见 `primitives.md`；策略见同目录 workflow。
> 修改规则须核对 `docs/sources/voice/`。

# 2. 想法（I）

回答写在档案里（`docs/WORKFLOW.md` §3）；`fact` / `ttl` 见 `docs/DESIGN.md` §8。

### I01 写下想法理由

- **条件**：想买之前，先写下为什么想买、消息从哪来。没有理由 → 不买，先提问。
- **来源**：用户裁决 2026-10-02（冲动冷却；为复盘留下依据）
```rule
kind: veto
ask: 为什么想买？请在档案 idea 中写下 reason（理由）与 source（news / research / chart / impulse）
when:
  - fact: {key: idea.reason}
```

# 3. 不买原则（V）

## 3.1 下跌过程

### V01 收盘价创近期新低

- **条件**：P-NEWLOW 成立。
- **来源**：EP301§R01
- **案例**：20 日收盘最低 100，T 收盘 99.5 → VETO；T 收盘 100.2 → PASS
```rule
kind: veto
when:
  - new_low: {n: 20}          # recent.lookback_days · 默认值，待实盘校准
```

### V02 刚跌破强支撑下沿

- **条件**：某支撑区间在最近 2 个交易日内 P-BREAK = broken，且至今未收复。
- **来源**：EP301§R02（"刚出现这种情况的，或者是出现一两天"）
- **案例**：支撑 100–120，T-1 收盘 99 → VETO
```rule
kind: veto
when:
  - zone_broken_within: {kind: support, days: 2}   # recent.break_days · 默认值
```

### V03 刚跌破上行趋势线 / 61.8% / 顶部颈线

- **条件**：最近 2 个交易日内，上行趋势线、大结构 Fib 61.8%、M 顶 / 头肩顶颈线中任一出现 P-BREAK = broken。
- **来源**：EP301§R03
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

### V04 缩量反弹

- **条件**（任一）：
  1. `close[T] > close[T-1]` 且 P-VOL = shrink
  2. 近 5 日收盘整体上行（`close[T] > close[T-5]`），同时成交量逐日萎缩、量能 MA5 拐头向下
- **来源**：EP301§R04
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

### V05 止损无法确定或超出承受力

- **条件**（每个候选）：没有止损，或 `(entry − stop) / entry > 10%`。
- **来源**：EP301§R05（"有的朋友觉得10%止损不大，那你没问题，你可以买"）
- **案例**（EP301）：支撑 100–120，entry 119、stop 100 → 16% → VETO；entry 109、stop 100 → 8.3% → PASS
```rule
kind: veto
scope: candidate
when:
  - stop_wider_than: {pct: 0.10}   # veto.max_stop_pct · 已裁决
```

### V06 所属板块前一日跌幅前 10%

- **条件**：T 日（买入日的前一交易日）个股跌幅在所属板块成分股中排名前 10%（30 只取前 3，50 只取前 5）。不做板块扫描，由人回答。
- **来源**：EP301§R06（"跌幅排在前五的，前一交易日不要去碰它"）
```rule
kind: veto
ask: T 日（最近收盘日）该股跌幅是否位列所属板块成分股前 10%？（不做板块扫描，请自查后回答）
when:
  - fact: {key: v06.sector_top_loser, is: true, ttl: 1}   # 只针对 T · 默认值
```

### V07 持续下跌且财报前异常放量加速

- **条件**（全部）：P-TREND = down；距下次财报 ≤ 2 个交易日；T 日跌幅 ≥ 3%；P-VOL = expand；且**没有**明显利空消息（下跌无法解释，像是提前收到风声）。消息面由人回答；前四项不全成立时不提问。
- **来源**：EP301§R07（"财报就是明天后天……突然间开始异常下跌，而且还放量了，也没有什么太多的利空消息，这种情况不要买"）
```rule
kind: veto
ask: 这次下跌有明显的利空消息吗？没有 → 回答 v07.no_bad_news = true
when:
  - trend: {direction: down}              # P-TREND simple · 默认实现
  - days_to_earnings: {max: 2}            # v07.earnings_window_days · 默认值
  - drop_pct: {min: 0.03}                 # v07.min_drop_pct · 默认值，待实盘校准
  - volume_state: {state: expand}
  - fact: {key: v07.no_bad_news, is: true, ttl: 1}   # 消息面变化快 · 默认值
```

### V08 刚被打止损

- **条件**：最近一次止损日期距 T 不足 5 个交易日。没有止损记录则回答 `false`。日志驱动之前由人回答。
- **来源**：EP301§R08（原文"数日"）
```rule
kind: veto
ask: 最近一次在该股上被打止损的日期？（v08.stopped_out：日期，或 false 表示没有）
when:
  - fact: {key: v08.stopped_out, within: 5}   # 数日 · 默认值
```

### V09 不熟悉基本面、仅因跌幅大而"看似便宜"

- **条件**：不熟悉公司基本面。把「熟悉」拆成 9 个是 / 否问题，至少 7 项为「是」才算熟悉；问题可增删。

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

- **来源**：EP301§R09
```rule
kind: veto
ask: 请回答基本面熟悉度清单（v09.*，见上表）；若只是因为跌幅大而觉得便宜，不买
when:
  - checklist: {keys: [v09.business, v09.revenue_mix, v09.last_earnings, v09.growth, v09.margin, v09.guidance, v09.competitors, v09.catalyst, v09.tracked], min: 7, ttl: 63}   # 7/9 · 默认值；63 ≈ 一季度
```

### V10 小市值 / OTC

- **条件**：非 NYSE / NASDAQ 主板 → VETO；市值 < 50 亿美元 → WARN（由人决定）。
- **来源**：EP301§R10、EP302（"100亿以内的相对来讲都缺乏一些稳定性"）
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

### V10b 大跌后社群热度异常

- **条件**：大跌后社群热度异常。不做社群数据，由人回答。从 V10 拆出，避免被市值 WARN 遮蔽。
- **来源**：EP301§R10
```rule
kind: veto
ask: 大跌后社群热度是否异常？（不做社群数据，请自查后回答 v10b.social_hype）
when:
  - fact: {key: v10b.social_hype, is: true, ttl: 5}   # 约一周 · 默认值
```

## 3.2 上涨过程

### V11 缩量创新高

- **条件**：P-NEWHIGH 成立且 P-VOL = shrink。
- **来源**：EP301§R11
```rule
kind: veto
when:
  - new_high: {n: 20}         # recent.lookback_days · 默认值，待实盘校准
  - volume_state: {state: shrink}
```

### V12 突破后悬空、远离支撑

- **条件**（每个候选）：entry 距下方最近支撑区间上沿超过 10%，或下方没有支撑。与 V05 不同：V05 看候选自带的止损，V12 看结构支撑；止损设得紧但下方悬空时 V12 仍否决。
- **来源**：EP301§R12（"大涨百分之十几……远离了支撑，中间悬空状态的……不能买"，SNOW +16% 案例）
```rule
kind: veto
scope: candidate
when:
  - far_from_support: {pct: 0.10}   # v12.max_distance_pct · 已裁决
```

### V13 突破前阻力、但开盘直接顶入下一强阻力下沿

- **条件**（每个候选）：最近 2 日突破了一个阻力区间，且 entry 距上方下一个阻力区间下沿不足 2%。
- **来源**：EP301§R13
- **案例**：价格 75，阻力 80–90 与 100–110；跳空开盘 99 → VETO
```rule
kind: veto
scope: candidate
when:
  - zone_broken_within: {kind: resistance, days: 2}
  - tight_to_resistance: {pct: 0.02}   # v13.min_room_pct · 默认值
```

### V14 盈亏比不足

- **条件**（每个候选）：`rr = (target − entry) / (entry − stop)`；rr < 1.0 → VETO；1.0 ≤ rr < 1.5 → WARN；没有 target → 由人设定。
- **来源**：EP301§R14、EP302（"你20块钱的止损上方至少要涨20块钱的预期，你才能够实现1:1"）
- **案例**（EP301）：entry 125、stop 100、target 142 → rr 0.68 → VETO
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

### V15 RSI-6 > 90

- **条件**：T 日 RSI-6 > 90。
- **来源**：EP301§R15
```rule
kind: veto
when:
  - rsi_above: {period: 6, x: 90}    # v15.rsi_fast_max · source
```

### V16 RSI 超买区顶背离

- **条件**：T 日 RSI-6 > 80 且 P-DIVERGENCE 顶背离成立。
- **来源**：EP301§R16
```rule
kind: veto
trust: review
when:
  - rsi_above: {period: 6, x: 80}        # v16.rsi_overbought · source
  - divergence: {kind: top, max_gap: 30, k: 2}
```

## 3.3 执行时刻（V17–V18）

盘后无法判断，作为次日提醒，见 A-V17、A-V18。

# 4. 买点（S）

通用约定：

- **entry** 为 T 日收盘价（盘后分析，次日计划参考价）。
- **target** 为 entry 上方最近阻力区间的下沿；没有则为空（V14 请人设定）。
- **stop** 按各买点定义，统一预留 1% 缓冲以防扫损（EP150）。
- **grade**：A = 形态一级 + 量能确认且无近似算法；B = 用到近似算法或形态非一级；C = 形态中性。
- 所有候选都经过 V05、V12、V13、V14。

### S01 放量突破强阻力 → 缩量回踩突破区间

- **条件**：
  1. 最近 20 日内，某阻力区间被放量突破
  2. 之后回踩进入该区间，回踩期间不放量，收盘未跌破区间下沿
  3. 触发（二选一）：T 日在区间内出现止跌形态；或 T 日放量阳线
- **止损**：区间下沿 × 0.99
- **来源**：EP302§B1（案例：META 638–680 区间）
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

### S02 下行趋势线放量突破 → 缩量回踩不破

- **条件**：
  1. 下行趋势线在最近 20 日内被放量突破
  2. 此后每日收盘均在线上
  3. T 日缩量，且收盘距线 ≤ 3%
- **止损**：`line(T)` × 0.99。激进模式（突破当日直接买）不实现。
- **来源**：EP302§B2
```rule
kind: setup
when:
  - retest_line: {kind: trendline, side: above, lookback: 20, slope: down, near_pct: 0.03}
  - volume_state: {state: shrink}
entry: {session_close: {}}
stop: {buffered_line: {kind: trendline, side: above, lookback: 20, slope: down, pct: 0.01}}
target: {nearest_resistance: {}}
```

### S03 上升旗形放量突破 A 线

- **条件**（EP150）：
  1. 旗杆（人画 `flag_pole`）期间均量高于杆底前 20 日均量
  2. 旗面（杆顶之后，人画 A 线 `flag_upper`、B 线 `flag_lower`）均量低于旗杆，且无持续放量大阴线
  3. 旗面最低收盘 ≥ 旗杆 Fib 61.8%
  4. T 日放量阳线收盘 > A 线
- **止损**：`B(T)` × 0.99。**目标**：T1 = 旗杆顶；T2 = entry + 旗杆高度（写入 evidence）。B 线左侧买点暂不实现。
- **来源**：EP302§B3、EP150
```rule
kind: setup
when:
  - flag_break: {pre: 20}     # s03.pre_pole_days · source「其前 20 日」
  - green_expand: {}
entry: {session_close: {}}
stop: {buffered_flag_lower: {pct: 0.01}}
target: {flag_pole_high: {}}
```

### S04 W 底 / 头肩底颈线突破 → 回踩不破

- **条件**：
  1. 颈线在最近 20 日内被放量突破
  2. 此后收盘未跌回颈线下方（忽略影线）
  3. T 日 low 触及颈线 ± 2%，开盘与收盘都在颈线之上
- **止损**：`neckline(T)` × 0.99。原文「分时主动买盘强抵抗」只作提醒。
- **来源**：EP302§B4
```rule
kind: setup
when:
  - retest_line: {kind: neckline, side: above, lookback: 20, touch_pct: 0.02}
entry: {session_close: {}}
stop: {buffered_line: {kind: neckline, side: above, lookback: 20, pct: 0.01}}
target: {nearest_resistance: {}}
```

### S05 强势连阳后首次阴线回踩 MA5 / MA10

- **条件**：
  1. T 日之前连续收涨 ≥ 5 日
  2. T 日为连涨后的**第一根**收跌 K 线（连涨后多日阴跌慢慢靠近均线不算）
  3. `low[T] ≤ MA5[T] ≤ close[T]`（或 MA10）
- **止损**：`low[T]` × 0.99。此类止损常偏大，交给 V05 / V14 过滤。
- **来源**：EP302§B5（"第一次下跌收跌，它就回踩到了最近的一条MA……连续几个阴跌跌下来，慢慢摸到均线，无效"）
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

### S06 极度缩量后放量看涨吞没

- **条件**：
  1. P-TREND 为 down 或 sideways
  2. T-1 极度缩量：两个量比都 < 0.6
  3. T 日一级看涨吞没，放量，上影线极短
- **止损**：`low[T]` × 0.99
- **来源**：EP302§B6
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

### S07 缩量新低后放量锤子线

- **条件**：
  1. P-TREND = down
  2. T-1 收盘新低且缩量
  3. T 日锤子线且放量；T 日收盘仍为新低 → grade C（等 1 个交易日，此时 V01 也会否决）
- **止损**：`low[T]` × 0.99
- **来源**：EP302§B7、EP124
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

### S08 板块突破日龙头放量大阳

- **条件**：所属板块指数突破当日，该股放量实体大阳突破最近压力，上影线越小越好；上方压力越远越好。板块与龙头由人回答。
- **止损**：原文未给，**不设**。V05 因此否决（止损无法确定）；要买，由人在计划中写明止损。
- **来源**：EP302§B8（"板块突破的当天……成分股出现了放量的实体大阳线，突破了最近的压力"）
```rule
kind: setup
ask: T 日所属板块指数是否突破？该股是否为放量实体大阳突破最近压力的龙头？（回答 s08.sector_breakout_leader）
when:
  - fact: {key: s08.sector_breakout_leader, is: true, ttl: 1}   # 只针对 T · 默认值
  - green_expand: {}
entry: {session_close: {}}
target: {nearest_resistance: {}}
```

### S09 上行回撤不破 61.8% + RSI 超卖 + 底背离 + 止跌形态

- **条件**（全部）：
  1. 大结构上行，回撤收盘始终在 Fib 61.8% 之上
  2. 最近 30 日内 RSI-6 < 20（原文"超卖是RSI大于80"为口误，已确认）
  3. P-DIVERGENCE 底背离
  4. T 日出现止跌形态
- **止损**：Fib 61.8% × 0.99。**目标**：回撤起点的摆动高点。
- **来源**：EP302§B9
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

# 5. 提醒（A）

只提醒，不影响结论。

### A-V17 盘前盘后异动不参与

- **来源**：EP301§R17、EP272
```rule
kind: advice
say: 非财报的盘前盘后大涨大跌不参与，以常规时段开盘为准
```

### A-V18 开盘半小时不下单

- **来源**：EP301§R18
```rule
kind: advice
say: 美东 9:30–10:00 不下单
```

### A-EARN 财报临近

- **来源**：EP301§R07、EP189（到期日前有财报时，Band68 含财报波动）
```rule
kind: advice
say: 财报临近，Band68 含财报波动
when:
  - days_to_earnings: {max: 5}     # a_earn.highlight_days · 默认值
```

### A-BAND68 Band68 区间

- **来源**：EP189（算法见 P-BAND68）
```rule
kind: advice
when:
  - band68_range: {max_strike_gap_pct: 0.02}   # band68.max_strike_gap_pct · source
```

### A-BAND68-SUP Band68 下沿触及支撑

- **来源**：EP189
```rule
kind: advice
say: Band68 下沿可能跌破最近支撑
when:
  - band68_edge: {against: support, max_strike_gap_pct: 0.02}
```

### A-BAND68-RES Band68 上沿超出阻力

- **来源**：EP189
```rule
kind: advice
say: Band68 上沿可能超出最近阻力
when:
  - band68_edge: {against: resistance, max_strike_gap_pct: 0.02}
```

### A-BAND68-FIB Band68 下沿低于 Fib 61.8%

- **来源**：EP189（期权在定价破位）
```rule
kind: advice
say: Band68 下沿低于 Fib 61.8%，期权在定价破位
when:
  - band68_edge: {against: fib, level: 0.618, max_strike_gap_pct: 0.02}
```

### A-TOP 见顶形态

- **来源**：EP124、EP302§B1 案例
```rule
kind: advice
say: 见顶形态（流星线），当天不宜抄底 / 追高
when:
  - shooting_star: {short_shadow_ratio: 0.1}
```

# 6. 左侧未满即反弹（EP292）

# 2. 档案回答

| key | 值 |
| --- | --- |
| `left.filled` | 已买几成（0–10） |
| `left.valuation` | `undervalued` / `fair` / `overvalued` |
| `left.small_break` | 小结构已走、大结构未破（当日） |
| `left.fy_rolled` | 已进入下一财年炒作、最初买点等不到了 |

### L01 写下已买仓位

- **条件**：没有 `left.filled` → 提问。
- **来源**：EP292（仓位安排是预案的前提）
```rule
kind: veto
ask: 该股已买几成？请回答 left.filled（0–10，满仓=10）
when:
  - fact: {key: left.filled}
```

### L02 写下估值分档

- **条件**：没有 `left.valuation` → 提问。
- **来源**：EP292（买点看前瞻估值下限/中位/低估）
```rule
kind: veto
ask: 当前估值？请回答 left.valuation（undervalued / fair / overvalued）
when:
  - fact: {key: left.valuation}
```

# 3. 反弹后

### A-LEFT-LIGHT 小结构走了且未过半

- **条件**：已买不足 5 成；估值仍合理或低估；小结构向上、大结构未破。可少量加到 3–5 成，下方档位仍留。
- **来源**：EP292（只买了两成、突破小趋势，可动态加到 3–5 成）
```rule
kind: advice
say: 小结构向上、仓位未过半，可少量加到 3–5 成；下方档位仍留，不要一次打完
when:
  - fact: {key: left.filled, max: 4}
  - fact: {key: left.valuation, is: fair}
  - fact: {key: left.small_break, is: true, ttl: 1}
```

```rule
kind: advice
say: 小结构向上、仓位未过半，可少量加到 3–5 成；下方档位仍留，不要一次打完
when:
  - fact: {key: left.filled, max: 4}
  - fact: {key: left.valuation, is: undervalued}
  - fact: {key: left.small_break, is: true, ttl: 1}
```

### A-LEFT-HEAVY 已过半则小突破不加

- **条件**：已买 ≥ 5 成，且小结构走了。剩下的留在更低位置。
- **来源**：EP292（已经买到 50% 不要激进加仓）
```rule
kind: advice
say: 已过半，小突破不加长线；坐轿，预留下方档位
when:
  - fact: {key: left.filled, min: 5}
  - fact: {key: left.small_break, is: true, ttl: 1}
```

### A-LEFT-OVER 高估不加长线

- **条件**：估值已是 `overvalued`。长线仓位绝对不加；技术面右侧波段须小于已持仓，止盈止损走 `technical.md`；不熟则放弃。
- **来源**：EP292（回到高估绝不加长线仓位）
```rule
kind: advice
say: 高估，不加长线。右侧波段仓位必须小于已持仓，止盈止损按 technical 买点规则；不熟则放弃
when:
  - fact: {key: left.valuation, is: overvalued}
```

### A-LEFT-FY 财年推演后上调买点

- **条件**：人确认已进入下一财年炒作。最初低位等不到，买点上调，仍要估值合理 + 支撑。
- **来源**：EP292（苹果/美光：同样价格去年高估、今年可能合理）
```rule
kind: advice
say: 已进入下一财年炒作，上调买点；仍须估值合理加技术面支撑
when:
  - fact: {key: left.fy_rolled, is: true}
```

### A-LEFT-PUT 更低档可 Sell Put

- **条件**：尚未买满。前提是资金能承接正股，不是单纯薅权利金。
- **来源**：EP292
```rule
kind: advice
say: 更低档位可 Sell Put，前提是行权时资金能接股票；不要单纯薅权利金
when:
  - fact: {key: left.filled, max: 9}
```

### A-LEFT-CALL Covered Call 行权价

- **条件**：有当日期权链。行权价放在 Band68 之外、强阻力上沿；最近月度到期。击穿不是期权止损，临到期前 1–2 天再平。
- **来源**：EP292、EP189
```rule
kind: advice
say: Covered Call 行权价放在 Band68 之外、强阻力上沿；月度到期。击穿临到期再平，不存在期权止损
when:
  - band68_range: {max_strike_gap_pct: 0.02}
```

### A-LEFT-CASH 预留现金

- **来源**：EP292（不要买股息股作过渡）
```rule
kind: advice
say: 预留现金放券商利息或货币基金 / 短期国债；不要买股息股或股息 ETF 作过渡
```
