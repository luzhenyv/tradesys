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
