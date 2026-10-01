"""工具注册表（DESIGN §4）。playbook 的 rule 块按名字引用这里的工具。

约定：tool(snap, **args) -> Check；scope: candidate 的工具为 tool(snap, candidate, **args)。
"""

from tradesys.tools.band68 import band68_range
from tradesys.tools.price import new_high, new_low
from tradesys.tools.risk import rr_below, stop_wider_than
from tradesys.tools.volume import volume_state

TOOLS = {
    "new_low": new_low,
    "new_high": new_high,
    "volume_state": volume_state,
    "stop_wider_than": stop_wider_than,
    "rr_below": rr_below,
    "band68_range": band68_range,
}
