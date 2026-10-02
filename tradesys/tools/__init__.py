"""工具注册表（DESIGN §5）。playbook 的 rule 块按名字引用这里的工具。

约定：tool(snap, **args) -> Check；scope: candidate 的工具为 tool(snap, candidate, **args)。
candidate 规则里可以组合不接收 candidate 的工具（只看 Snapshot）。
"""

import inspect

from tradesys.tools.band68 import band68_edge, band68_range
from tradesys.tools.candle import (
    bullish_engulfing,
    green_expand,
    hammer,
    shooting_star,
    stop_candle,
)
from tradesys.tools.fib import fib_broken, fib_holds, fib_stop, impulse_high
from tradesys.tools.flag import buffered_flag_lower, flag_break, flag_pole_high
from tradesys.tools.listing import days_to_earnings, exchange_not_in, market_cap_below
from tradesys.tools.price import close_up, drop_pct, new_high, new_low
from tradesys.tools.proximity import far_from_support, tight_to_resistance
from tradesys.tools.quote import buffered_low, nearest_resistance, session_close
from tradesys.tools.retest import buffered_line, buffered_zone_low, retest_breakout, retest_line
from tradesys.tools.risk import rr_below, stop_wider_than
from tradesys.tools.rsi import rsi_above, rsi_below, rsi_below_within
from tradesys.tools.setup import first_down, pullback_to_ma, up_streak
from tradesys.tools.structure import line_broken_within, zone_broken_within
from tradesys.tools.swing import divergence
from tradesys.tools.trend import trend
from tradesys.tools.volume import (
    volume_declining,
    volume_dry,
    volume_ma5_turning_down,
    volume_state,
)

TOOLS = {
    "new_low": new_low,
    "new_high": new_high,
    "close_up": close_up,
    "drop_pct": drop_pct,
    "volume_state": volume_state,
    "volume_declining": volume_declining,
    "volume_ma5_turning_down": volume_ma5_turning_down,
    "volume_dry": volume_dry,
    "trend": trend,
    "rsi_above": rsi_above,
    "rsi_below": rsi_below,
    "rsi_below_within": rsi_below_within,
    "divergence": divergence,
    "fib_broken": fib_broken,
    "fib_holds": fib_holds,
    "fib_stop": fib_stop,
    "impulse_high": impulse_high,
    "hammer": hammer,
    "bullish_engulfing": bullish_engulfing,
    "shooting_star": shooting_star,
    "stop_candle": stop_candle,
    "green_expand": green_expand,
    "retest_breakout": retest_breakout,
    "retest_line": retest_line,
    "buffered_zone_low": buffered_zone_low,
    "buffered_line": buffered_line,
    "flag_break": flag_break,
    "buffered_flag_lower": buffered_flag_lower,
    "flag_pole_high": flag_pole_high,
    "up_streak": up_streak,
    "first_down": first_down,
    "pullback_to_ma": pullback_to_ma,
    "session_close": session_close,
    "buffered_low": buffered_low,
    "nearest_resistance": nearest_resistance,
    "days_to_earnings": days_to_earnings,
    "exchange_not_in": exchange_not_in,
    "market_cap_below": market_cap_below,
    "zone_broken_within": zone_broken_within,
    "line_broken_within": line_broken_within,
    "far_from_support": far_from_support,
    "tight_to_resistance": tight_to_resistance,
    "stop_wider_than": stop_wider_than,
    "rr_below": rr_below,
    "band68_range": band68_range,
    "band68_edge": band68_edge,
}


def call(name: str, snap, args: dict | None = None, candidate=None):
    """按工具签名调用：只有声明了 candidate 参数的工具才传入候选买点。"""
    fn = TOOLS[name]
    takes = candidate is not None and "candidate" in inspect.signature(fn).parameters
    extra = (candidate,) if takes else ()
    return fn(snap, *extra, **(args or {}))
