"""纯日期计算（AF §4、§8）。"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from tradesys.models import Bars

ET = ZoneInfo("America/New_York")
MARKET_CLOSE = time(16, 0)


def session_date(bars: Bars, as_of: datetime) -> date:
    """as_of 之前（含）最近一个已收盘交易日。

    交易日由 bars 本身决定，不引入节假日日历。naive datetime 视为美东时间。
    """
    local = as_of.astimezone(ET) if as_of.tzinfo else as_of
    cutoff = local.date() if local.time() >= MARKET_CLOSE else local.date() - timedelta(days=1)
    closed = [b.d for b in bars.items if b.d <= cutoff]
    if not closed:
        raise ValueError(f"no completed session on or before {cutoff}")
    return closed[-1]


def is_opex_friday(d: date) -> bool:
    """月度期权交割日：每月第三个周五。"""
    return d.weekday() == 4 and 15 <= d.day <= 21
