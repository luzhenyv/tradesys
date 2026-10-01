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


def fib_broken(snap: Snapshot, level: float = 0.618, days: int = 2, window: int = 60) -> Check:
    """收盘刚跌破 Fib level 且未收回。"""
    imp = impulse(snap.bars.closes, window)
    if imp is None:
        return Check(None, ("历史不足",), missing=True, review=True)
    low, high = imp
    if high <= low:
        return Check(False, ("无上涨结构",), review=True)
    line = retrace(low, high, level)
    c = snap.bars.closes
    hit = False
    start = max(1, len(c) - days)
    for i in range(start, len(c)):
        if c[i] < line <= c[i - 1]:
            hit = True
    if c[-1] >= line:
        hit = False
    return Check(hit, (f"fib{level}={line:.2f}", f"close={c[-1]}"), review=True)
