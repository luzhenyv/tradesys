"""P-BREAK · EP272：支撑 100–120 的破位时序。"""

from datetime import date

from tradesys.adapters.fake import trading_days
from tradesys.models import Bar, Bars, Zone
from tradesys.structure.zones import break_verdict

SUPPORT = Zone("z-100-120", "support", 100.0, 120.0)
RESISTANCE = Zone("r-100-120", "resistance", 100.0, 120.0)

# (low, close)：先在区间上方，再盘中刺破 99 收 100.5，然后收盘 95，反抽 105，最后收复 121
EP272_PATH = [(123, 125), (99, 100.5), (94, 95), (95, 105), (104, 121)]


def _bars(path: list[tuple[float, float]]) -> Bars:
    days = trading_days(date(2026, 1, 5), len(path))
    return Bars(
        "TEST",
        tuple(Bar(d, c, max(c, lo), lo, c, 1e6) for d, (lo, c) in zip(days, path, strict=True)),
    )


def _state(zone: Zone, n: int) -> str:
    return break_verdict(zone, _bars(EP272_PATH[:n])).state


def test_break_ep272_intraday_poke_close_above_is_false_break():
    assert _state(SUPPORT, 2) == "false_break"


def test_break_ep272_close_below_low_is_broken():
    assert _state(SUPPORT, 3) == "broken"


def test_break_ep272_bounce_into_zone_stays_broken():
    assert _state(SUPPORT, 4) == "broken"


def test_break_ep272_close_above_high_reclaims():
    assert _state(SUPPORT, 5) == "reclaimed"


def test_break_resistance_close_above_high_is_breakout():
    bars = _bars([(110, 115), (118, 125)])
    v = break_verdict(RESISTANCE, bars)
    assert (v.state, v.on) == ("broken", bars.last.d)
