"""Setup 取价：entry / stop / target → Check.value。"""

from tradesys.models import Check, Snapshot
from tradesys.tools.structure import current_role


def session_close(snap: Snapshot) -> Check:
    """T 日收盘价，作为次日计划参考入场价。"""
    v = snap.bars.last.close
    return Check(True, (f"close={v}",), value=v)


def buffered_low(snap: Snapshot, pct: float) -> Check:
    """low[T] × (1 − pct)，预留扫损缓冲。"""
    v = snap.bars.last.low * (1 - pct)
    return Check(True, (f"low={snap.bars.last.low}", f"stop={v}"), value=v)


def nearest_resistance(snap: Snapshot) -> Check:
    """entry（T 收盘）上方最近当前阻力的下沿；没有则为 None。"""
    entry = snap.bars.last.close
    above = [z for z in snap.zones if current_role(z, snap.bars) == "resistance" and z.low > entry]
    if not above:
        return Check(True, ("上方无阻力",), value=None)
    z = min(above, key=lambda z: z.low)
    return Check(True, (f"{z.id} {z.low}-{z.high}",), value=z.low)
