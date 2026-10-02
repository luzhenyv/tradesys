"""纯日期计算与 Snapshot 组装（DESIGN §7）。

系统内部统一使用 UTC 时间；只在涉及美股交易时段与交易日时转换为美东时间（ET）。
"""

from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tradesys.models import Bars, Snapshot

ET = ZoneInfo("America/New_York")
MARKET_OPEN, MARKET_CLOSE = time(9, 30), time(16, 0)
# NYSE 全日休市（2025–2027）；范围之外只按周末判断，需逐年补充
NYSE_HOLIDAYS = frozenset(
    date.fromisoformat(d)
    for d in (
        "2025-01-01 2025-01-09 2025-01-20 2025-02-17 2025-04-18 2025-05-26 2025-06-19 "
        "2025-07-04 2025-09-01 2025-11-27 2025-12-25 "
        "2026-01-01 2026-01-19 2026-02-16 2026-04-03 2026-05-25 2026-06-19 2026-07-03 "
        "2026-09-07 2026-11-26 2026-12-25 "
        "2027-01-01 2027-01-18 2027-02-15 2027-03-26 2027-05-31 2027-06-18 2027-07-05 "
        "2027-09-06 2027-11-25 2027-12-24"
    ).split()
)


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


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in NYSE_HOLIDAYS


def is_monthly_opex(d: date) -> bool:
    """月度期权交割日：每月第三个周五；该日休市则提前到周四（如 2025-04-18 Good Friday）。"""
    friday = d + timedelta(days=(4 - d.weekday()) % 7)
    if friday - d > timedelta(days=1) or not 15 <= friday.day <= 21:
        return False
    return d == (friday if is_trading_day(friday) else friday - timedelta(days=1))


def trading_days_between(start: date, end: date) -> int:
    """(start, end] 之间的交易日数（跳过周末与 NYSE 休市）。同一天为 0；end 早于 start 为负数。"""
    if end < start:
        return -trading_days_between(end, start)
    n, d = 0, start + timedelta(days=1)
    while d <= end:
        n += is_trading_day(d)
        d += timedelta(days=1)
    return n


def next_trading_day(d: date) -> date:
    n = d + timedelta(days=1)
    while not is_trading_day(n):
        n += timedelta(days=1)
    return n


def add_trading_days(d: date, n: int) -> date:
    """d 之后第 n 个交易日。"""
    for _ in range(n):
        d = next_trading_day(d)
    return d


def session_open_since(session: date, now: datetime) -> bool:
    """session 收盘之后，到 now 为止是否已有新的常规时段开盘（下一交易日 9:30 ET）。"""
    return to_et(now) >= datetime.combine(next_trading_day(session), MARKET_OPEN, tzinfo=ET)


def at_offset(snap: Snapshot, offset: int) -> Snapshot:
    """去掉最后 offset 根，在 T−offset 上求值。offset=0 原样返回。"""
    if offset <= 0:
        return snap
    items = snap.bars.items[:-offset] if offset < len(snap.bars.items) else ()
    bars = Bars(snap.bars.ticker, items)
    if not items:
        return replace(snap, bars=bars)
    return replace(snap, bars=bars, session_date=items[-1].d)


def make_snapshot(bars: Bars, as_of: datetime, **inputs) -> Snapshot:
    """把 as_of 统一为 UTC 并解析为 session_date，截取 bars，组装 Snapshot。inputs 为其余字段。"""
    utc_as_of = to_utc(as_of)
    sd = session_date(bars, utc_as_of)
    return Snapshot(bars.ticker, utc_as_of, sd, bars.upto(sd), **inputs)
