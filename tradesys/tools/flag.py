"""上升旗形（YAML A/B 线）· EP150。旗杆切分是近似，review=True。"""

from datetime import date

from tradesys.models import Check, Line, Snapshot
from tradesys.tools.fib import retrace
from tradesys.tools.structure import ASK
from tradesys.tools.volume import state_at


def _pair(snap: Snapshot) -> tuple[Line, Line] | None:
    up = [ln for ln in snap.lines if ln.kind == "flag_upper"]
    lo = [ln for ln in snap.lines if ln.kind == "flag_lower"]
    if not up or not lo:
        return None
    return up[0], lo[0]


def _start(a: Line, b: Line) -> date:
    return min(a.p1[0], a.p2[0], b.p1[0], b.p2[0])


def _windows(snap: Snapshot) -> tuple[tuple, tuple, tuple] | None:
    pair = _pair(snap)
    if pair is None:
        return None
    a, b = pair
    start = _start(a, b)
    pole = tuple(x for x in snap.bars.items if x.d < start)
    flag = tuple(x for x in snap.bars.items[:-1] if x.d >= start)
    return pole, flag, pair


def flag_break(snap: Snapshot) -> Check:
    """旗杆放量、旗面缩量且守住 61.8%、T 收盘越过 A 线。"""
    win = _windows(snap)
    if win is None:
        return Check(None, (ASK,), review=True)
    pole, flag, (a, _) = win
    if len(pole) < 25 or len(flag) < 2:
        return Check(False, ("旗杆或旗面过短",), review=True)
    before, pole = pole[:20], pole[20:]
    if len(pole) < 5:
        return Check(False, ("旗杆过短",), review=True)
    pole_vol = sum(x.volume for x in pole) / len(pole)
    flag_vol = sum(x.volume for x in flag) / len(flag)
    pre_vol = sum(x.volume for x in before) / len(before)
    if pole_vol <= pre_vol or flag_vol >= pole_vol:
        return Check(False, ("量能不符合旗形",), review=True)
    dates = [x.d for x in snap.bars.items]
    reds = 0
    for b in flag:
        vols = tuple(x.volume for x in snap.bars.items[: dates.index(b.d) + 1])
        if b.close < b.open and state_at(vols) == "expand":
            reds += 1
            if reds >= 2:
                return Check(False, ("旗面持续放量大阴",), review=True)
        else:
            reds = 0
    low, high = min(x.close for x in pole), max(x.close for x in pole)
    if min(x.close for x in flag) < retrace(low, high, 0.618):
        return Check(False, ("旗面跌破旗杆 61.8%",), review=True)
    last, at = snap.bars.last, a.value_at(snap.session_date)
    if last.close <= at:
        return Check(False, (f"收盘未过 A 线 {at:.2f}",), review=True)
    t2 = last.close + (high - low)
    return Check(True, (f"A={at:.2f}", f"pole_high={high}", f"T2={t2:.2f}"), review=True)


def buffered_flag_lower(snap: Snapshot, pct: float) -> Check:
    """B(T) × (1−pct)。"""
    pair = _pair(snap)
    if pair is None:
        return Check(None, (ASK,), review=True)
    _, b = pair
    v = b.value_at(snap.session_date) * (1 - pct)
    return Check(True, (f"stop={v}",), review=True, value=v)


def flag_pole_high(snap: Snapshot) -> Check:
    """旗杆最高收盘（T1）。"""
    win = _windows(snap)
    if win is None:
        return Check(None, (ASK,), review=True)
    pre, _, _ = win
    pole = pre[20:] if len(pre) >= 25 else pre
    if not pole:
        return Check(True, ("无旗杆",), review=True, value=None)
    v = max(x.close for x in pole)
    return Check(True, (f"T1={v}",), review=True, value=v)
