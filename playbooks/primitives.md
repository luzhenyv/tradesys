# 原语

> 规则库共同使用的判定积木。每个原语只有一个实现（工具 docstring 首行写原语 ID）；规则不得自行重写。本文件不执行。
> **Impl**：`full` 完整实现；`simple` 近似算法（工具返回 `review=True`）；`YAML` 结构由人画。

### P-TREND 趋势方向

- **Impl**：simple（MA20 近似，默认实现，待校准）
- `down`：`close[T] < MA20[T]` 且 `MA20[T] < MA20[T-5]`；`up`：镜像；其他 `sideways`。
- **Source**：EP302（"低点不断在创新低……收盘价不断的在创新低，这是很明显的下跌趋势"）

### P-SWING 摆动点

- **Impl**：simple（k 分形，默认 k=2）
- `high[t]` 高于左右各 k 根 K 线的 high 即为 swing high；low 同理。用于背离。

### P-NEWLOW / P-NEWHIGH 近期新低 / 新高

- **Impl**：full
- 新低：`close[T] < min(close[T-N .. T-1])`；新高镜像。N 默认 20。
- evidence 给出「收盘价为 K 日新低 / 新高」的实际 K 值。
- **Source**：EP301§R01（"和近期的收盘价对比，不是要和历史上最低价去对比"）

### P-VOL 量能状态

- **Impl**：full
- `vs_prev = vol[T] / vol[T-1]`；`vs_ma5 = vol[T] / mean(vol[T-5 .. T-1])`（不含当日）。
- 两个量比都 < shrink_ratio → `shrink`；都 > expand_ratio → `expand`；其他 `neutral`。默认比值 1.0。
- 月度 OpEx 日放量：evidence 标注「OpEx 放量，有效性打折」，不改变状态（EP249）。
- **Source**：EP010、EP301§R04（"和前5天比……和成交量的5日均线比"）、EP249

### P-ZONE 支撑阻力区间

- **Impl**：YAML（不自动识别）
- 支撑阻力是**区间** `[low, high]` 而非单点。人画区间时参考成交密集区、横盘平台（EP249：连续 2–5 日窄幅横盘）、前高前低。
- 单一均线 / 单一趋势线 / 单一前低点的有效性打折（EP272）。

### P-BREAK 突破 / 破位

- **Impl**：full（对 YAML 结构判定）
- 以支撑区间为例：
  - 盘中 `low < zone.low` 但收盘 ≥ `zone.low` → `false_break`（盘中刺破无效）
  - 收盘 < `zone.low` → `broken`，极性翻转为阻力
  - 已 broken 后，只有收盘 > `zone.high` 才算 `reclaimed`；反弹到区间内部仍是阻力测试
  - 阻力区间镜像；Line 用 `close[T]` 与 `line(T)` 比较
- 记录破位当日量能：放量破位有效，缩量破位有待观察（EP010）。
- **Source**：EP272、EP010、EP150
- **Test Case**（EP272）：支撑 100–120；盘中 99 收盘 100.5 → false_break；收盘 95 → broken；次日 105 → 仍 broken；之后 121 → reclaimed

### P-FIB 斐波那契回撤

- **Impl**：simple（近 60 日最低收盘 → 其后最高收盘）
- 一段上涨的 38.2 / 50 / 61.8% 回撤位。回撤守在 61.8% 之上为良性；**收盘**跌破 61.8% → 上涨结构失效。
- **Source**：EP150、EP301§R03

### P-CANDLE K 线形态

- **Impl**：simple（只实现锤子线、一级看涨吞没、流星线；其余形态请人工看图）
- 止跌排序（高 → 低）：锤子线 > 看涨吞没 > 启明星 > 倒锤子线 > 看涨孕线
- 见顶排序（高 → 低）：流星线 > 上吊线 > 看跌吞没 > 黄昏之星 > 看跌孕线

| 形态 | 要件 |
| --- | --- |
| 锤子线 | 下影线 ≥ 2 × 实体；上影线 ≤ 振幅 × short_shadow_ratio（默认 0.1）；出现在下跌中 |
| 看涨吞没 | T-1 阴线；T 阳线。一级：T 开盘 < T-1 low 且收盘 > T-1 high |
| 流星线 | 上影线 ≥ 2 × 实体；下影线极短 |
| 启明星 | 大阴线 + 星线 + 大阳线；第三根实体上沿超过第一根实体中点 |
| 倒锤子线 | 上影线 ≥ 2 × 实体；下影线极短；出现在下跌中 |
| 看涨孕线 | T-1 大阴线；T 小阳线完全位于 T-1 实体内；始终视为中性 |

- 放量要求不在形态工具里，由 rule 块组合 P-VOL。
- 形态当日收盘为近期新低 → grade C（中性，需再观察 1–2 个交易日；EP124、EP302§B7）。
- **Source**：EP124

### P-RSI / P-DIVERGENCE

- **Impl**：P-RSI full；P-DIVERGENCE simple（最近两个摆动点）
- P-RSI：Wilder RSI，周期 6 与 24，不使用 12（EP301§R15、EP302§B9）。
- 顶背离：最近两个 swing high 价格抬高（或持平），RSI-6 降低。
- 底背离：最近两个 swing low 价格降低（或持平），RSI-6 与 RSI-24 均抬高。
- 两个摆动点间隔 ≤ 30 日（默认）。

### P-BAND68 期权 68% 波动区间

- **Impl**：full
- EP189 步骤：到期日默认下一个月度交割日；`C` = T 日收盘；`K` = 最近行权价，`|K − C| / C > 2%` → 不可用；`X = call_ask(K) + put_ask(K)`（**必须用 Ask**）；`X' = X − (K − C)`；`Band68 = [C − X', C + X']`。
- 无 T 日期权链 → 不可用，不得用当日期权链替代。
- **Test Case**：TSLA C=164.9、K=165、call 6.30 + put 6.00 → **[152.7, 177.1]**；NVDA C=880、K=880、call 29.0 + put 27.1 → **[823.9, 936.1]**
