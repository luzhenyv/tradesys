"""P-VOL · EP010、EP301§R04：同时与前一日、前 5 日均量（不含当日）比较。"""

from tradesys.calendar_utils import is_opex_friday
from tradesys.models import Check, Snapshot


def volume_ratios(vols: tuple[float, ...]) -> tuple[float | None, float | None]:
    """T 日的 (vs_prev, vs_ma5)；历史不足时为 None。"""
    v = vols[-1]
    prev = v / vols[-2] if len(vols) >= 2 and vols[-2] else None
    base = sum(vols[-6:-1]) / 5 if len(vols) >= 6 else 0.0
    return prev, (v / base if base else None)


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
    snap: Snapshot, state: str, shrink_ratio: float = 1.0, expand_ratio: float = 1.0
) -> Check:
    """P-VOL：T 日量能状态是否为 state（shrink / expand / neutral）。"""
    prev, ma5 = volume_ratios(snap.bars.volumes)
    actual = classify(prev, ma5, shrink_ratio, expand_ratio)
    evidence = [f"vs_prev={prev and round(prev, 2)}", f"vs_ma5={ma5 and round(ma5, 2)}", actual]
    if actual == "expand" and is_opex_friday(snap.session_date):
        evidence.append("OpEx 放量，有效性打折")
    return Check(actual == state, tuple(evidence))
