"""P-RSI · EP301§R15：Wilder RSI；V1 用 6 与 24，不用 12。"""

from tradesys.models import Check, Snapshot


def rsi_series(closes: tuple[float, ...], period: int) -> tuple[float | None, ...]:
    """与 closes 对齐的 Wilder RSI；前 period 根为 None。"""
    n = len(closes)
    out: list[float | None] = [None] * n
    if period < 1 or n < period + 1:
        return tuple(out)
    gains, losses = [], []
    for a, b in zip(closes[:-1], closes[1:], strict=True):
        delta = b - a
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def value() -> float:
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    out[period] = value()
    later = zip(gains[period:], losses[period:], strict=True)
    for i, (g, loss) in enumerate(later, start=period + 1):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = value()
    return tuple(out)


def rsi(closes: tuple[float, ...], period: int) -> float | None:
    """最后一根的 Wilder RSI；历史不足 period+1 根时为 None。"""
    return rsi_series(closes, period)[-1] if closes else None


def rsi_above(snap: Snapshot, period: int, x: float) -> Check:
    """P-RSI：T 日 RSI 是否高于 x。"""
    value = rsi(snap.bars.closes, period)
    if value is None:
        return Check(None, (f"历史不足 {period + 1} 根",), missing=True)
    return Check(value > x, (f"RSI-{period}={value:.1f}", f"x={x}"))


def rsi_below_within(snap: Snapshot, period: int, x: float, days: int) -> Check:
    """最近 days 根内 RSI 是否曾低于 x。"""
    series = rsi_series(snap.bars.closes, period)[-days:]
    vals = [v for v in series if v is not None]
    if not vals:
        return Check(None, (f"历史不足 {period + 1} 根",), missing=True)
    hit = any(v < x for v in vals)
    return Check(hit, (f"min RSI-{period}={min(vals):.1f}", f"x={x}"))
