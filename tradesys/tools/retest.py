"""YAML 结构的突破回踩（区间与线）。无结构 → MANUAL；absent 声明不存在 → 不适用。"""

from tradesys.models import Check, Line, Snapshot, Zone
from tradesys.tools.structure import break_verdict, line_break_verdict, no_structure
from tradesys.tools.volume import state_at


def _vols(snap: Snapshot, end: int) -> tuple[float, ...]:
    return tuple(b.volume for b in snap.bars.items[: end + 1])


def _slope_down(line: Line) -> bool:
    (d1, v1), (d2, v2) = line.p1, line.p2
    return (v2 < v1) if d2 >= d1 else (v1 < v2)


def _latest(snap: Snapshot, items, verdict, lookback: int, holds):
    """items 中最近一次在 lookback 根内放量突破（不含 T）、且 holds(x, i) 成立的结构。"""
    dates = [b.d for b in snap.bars.items]
    t = len(dates) - 1
    best = None
    for x in items:
        state, on = verdict(x)
        if state != "broken" or on not in dates:
            continue
        i = dates.index(on)
        if i >= t or t - i >= lookback or state_at(_vols(snap, i)) != "expand":
            continue
        if holds(x, i) and (best is None or i > best[0]):
            best = (i, x)
    return None if best is None else best[1]


def find_retest_zone(snap: Snapshot, lookback: int) -> Zone | None:
    """最近一次放量突破阻力、且正在区间内缩量回踩的 Zone。"""

    def holds(z: Zone, i: int) -> bool:
        after = snap.bars.items[i + 1 :]
        pull = range(i + 1, len(snap.bars.items) - 1)  # 回踩日不含 T，T 的量能由触发工具检查
        return (
            all(b.close >= z.low for b in after)
            and z.low <= snap.bars.last.close <= z.high
            and not any(state_at(_vols(snap, j)) == "expand" for j in pull)
        )

    zones = [z for z in snap.zones if z.kind == "resistance"]
    return _latest(snap, zones, lambda z: break_verdict(z, snap.bars), lookback, holds)


def find_retest_line(
    snap: Snapshot, kind: str, side: str, lookback: int, slope: str | None = None
) -> Line | None:
    """最近一次放量穿越 side、此后收盘未回到另一侧的 Line。"""

    def holds(line: Line, i: int) -> bool:
        after = snap.bars.items[i + 1 :]
        if side == "above":
            return all(b.close >= line.value_at(b.d) for b in after)
        return all(b.close <= line.value_at(b.d) for b in after)

    lines = [
        ln
        for ln in snap.lines
        if ln.kind == kind and slope in (None, "down" if _slope_down(ln) else "up")
    ]
    verdict = lambda ln: line_break_verdict(ln, snap.bars, side)  # noqa: E731
    return _latest(snap, lines, verdict, lookback, holds)


def retest_breakout(snap: Snapshot, lookback: int = 20) -> Check:
    """阻力放量突破后，缩量回踩仍在区间内。"""
    if not snap.zones:
        return no_structure(snap, "zone")
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
        return no_structure(snap, kind)
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
        return no_structure(snap, "zone")
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
        return no_structure(snap, kind)
    line = find_retest_line(snap, kind, side, lookback, slope)
    if line is None:
        return Check(True, ("无线可止损",), value=None)
    lv = line.value_at(snap.session_date)
    return Check(True, (f"{line.id} stop={lv * (1 - pct)}",), value=lv * (1 - pct))
