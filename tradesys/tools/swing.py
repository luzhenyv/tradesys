"""P-SWING / P-DIVERGENCE · EP302：k 分形摆动点；顶/底背离用最近两个摆动。"""

from tradesys.models import Check, Snapshot
from tradesys.tools.rsi import rsi_series


def fractals(values: tuple[float, ...], k: int, high: bool) -> tuple[int, ...]:
    """局部极值下标：values[i] 高于/低于左右各 k 根。"""
    out = []
    for i in range(k, len(values) - k):
        left = values[i - k : i]
        right = values[i + 1 : i + 1 + k]
        if high and all(values[i] > x for x in (*left, *right)):
            out.append(i)
        elif not high and all(values[i] < x for x in (*left, *right)):
            out.append(i)
    return tuple(out)


def divergence(snap: Snapshot, kind: str, max_gap: int = 30, k: int = 2) -> Check:
    """P-DIVERGENCE：顶背离 kind=top，底背离 kind=bottom。"""
    top = kind == "top"
    idx = fractals(snap.bars.highs if top else snap.bars.lows, k, high=top)
    if len(idx) < 2:
        return Check(False, ("摆动点不足",), review=True)
    a, b = idx[-2], idx[-1]
    if b - a > max_gap:
        return Check(False, (f"间隔 {b - a} > {max_gap}",), review=True)
    rsi6 = rsi_series(snap.bars.closes, 6)
    if rsi6[a] is None or rsi6[b] is None:
        return Check(None, ("RSI 历史不足",), review=True, missing=True)
    px = snap.bars.highs if top else snap.bars.lows
    if top:
        hit = px[b] >= px[a] and rsi6[b] < rsi6[a]
    else:
        rsi24 = rsi_series(snap.bars.closes, 24)
        if rsi24[a] is None or rsi24[b] is None:
            return Check(None, ("RSI-24 历史不足",), review=True, missing=True)
        hit = px[b] <= px[a] and rsi6[b] > rsi6[a] and rsi24[b] > rsi24[a]
    return Check(hit, (f"{kind} {a}->{b}", f"RSI6 {rsi6[a]:.1f}->{rsi6[b]:.1f}"), review=True)
