"""P-TREND · EP302：MA20 近似短期趋势，结果需人工复核。"""

from tradesys.models import Check, Snapshot

WINDOW, LOOKBACK = 20, 5


def classify(closes: tuple[float, ...]) -> str | None:
    """down / up / sideways；历史不足 WINDOW+LOOKBACK 根时为 None。"""
    n = WINDOW + LOOKBACK
    if len(closes) < n:
        return None
    ma_t = sum(closes[-WINDOW:]) / WINDOW
    ma_prev = sum(closes[-n:-LOOKBACK]) / WINDOW
    close = closes[-1]
    if close < ma_t and ma_t < ma_prev:
        return "down"
    if close > ma_t and ma_t > ma_prev:
        return "up"
    return "sideways"


def trend(snap: Snapshot, direction: str) -> Check:
    """P-TREND：T 日趋势是否为 direction（down / up / sideways）。"""
    actual = classify(snap.bars.closes)
    if actual is None:
        return Check(None, ("历史不足以计算 MA20",), missing=True)
    ma_t = sum(snap.bars.closes[-WINDOW:]) / WINDOW
    return Check(
        actual == direction,
        (f"trend={actual}", f"close={snap.bars.last.close}", f"MA20={ma_t:.2f}"),
        review=True,
    )
