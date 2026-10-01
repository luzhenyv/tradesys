"""P-VOL · EP010、EP301§R04：同时与前一日、前 5 日均量（不含当日）比较。"""

from tradesys.calendar_utils import at_offset, is_opex_friday
from tradesys.models import Check, Snapshot


def volume_ratios(vols: tuple[float, ...]) -> tuple[float | None, float | None]:
    """T 日的 (vs_prev, vs_ma5)；历史不足时为 None。"""
    v = vols[-1]
    prev = v / vols[-2] if len(vols) >= 2 and vols[-2] else None
    base = sum(vols[-6:-1]) / 5 if len(vols) >= 6 else 0.0
    return prev, (v / base if base else None)


def state_at(vols: tuple[float, ...], shrink: float = 1.0, expand: float = 1.0) -> str:
    """截至该序列最后一根的量能状态。"""
    return classify(*volume_ratios(vols), shrink, expand)


def classify(prev: float | None, ma5: float | None, shrink: float, expand: float) -> str:
    """两个量比都低于 shrink → shrink；都高于 expand → expand；其余 neutral。"""
    if prev is None or ma5 is None:
        return "neutral"
    if prev < shrink and ma5 < shrink:
        return "shrink"
    if prev > expand and ma5 > expand:
        return "expand"
    return "neutral"


def volume_state(
    snap: Snapshot,
    state: str,
    shrink_ratio: float = 1.0,
    expand_ratio: float = 1.0,
    offset: int = 0,
) -> Check:
    """P-VOL：T 日量能状态是否为 state（shrink / expand / neutral）。"""
    snap = at_offset(snap, offset)
    if len(snap.bars.items) < 2:
        return Check(None, ("历史不足",), missing=True)
    prev, ma5 = volume_ratios(snap.bars.volumes)
    actual = classify(prev, ma5, shrink_ratio, expand_ratio)
    evidence = [f"vs_prev={prev and round(prev, 2)}", f"vs_ma5={ma5 and round(ma5, 2)}", actual]
    if actual == "expand" and is_opex_friday(snap.session_date):
        evidence.append("OpEx 放量，有效性打折")
    return Check(actual == state, tuple(evidence))


def volume_dry(snap: Snapshot, ratio: float, offset: int = 0) -> Check:
    """vs_prev 与 vs_ma5 都低于 ratio（极度缩量）。"""
    snap = at_offset(snap, offset)
    prev, ma5 = volume_ratios(snap.bars.volumes)
    if prev is None or ma5 is None:
        return Check(None, ("历史不足",), missing=True)
    return Check(
        prev < ratio and ma5 < ratio,
        (f"vs_prev={prev:.2f}", f"vs_ma5={ma5:.2f}", f"ratio={ratio}"),
    )


def volume_declining(snap: Snapshot, n: int) -> Check:
    """最近 n 日成交量是否严格逐日下降。"""
    v = snap.bars.volumes
    if len(v) < n:
        return Check(None, (f"历史不足 {n} 根",), missing=True)
    window = v[-n:]
    hit = all(window[i] < window[i - 1] for i in range(1, n))
    return Check(hit, (f"vol={tuple(round(x) for x in window)}",))


def volume_ma5_turning_down(snap: Snapshot) -> Check:
    """含当日的量能 MA5 是否拐头向下（MA5vol[T] < MA5vol[T-1]）。"""
    v = snap.bars.volumes
    if len(v) < 6:
        return Check(None, ("历史不足 6 根",), missing=True)
    ma_t, ma_prev = sum(v[-5:]) / 5, sum(v[-6:-1]) / 5
    return Check(ma_t < ma_prev, (f"MA5vol={ma_t:.0f}", f"MA5vol[T-1]={ma_prev:.0f}"))
