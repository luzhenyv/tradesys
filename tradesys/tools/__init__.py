"""工具注册表（DESIGN §4）。playbook 的 rule 块按名字引用这里的工具。

约定：tool(snap, **args) -> Check；scope: candidate 的工具为 tool(snap, candidate, **args)。
"""

from tradesys.tools.band68 import band68_range
from tradesys.tools.listing import days_to_earnings, exchange_not_in, market_cap_below
from tradesys.tools.price import close_up, drop_pct, new_high, new_low
from tradesys.tools.risk import rr_below, stop_wider_than
from tradesys.tools.rsi import rsi_above
from tradesys.tools.trend import trend
from tradesys.tools.volume import volume_declining, volume_ma5_turning_down, volume_state

TOOLS = {
    "new_low": new_low,
    "new_high": new_high,
    "close_up": close_up,
    "drop_pct": drop_pct,
    "volume_state": volume_state,
    "volume_declining": volume_declining,
    "volume_ma5_turning_down": volume_ma5_turning_down,
    "trend": trend,
    "rsi_above": rsi_above,
    "days_to_earnings": days_to_earnings,
    "exchange_not_in": exchange_not_in,
    "market_cap_below": market_cap_below,
    "stop_wider_than": stop_wider_than,
    "rr_below": rr_below,
    "band68_range": band68_range,
}
