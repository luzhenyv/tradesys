"""P-BREAK · EP272：收盘定盘判定突破 / 破位，盘中刺破无效。"""

from tradesys.models import Bars, BreakState, BreakVerdict, Zone


def break_verdict(zone: Zone, bars: Bars) -> BreakVerdict:
    """逐日回放 bars，返回最后一日的判定。

    支撑区间：收盘 < low → broken（转为阻力）；此后只有收盘 > high 才算 reclaimed。
    阻力区间镜像：收盘 > high → broken（突破，转为支撑）；此后收盘 < low 才算 reclaimed。
    """
    support = zone.kind == "support"
    flipped = False
    state: BreakState = "intact"
    on = None

    for b in bars.items:
        if not flipped:
            closed_through = b.close < zone.low if support else b.close > zone.high
            poked = b.low < zone.low if support else b.high > zone.high
            if closed_through:
                flipped, state, on = True, "broken", b.d
            elif poked:
                state, on = "false_break", b.d
            elif state == "false_break":
                state = "intact"
        else:
            recovered = b.close > zone.high if support else b.close < zone.low
            if recovered:
                flipped, state, on = False, "reclaimed", b.d

    return BreakVerdict(target_id=zone.id, state=state, on=on)
