"""P-NEWLOW / P-NEWHIGH · EP301§R01：只比较收盘价，不比较历史最低价。"""

from tradesys.models import Check, Snapshot


def extreme(closes: tuple[float, ...], n: int, low: bool) -> tuple[bool, int]:
    """返回 (是否为 n 日收盘新低/新高, 实际 K 值：前面连续 K 天收盘都比今天更高/更低)。"""
    today, prior = closes[-1], closes[:-1]
    k = 0
    for past in reversed(prior):
        if (past > today) if low else (past < today):
            k += 1
        else:
            break
    return len(prior) >= n and k >= n, k


def new_low(snap: Snapshot, n: int) -> Check:
    """P-NEWLOW：T 日收盘价低于前 n 日所有收盘价。"""
    hit, k = extreme(snap.bars.closes, n, low=True)
    return Check(hit, (f"close={snap.bars.last.close}", f"收盘价为 {k} 日新低", f"n={n}"))


def new_high(snap: Snapshot, n: int) -> Check:
    """P-NEWHIGH：T 日收盘价高于前 n 日所有收盘价。"""
    hit, k = extreme(snap.bars.closes, n, low=False)
    return Check(hit, (f"close={snap.bars.last.close}", f"收盘价为 {k} 日新高", f"n={n}"))


def close_up(snap: Snapshot, n: int) -> Check:
    """T 日收盘价是否高于 T−n 日收盘价。"""
    c = snap.bars.closes
    if len(c) < n + 1:
        return Check(None, (f"历史不足 {n + 1} 根",), missing=True)
    return Check(c[-1] > c[-1 - n], (f"close={c[-1]}", f"close[T-{n}]={c[-1 - n]}"))


def drop_pct(snap: Snapshot, min: float) -> Check:
    """T 日收盘跌幅是否达到 min（close[T]/close[T-1]−1 ≤ −min）。"""
    c = snap.bars.closes
    if len(c) < 2:
        return Check(None, ("历史不足 2 根",), missing=True)
    ret = c[-1] / c[-2] - 1
    return Check(ret <= -min, (f"close={c[-1]}", f"prev={c[-2]}", f"涨跌={ret:.1%}"))
