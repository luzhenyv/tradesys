"""P-NEWLOW / P-NEWHIGH · EP301§R01：只比较收盘价，不比较历史最低价。"""


def new_low(closes: tuple[float, ...], n: int) -> tuple[bool, int]:
    """返回 (是否为 n 日收盘新低, 实际 K 值：前面连续 K 天的收盘价都高于今天)。"""
    return _extreme(closes, n, lambda past, today: past > today)


def new_high(closes: tuple[float, ...], n: int) -> tuple[bool, int]:
    return _extreme(closes, n, lambda past, today: past < today)


def _extreme(closes, n, beyond) -> tuple[bool, int]:
    today, prior = closes[-1], closes[:-1]
    k = 0
    for past in reversed(prior):
        if not beyond(past, today):
            break
        k += 1
    return len(prior) >= n and k >= n, k
