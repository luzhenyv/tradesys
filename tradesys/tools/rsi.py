"""P-RSI · EP301§R15：Wilder RSI；V1 用 6 与 24，不用 12。"""

from tradesys.models import Check, Snapshot


def rsi(closes: tuple[float, ...], period: int) -> float | None:
    """最后一根的 Wilder RSI；历史不足 period+1 根时为 None。"""
    if period < 1 or len(closes) < period + 1:
        return None
    gains, losses = [], []
    for a, b in zip(closes[:-1], closes[1:], strict=True):
        delta = b - a
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, loss in zip(gains[period:], losses[period:], strict=True):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)


def rsi_above(snap: Snapshot, period: int, x: float) -> Check:
    """P-RSI：T 日 RSI 是否高于 x。"""
    value = rsi(snap.bars.closes, period)
    if value is None:
        return Check(None, (f"历史不足 {period + 1} 根",), missing=True)
    return Check(value > x, (f"RSI-{period}={value:.1f}", f"x={x}"))
