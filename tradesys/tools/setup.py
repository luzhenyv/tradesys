"""Setup 条件小工具：连涨、第一根阴线、回踩均线。"""

from tradesys.models import Check, Snapshot


def up_streak(snap: Snapshot, n: int) -> Check:
    """T 日之前连续 n 日收涨。"""
    c = snap.bars.closes
    if len(c) < n + 2:
        return Check(None, (f"历史不足 {n + 2} 根",), missing=True)
    seq = c[-(n + 2) : -1]
    hit = all(seq[i] > seq[i - 1] for i in range(1, len(seq)))
    return Check(hit, (f"连涨 {n} 日" if hit else f"连涨不足 {n} 日",))


def first_down(snap: Snapshot) -> Check:
    """T 日收跌（连涨后的第一根由 up_streak 保证）。"""
    c = snap.bars.closes
    if len(c) < 2:
        return Check(None, ("历史不足 2 根",), missing=True)
    return Check(c[-1] < c[-2], (f"close={c[-1]}", f"prev={c[-2]}"))


def pullback_to_ma(snap: Snapshot, n: int) -> Check:
    """low[T] ≤ MA_n[T] ≤ close[T]。"""
    c = snap.bars.closes
    if len(c) < n:
        return Check(None, (f"历史不足 {n} 根",), missing=True)
    ma = sum(c[-n:]) / n
    low, close = snap.bars.last.low, c[-1]
    return Check(low <= ma <= close, (f"MA{n}={ma:.2f}", f"low={low}", f"close={close}"))
