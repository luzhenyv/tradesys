"""P-BREAK · EP272：收盘定盘判定突破 / 破位，盘中刺破无效。"""

from datetime import date
from typing import Literal

from tradesys.models import Bars, Check, Line, Snapshot, Zone
from tradesys.tools.volume import classify, volume_ratios

BreakState = Literal["intact", "false_break", "broken", "reclaimed"]
ASK = "请在 YAML 中标注结构"


def no_structure(snap: Snapshot, kind: str) -> Check:
    """缺少 kind 结构：人已在 absent 中确认不存在 → False（不适用）；否则 None（请标注或复核）。"""
    if kind in snap.absent:
        return Check(False, (f"已确认无 {kind}，不适用",))
    if kind in snap.expired:
        return Check(None, (f"{kind} 已过期，请复核后更新 confirmed_at",))
    return Check(None, (f"{ASK}（{kind}），或在 absent 中声明不存在",))


def break_verdict(zone: Zone, bars: Bars) -> tuple[BreakState, date | None]:
    """逐日回放 bars，返回最后一日的 (状态, 发生日)。

    支撑区间：收盘 < low → broken（转为阻力）；此后只有收盘 > high 才算 reclaimed。
    阻力区间镜像：收盘 > high → broken（突破，转为支撑）；此后收盘 < low 才算 reclaimed。
    """
    support = zone.kind == "support"
    return _replay(
        bars,
        None,
        through=lambda b, z: b.close < z.low if support else b.close > z.high,
        poke=lambda b, z: b.low < z.low if support else b.high > z.high,
        recover=lambda b, z: b.close > z.high if support else b.close < z.low,
        level=lambda _b: zone,
    )


def line_break_verdict(line: Line, bars: Bars, side: str) -> tuple[BreakState, date | None]:
    """收盘穿越才算破；side=below 为跌破（价格应在线上）。从 p1 日起回放。"""
    below = side == "below"
    return _replay(
        bars,
        line.p1[0],
        through=lambda b, lv: b.close < lv if below else b.close > lv,
        poke=lambda b, lv: b.low < lv if below else b.high > lv,
        recover=lambda b, lv: b.close > lv if below else b.close < lv,
        level=lambda b: line.value_at(b.d),
    )


def _replay(bars: Bars, start: date | None, through, poke, recover, level):
    flipped, state, on = False, "intact", None
    for b in bars.items:
        if start is not None and b.d < start:
            continue
        lv = level(b)
        if not flipped:
            if through(b, lv):
                flipped, state, on = True, "broken", b.d
            elif poke(b, lv):
                state, on = "false_break", b.d
            elif state == "false_break":
                state = "intact"
        elif recover(b, lv):
            flipped, state, on = False, "reclaimed", b.d
    return state, on


def current_role(zone: Zone, bars: Bars) -> Literal["support", "resistance"]:
    """破位未收复则极性翻转；其余保持 YAML 里的 kind。"""
    state, _ = break_verdict(zone, bars)
    if state != "broken":
        return zone.kind
    return "resistance" if zone.kind == "support" else "support"


def _within(bars: Bars, on: date | None, days: int) -> bool:
    if on is None:
        return False
    dates = [b.d for b in bars.items]
    try:
        i = dates.index(on)
    except ValueError:
        return False
    return len(dates) - 1 - i < days


def _vol_tag(bars: Bars, on: date | None) -> tuple[str, ...]:
    if on is None:
        return ()
    prev, ma5 = volume_ratios(bars.upto(on).volumes)
    state = classify(prev, ma5, 1.0, 1.0)
    if state == "expand":
        return ("放量破位",)
    if state == "shrink":
        return ("缩量破位，有待观察",)
    return ()


def zone_broken_within(snap: Snapshot, kind: str, days: int) -> Check:
    """原始 kind 的 Zone 是否在最近 days 根内 broken 且未收复。"""
    if not snap.zones:
        return no_structure(snap, "zone")
    evidence: list[str] = []
    hit = False
    for z in snap.zones:
        if z.kind != kind:
            continue
        state, on = break_verdict(z, snap.bars)
        if state == "broken" and _within(snap.bars, on, days):
            hit = True
            evidence += [f"{z.id} {z.low}-{z.high} broken {on}", *_vol_tag(snap.bars, on)]
    return Check(hit, tuple(evidence) or (f"无近期 {kind} 破位",))


def line_broken_within(snap: Snapshot, kind: str, days: int, side: str) -> Check:
    """给定 kind 的 Line 是否在最近 days 根内收盘穿越 side。"""
    if not any(ln.kind == kind for ln in snap.lines):
        return no_structure(snap, kind)
    evidence: list[str] = []
    hit = False
    for line in snap.lines:
        if line.kind != kind:
            continue
        state, on = line_break_verdict(line, snap.bars, side)
        if state == "broken" and _within(snap.bars, on, days):
            hit = True
            evidence += [f"{line.id} broken {on}", *_vol_tag(snap.bars, on)]
    return Check(hit, tuple(evidence) or (f"无近期 {kind} 破位",))
