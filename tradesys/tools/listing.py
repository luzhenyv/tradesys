"""上市状态、市值、财报日距 · EP301§R07、§R10。"""

from tradesys.calendar_utils import weekdays_between
from tradesys.models import Check, Snapshot


def days_to_earnings(snap: Snapshot, max: int) -> Check:
    """距下次财报的交易日数是否 ≤ max。"""
    if snap.next_earnings is None:
        return Check(None, ("缺少财报日期",), missing=True)
    days = weekdays_between(snap.session_date, snap.next_earnings)
    return Check(
        0 <= days <= max,
        (f"距财报 {days} 个交易日", f"earnings={snap.next_earnings}", "请确认无明显利空消息"),
    )


def exchange_not_in(snap: Snapshot, codes: list[str]) -> Check:
    """交易所代码不在 codes 中。"""
    fund = snap.fundamental
    if fund is None or fund.exchange is None:
        return Check(None, ("缺少交易所信息",), missing=True)
    return Check(fund.exchange not in codes, (f"exchange={fund.exchange}",))


def market_cap_below(snap: Snapshot, usd: float) -> Check:
    """市值低于 usd 美元。"""
    fund = snap.fundamental
    if fund is None or fund.market_cap is None:
        return Check(None, ("缺少市值信息",), missing=True)
    return Check(
        fund.market_cap < usd,
        (f"market_cap={fund.market_cap}", f"threshold={usd}"),
    )
