"""测试用数据：由简单的列表构造 Bars / Chain / Snapshot。"""

from datetime import date, datetime, timedelta

from tradesys.calendar_utils import ET, make_snapshot, to_utc
from tradesys.models import Bar, Bars, Chain, OptionQuote, Snapshot


def trading_days(start: date, n: int) -> list[date]:
    """从 start 起的 n 个工作日（不考虑节假日）。"""
    days, d = [], start
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def make_bars(
    closes: list[float],
    volumes: list[float] | None = None,
    ticker: str = "TEST",
    start: date = date(2026, 1, 5),
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
) -> Bars:
    """默认 open = high = low = close 的简化日线。"""
    vols = volumes or [1_000_000.0] * len(closes)
    ops = opens or closes
    his = highs or closes
    los = lows or closes
    days = trading_days(start, len(closes))
    return Bars(
        ticker,
        tuple(
            Bar(d, o, h, lo, c, v)
            for d, c, v, o, h, lo in zip(days, closes, vols, ops, his, los, strict=True)
        ),
    )


def make_chain(
    rows: list[tuple[float, float, float]],
    ticker: str = "TEST",
    expiry: date = date(2026, 4, 19),
    as_of: datetime | None = None,
) -> Chain:
    """rows: (strike, call_ask, put_ask)。bid 置 0，本系统只用 ask。"""
    quotes = []
    for strike, call_ask, put_ask in rows:
        quotes.append(OptionQuote(strike, "call", 0.0, call_ask))
        quotes.append(OptionQuote(strike, "put", 0.0, put_ask))
    when = to_utc(as_of or datetime(2026, 4, 12, 16, 30, tzinfo=ET))
    return Chain(ticker, expiry, when, tuple(quotes))


def fake_snapshot(bars: Bars, **inputs) -> Snapshot:
    """as_of 取最后一根 bar 当天美东 17:00（已收盘）对应的 UTC 时间。"""
    last = bars.last.d
    as_of = to_utc(datetime(last.year, last.month, last.day, 17, 0, tzinfo=ET))
    return make_snapshot(bars, as_of, sources=("market=fake",), **inputs)
