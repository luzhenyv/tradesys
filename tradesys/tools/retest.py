"""YAML 结构的突破回踩（区间与线）。无结构 → MANUAL。"""

from tradesys.models import Check, Line, Snapshot, Zone
from tradesys.tools.structure import ASK, break_verdict, line_break_verdict
from tradesys.tools.volume import state_at


def _vols(snap: Snapshot, end: int) -> tuple[float, ...]:
    return tuple(b.volume for b in snap.bars.items[: end + 1])


def _slope_down(line: Line) -> bool:
    (d1, v1), (d2, v2) = line.p1, line.p2
    return (v2 < v1) if d2 >= d1 else (v1 < v2)


def find_retest_zone(snap: Snapshot, lookback: int) -> Zone | None:
    """最近一次放量突破阻力、且正在区间内缩量回踩的 Zone。"""
    dates = [b.d for b in snap.bars.items]
    t = len(dates) - 1
    best: tuple[int, Zone] | None = None
    for z in snap.zones:
        if z.kind != "resistance":
            continue
        state, on = break_verdict(z, snap.bars)
        if state != "broken" or on not in dates:
            continue
        i = dates.index(on)
        if i >= t or t - i >= lookback:
            continue
        if state_at(_vols(snap, i)) != "expand":
            continue
        after = snap.bars.items[i + 1 :]
        if any(b.close < z.low for b in after):
            continue
        last = snap.bars.last
        if not (z.low <= last.close <= z.high):
            continue
        pull = after[:-1]  # 回踩日不含 T，T 的量能由触发工具检查
        if any(state_at(_vols(snap, i + 1 + j)) == "expand" for j in range(len(pull))):
            continue
        if best is None or i > best[0]:
            best = (i, z)
    return None if best is None else best[1]


def find_retest_line(
    snap: Snapshot, kind: str, side: str, lookback: int, slope: str | None = None
) -> Line | None:
    dates = [b.d for b in snap.bars.items]
    t = len(dates) - 1
    best: tuple[int, Line] | None = None
    for line in snap.lines:
        if line.kind != kind:
            continue
        if slope == "down" and not _slope_down(line):
            continue
        if slope == "up" and _slope_down(line):
            continue
        state, on = line_break_verdict(line, snap.bars, side)
        if state != "broken" or on not in dates:
            continue
        i = dates.index(on)
        if i >= t or t - i >= lookback:
            continue
        if state_at(_vols(snap, i)) != "expand":
            continue
        ok = True
        for b in snap.bars.items[i + 1 :]:
            lv = line.value_at(b.d)
            crossed = b.close < lv if side == "above" else b.close > lv
            if crossed:
                ok = False
                break
        if not ok:
            continue
        if best is None or i > best[0]:
            best = (i, line)
    return None if best is None else best[1]


def retest_breakout(snap: Snapshot, lookback: int = 20) -> Check:
    """阻力放量突破后，缩量回踩仍在区间内。"""
    if not snap.zones:
        return Check(None, (ASK,))
    z = find_retest_zone(snap, lookback)
    if z is None:
        return Check(False, ("无放量突破回踩",))
    return Check(True, (f"{z.id} {z.low}-{z.high} 回踩",))


def retest_line(
    snap: Snapshot,
    kind: str,
    side: str,
    lookback: int = 20,
    slope: str | None = None,
    near_pct: float | None = None,
    touch_pct: float | None = None,
) -> Check:
    """线放量突破后回踩不破。"""
    if not any(ln.kind == kind for ln in snap.lines):
        return Check(None, (ASK,))
    line = find_retest_line(snap, kind, side, lookback, slope)
    if line is None:
        return Check(False, (f"无 {kind} 突破回踩",))
    last, lv = snap.bars.last, line.value_at(snap.session_date)
    if touch_pct is not None:
        if last.close < lv or last.open < lv:
            return Check(False, ("开盘或收盘在颈线下方",))
        if abs(last.low - lv) / lv > touch_pct:
            return Check(False, (f"low 未触及 {line.id}",))
    if near_pct is not None:
        if last.close < lv or (last.close - lv) / last.close > near_pct:
            return Check(False, (f"收盘未贴近 {line.id}",))
    return Check(True, (f"{line.id} 回踩 {lv:.2f}",))


def buffered_zone_low(snap: Snapshot, lookback: int, pct: float) -> Check:
    """回踩中的突破区间下沿 × (1−pct)。"""
    if not snap.zones:
        return Check(None, (ASK,))
    z = find_retest_zone(snap, lookback)
    if z is None:
        return Check(True, ("无回踩区间",), value=None)
    v = z.low * (1 - pct)
    return Check(True, (f"{z.id} stop={v}",), value=v)


def buffered_line(
    snap: Snapshot,
    kind: str,
    side: str,
    lookback: int,
    pct: float,
    slope: str | None = None,
) -> Check:
    """回踩中的线值 × (1−pct)。"""
    if not any(ln.kind == kind for ln in snap.lines):
        return Check(None, (ASK,))
    line = find_retest_line(snap, kind, side, lookback, slope)
    if line is None:
        return Check(True, ("无线可止损",), value=None)
    lv = line.value_at(snap.session_date)
    return Check(True, (f"{line.id} stop={lv * (1 - pct)}",), value=lv * (1 - pct))
