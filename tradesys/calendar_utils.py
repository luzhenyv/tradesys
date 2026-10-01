"""纯日期计算与 Snapshot 组装（DESIGN §6）。

系统内部统一使用 UTC 时间；只在涉及美股交易时段与交易日时转换为美东时间（ET）。
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tradesys.models import Bars, Snapshot

ET = ZoneInfo("America/New_York")
MARKET_CLOSE = time(16, 0)


def now_utc() -> datetime:
    """当前带时区的 UTC 时间。"""
    return datetime.now(UTC)


def to_utc(dt: datetime) -> datetime:
    """转为带时区的 UTC 时间；naive datetime 视为已是 UTC 时间。"""
    return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)


def to_et(dt: datetime) -> datetime:
    """转为带时区的美东时间；naive datetime 视为 UTC 后转美东。"""
    return to_utc(dt).astimezone(ET)


def parse_as_of(as_of: str | datetime | None, tz: str | ZoneInfo = "UTC") -> datetime:
    """解析 as_of 并转为带时区的 UTC 时间。

    - as_of 为 None 时取当前 UTC 时间。
    - 若输入本身带时区（如 ISO 字符串带 +08:00 / Z），以此为准并转为 UTC。
    - 若输入不带时区，则按传入的 tz（默认 UTC）解释，再转为 UTC。
    """
    if as_of is None:
        return now_utc()

    try:
        zone = ZoneInfo(tz) if isinstance(tz, str) else tz
    except ZoneInfoNotFoundError as e:
        raise ValueError(f"未知时区: {tz}") from e

    if isinstance(as_of, str):
        dt = datetime.fromisoformat(as_of)
    else:
        dt = as_of

    if dt.tzinfo is not None:
        return dt.astimezone(UTC)
    return dt.replace(tzinfo=zone).astimezone(UTC)


def session_date(bars: Bars, as_of: datetime) -> date:
    """as_of 之前（含）最近一个已收盘交易日。

    交易日由 bars 本身决定，不引入节假日日历。as_of 先转换为美东时间判定。
    """
    local = to_et(as_of)
    cutoff = local.date() if local.time() >= MARKET_CLOSE else local.date() - timedelta(days=1)
    closed = [b.d for b in bars.items if b.d <= cutoff]
    if not closed:
        raise ValueError(f"no completed session on or before {cutoff}")
    return closed[-1]


def is_opex_friday(d: date) -> bool:
    """月度期权交割日：每月第三个周五。"""
    return d.weekday() == 4 and 15 <= d.day <= 21


def weekdays_between(start: date, end: date) -> int:
    """(start, end] 之间的工作日数。同一天为 0；end 早于 start 为负数。"""
    if end < start:
        return -weekdays_between(end, start)
    n, d = 0, start + timedelta(days=1)
    while d <= end:
        n += d.weekday() < 5
        d += timedelta(days=1)
    return n


def make_snapshot(bars: Bars, as_of: datetime, **inputs) -> Snapshot:
    """把 as_of 统一为 UTC 并解析为 session_date，截取 bars，组装 Snapshot。inputs 为其余字段。"""
    utc_as_of = to_utc(as_of)
    sd = session_date(bars, utc_as_of)
    return Snapshot(bars.ticker, utc_as_of, sd, bars.upto(sd), **inputs)
