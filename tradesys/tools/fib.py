"""P-FIB · EP150、EP301§R03：近 window 日最低收盘 → 其后最高收盘。"""

from tradesys.models import Check, Snapshot


def impulse(closes: tuple[float, ...], window: int = 60) -> tuple[float, float] | None:
    """(swing low, swing high)。高点取低点之后的最高收盘。"""
    seq = closes[-window:] if len(closes) > window else closes
    if len(seq) < 2:
        return None
    i = min(range(len(seq)), key=lambda j: seq[j])
    return seq[i], max(seq[i:])


def retrace(low: float, high: float, level: float) -> float:
    return high - (high - low) * level


def fib_holds(snap: Snapshot, level: float = 0.618, window: int = 60) -> Check:
    """高点之后收盘从未跌破 Fib level。"""
    imp = impulse(snap.bars.closes, window)
    if imp is None:
        return Check(None, ("历史不足",), missing=True, review=True)
    low, high = imp
    if high <= low:
        return Check(False, ("无上涨结构",), review=True)
    line = retrace(low, high, level)
    seq = snap.bars.closes[-window:] if len(snap.bars.closes) > window else snap.bars.closes
    i_low = min(range(len(seq)), key=lambda j: seq[j])
    i_high = i_low + max(range(len(seq) - i_low), key=lambda j: seq[i_low + j])
    hit = all(c >= line for c in seq[i_high:])
    return Check(hit, (f"fib{level}={line:.2f}", f"high={high}"), review=True)


def fib_stop(snap: Snapshot, level: float = 0.618, pct: float = 0.01, window: int = 60) -> Check:
    """Fib level × (1−pct)。"""
    imp = impulse(snap.bars.closes, window)
    if imp is None:
        return Check(None, ("历史不足",), missing=True, review=True)
    v = retrace(*imp, level) * (1 - pct)
    return Check(True, (f"stop={v:.2f}",), review=True, value=v)


def impulse_high(snap: Snapshot, window: int = 60) -> Check:
    """P-FIB 上涨段的最高收盘。"""
    imp = impulse(snap.bars.closes, window)
    if imp is None:
        return Check(None, ("历史不足",), missing=True, review=True)
    return Check(True, (f"swing_high={imp[1]}",), review=True, value=imp[1])


def fib_broken(snap: Snapshot, level: float = 0.618, days: int = 2, window: int = 60) -> Check:
    """收盘在最近 days 根内跌破 Fib level 且未收回。上涨段取破位窗口之前，破位日新低不改写结构。"""
    c = snap.bars.closes
    imp = impulse(c[:-days], window) if len(c) > days else None
    if imp is None:
        return Check(None, ("历史不足",), missing=True, review=True)
    low, high = imp
    if high <= low:
        return Check(False, ("无上涨结构",), review=True)
    line = retrace(low, high, level)
    broke = any(c[i] < line <= c[i - 1] for i in range(max(1, len(c) - days), len(c)))
    hit = broke and c[-1] < line
    return Check(hit, (f"fib{level}={line:.2f}", f"close={c[-1]}"), review=True)
