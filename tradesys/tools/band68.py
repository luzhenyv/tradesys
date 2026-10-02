"""P-BAND68 · EP189：ATM straddle 推算 68% 波动区间。"""

from tradesys.models import Chain, Check, Snapshot
from tradesys.tools.fib import impulse, retrace
from tradesys.tools.structure import current_role


def band68(close: float, chain: Chain, max_strike_gap_pct: float) -> tuple[float, float] | None:
    """返回 (low, high)。close 必须是常规时段收盘价；只用 Ask。无法计算时返回 None。"""
    strikes = {q.strike for q in chain.quotes}
    if not strikes:
        return None
    k = min(strikes, key=lambda s: abs(s - close))
    if abs(k - close) / close > max_strike_gap_pct:
        return None

    asks = {q.kind: q.ask for q in chain.quotes if q.strike == k}
    if "call" not in asks or "put" not in asks:
        return None

    # K > C → X' = X − (K − C)；K < C → X' = X + (C − K)，两者合并为同一式
    x_adj = asks["call"] + asks["put"] - (k - close)
    return close - x_adj, close + x_adj


def band68_range(snap: Snapshot, max_strike_gap_pct: float = 0.02) -> Check:
    """P-BAND68：给出到期日前 68% 概率的价格区间（提醒用，hit 恒为 True）。"""
    if snap.chain is None:
        return Check(None, ("无 as_of 时点的期权链",), missing=True)
    band = band68(snap.bars.last.close, snap.chain, max_strike_gap_pct)
    if band is None:
        return Check(None, ("最近行权价偏离收盘价过大",), missing=True)
    low, high = band
    return Check(True, (f"Band68=[{low:.1f}, {high:.1f}]", f"expiry={snap.chain.expiry}"))


def band68_edge(
    snap: Snapshot, against: str, max_strike_gap_pct: float, level: float = 0.618
) -> Check:
    """P-BAND68 · EP189：下沿低于最近支撑 / Fib（support|fib），或上沿超出最近阻力。"""
    base = band68_range(snap, max_strike_gap_pct)
    if not base.hit:
        return base
    low, high = band68(snap.bars.last.close, snap.chain, max_strike_gap_pct)
    if against == "fib":
        imp = impulse(snap.bars.closes)
        if imp is None or imp[1] <= imp[0]:
            return Check(False, (*base.evidence, "无上涨结构"))
        fib = retrace(*imp, level)
        return Check(low < fib, (*base.evidence, f"Fib {level}={fib:.1f}"))
    zones = [z for z in snap.zones if current_role(z, snap.bars) == against]
    if not zones:
        return Check(False, (*base.evidence, f"无当前 {against}"))
    if against == "support":
        z = max(zones, key=lambda z: z.high)
        return Check(low < z.high, (*base.evidence, f"{z.id} {z.low}-{z.high}"))
    z = min(zones, key=lambda z: z.low)
    return Check(high > z.low, (*base.evidence, f"{z.id} {z.low}-{z.high}"))
