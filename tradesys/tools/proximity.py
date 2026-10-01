"""当前极性下，候选买点与最近支撑 / 阻力的距离 · EP301§R12、§R13。"""

from tradesys.models import Candidate, Check, Snapshot
from tradesys.tools.structure import ASK, current_role


def far_from_support(snap: Snapshot, candidate: Candidate, pct: float) -> Check:
    """entry 距下方最近当前支撑上沿是否超过 pct；无支撑则为悬空。"""
    if not snap.zones:
        return Check(None, (ASK,))
    below = [
        z for z in snap.zones if current_role(z, snap.bars) == "support" and z.low < candidate.entry
    ]
    if not below:
        return Check(True, ("下方没有结构支撑（悬空）",))
    nearest = max(below, key=lambda z: z.high)
    dist = (candidate.entry - nearest.high) / candidate.entry
    return Check(
        dist > pct,
        (f"{nearest.id} {nearest.low}-{nearest.high}", f"距离={dist:.1%}"),
    )


def tight_to_resistance(snap: Snapshot, candidate: Candidate, pct: float) -> Check:
    """entry 距上方最近当前阻力下沿是否不足 pct。"""
    if not snap.zones:
        return Check(None, (ASK,))
    above = [
        z
        for z in snap.zones
        if current_role(z, snap.bars) == "resistance" and z.high > candidate.entry
    ]
    if not above:
        return Check(False, ("上方没有阻力区间",))
    nearest = min(above, key=lambda z: z.low)
    room = (nearest.low - candidate.entry) / candidate.entry
    return Check(
        room < pct,
        (f"{nearest.id} {nearest.low}-{nearest.high}", f"空间={room:.1%}"),
    )
