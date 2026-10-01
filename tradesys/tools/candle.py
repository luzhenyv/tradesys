"""P-CANDLE · EP124：锤子线、一级看涨吞没、流星线（几何；量能在 rule 里组合）。"""

from tradesys.models import Bar, Check, Snapshot
from tradesys.tools.price import extreme


def _body(b: Bar) -> float:
    return abs(b.close - b.open)


def _span(b: Bar) -> float:
    return b.high - b.low or 1e-9


def hammer(snap: Snapshot, n: int = 20, short_shadow_ratio: float = 0.1) -> Check:
    """下影 ≥ 2×实体，上影极短。当日新低则 grade=C。"""
    if not snap.bars.items:
        return Check(None, ("无K线",), missing=True, review=True)
    b = snap.bars.last
    body, lower = _body(b), min(b.open, b.close) - b.low
    upper = b.high - max(b.open, b.close)
    if lower < 2 * body or upper > short_shadow_ratio * _span(b):
        return Check(False, ("非锤子线",), review=True)
    is_nl, _ = extreme(snap.bars.closes, n, True)
    return Check(True, ("锤子线",), review=True, grade="C" if is_nl else None)


def bullish_engulfing(snap: Snapshot, tier: int = 1, short_shadow_ratio: float = 0.1) -> Check:
    """一级：T 开盘 < T-1 low 且收盘 > T-1 high；上影不超过 short_shadow_ratio。"""
    if len(snap.bars.items) < 2:
        return Check(None, ("历史不足 2 根",), missing=True, review=True)
    a, b = snap.bars.items[-2], snap.bars.last
    if a.close >= a.open or b.close <= b.open:
        return Check(False, ("非阳包阴",), review=True)
    full = b.open < a.low and b.close > a.high
    if tier >= 1 and not full:
        return Check(False, ("非一级吞没",), review=True)
    if b.high - b.close > short_shadow_ratio * _span(b):
        return Check(False, ("上影过长",), review=True)
    return Check(True, ("一级看涨吞没",), review=True)


def stop_candle(snap: Snapshot) -> Check:
    """止跌形态：锤子线或一级看涨吞没。"""
    h, e = hammer(snap), bullish_engulfing(snap)
    if h.hit:
        return h
    if e.hit:
        return e
    return Check(False, ("无止跌形态",), review=True)


def green_expand(snap: Snapshot) -> Check:
    """放量阳线：收盘 > 开盘且 P-VOL=expand。"""
    from tradesys.tools.volume import volume_state

    if not snap.bars.items:
        return Check(None, ("无K线",), missing=True)
    b, vol = snap.bars.last, volume_state(snap, "expand")
    hit = b.close > b.open and vol.hit is True
    return Check(hit, (*vol.evidence, f"open={b.open}", f"close={b.close}"))


def shooting_star(snap: Snapshot, short_shadow_ratio: float = 0.1) -> Check:
    """上影 ≥ 2×实体，下影极短。"""
    if not snap.bars.items:
        return Check(None, ("无K线",), missing=True, review=True)
    b = snap.bars.last
    body, upper = _body(b), b.high - max(b.open, b.close)
    lower = min(b.open, b.close) - b.low
    hit = upper >= 2 * body and lower <= short_shadow_ratio * _span(b)
    return Check(hit, ("流星线" if hit else "非流星线",), review=True)
