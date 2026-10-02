"""上升旗形 · EP150。旗杆 flag_pole 与 A/B 线 flag_upper / flag_lower 均由人在 YAML 中画出。"""

from tradesys.models import Bar, Check, Line, Snapshot
from tradesys.tools.fib import retrace
from tradesys.tools.structure import no_structure
from tradesys.tools.volume import state_at

KINDS = ("flag_upper", "flag_lower", "flag_pole")


def _flag(snap: Snapshot) -> tuple[Line, Line, Line] | Check:
    """(A 线, B 线, 旗杆)，旗杆 p1 = 杆底，p2 = 杆顶；缺失或多组时返回 Check。"""
    found = [[ln for ln in snap.lines if ln.kind == k] for k in KINDS]
    if not all(found):
        return no_structure(snap, "flag")
    if any(len(f) > 1 for f in found):
        return Check(None, ("YAML 中有多组旗形线，请只保留当前一组",))
    return found[0][0], found[1][0], found[2][0]


def _avg(bars: tuple[Bar, ...]) -> float:
    return sum(x.volume for x in bars) / len(bars)


def flag_break(snap: Snapshot, pre: int) -> Check:
    """旗杆均量高于杆底前 pre 根、旗面缩量且守住旗杆 61.8%、T 收盘越过 A 线。"""
    flag = _flag(snap)
    if isinstance(flag, Check):
        return flag
    a, _, p = flag
    items = snap.bars.items
    (d0, low), (d1, high) = p.p1, p.p2
    before = tuple(x for x in items if x.d < d0)[-pre:]
    pole = tuple(x for x in items if d0 <= x.d <= d1)
    body = tuple(x for x in items[:-1] if x.d > d1)
    if len(before) < pre:
        return Check(None, (f"旗杆前不足 {pre} 根",), missing=True)
    if len(pole) < 2 or len(body) < 2:
        return Check(False, ("旗杆或旗面过短",))
    if _avg(pole) <= _avg(before) or _avg(body) >= _avg(pole):
        return Check(False, ("量能不符合旗形",))
    reds = 0
    for i, b in enumerate(items[:-1]):
        red = b in body and b.close < b.open and state_at(snap.bars.volumes[: i + 1]) == "expand"
        reds = reds + 1 if red else 0
        if reds >= 2:
            return Check(False, ("旗面持续放量大阴",))
    if min(x.close for x in body) < retrace(low, high, 0.618):
        return Check(False, ("旗面跌破旗杆 61.8%",))
    last, at = snap.bars.last, a.value_at(snap.session_date)
    if last.close <= at:
        return Check(False, (f"收盘未过 A 线 {at:.2f}",))
    t2 = last.close + (high - low)
    return Check(True, (f"A={at:.2f}", f"pole={low}→{high}", f"T2={t2:.2f}"))


def buffered_flag_lower(snap: Snapshot, pct: float) -> Check:
    """B(T) × (1−pct)。"""
    flag = _flag(snap)
    if isinstance(flag, Check):
        return flag
    v = flag[1].value_at(snap.session_date) * (1 - pct)
    return Check(True, (f"stop={v}",), value=v)


def flag_pole_high(snap: Snapshot) -> Check:
    """旗杆顶（T1），取 YAML 中 flag_pole 的 p2。"""
    flag = _flag(snap)
    if isinstance(flag, Check):
        return flag
    v = flag[2].p2[1]
    return Check(True, (f"T1={v}",), value=v)
