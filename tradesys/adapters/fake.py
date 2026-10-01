"""测试用数据源：由简单的列表构造 Bars / Chain。"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from tradesys.models import Bar, Bars, Chain, OptionQuote


@dataclass(frozen=True)
class FakeMarket:
    bars: Bars
    name: str = "fake"

    def daily(self, ticker: str, start: date, end: date) -> Bars:
        return Bars(ticker, tuple(b for b in self.bars.items if start <= b.d <= end))


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
) -> Bars:
    """open = high = low = close 的简化日线；需要影线时用 make_bar 单独构造。"""
    vols = volumes or [1_000_000.0] * len(closes)
    days = trading_days(start, len(closes))
    return Bars(
        ticker, tuple(Bar(d, c, c, c, c, v) for d, c, v in zip(days, closes, vols, strict=True))
    )


def make_chain(
    rows: list[tuple[float, float, float]],
    ticker: str = "TEST",
    expiry: date = date(2026, 4, 19),
    as_of: datetime = datetime(2026, 4, 12, 16, 30),
) -> Chain:
    """rows: (strike, call_ask, put_ask)。bid 置 0，本系统只用 ask。"""
    quotes = []
    for strike, call_ask, put_ask in rows:
        quotes.append(OptionQuote(strike, "call", 0.0, call_ask))
        quotes.append(OptionQuote(strike, "put", 0.0, put_ask))
    return Chain(ticker, expiry, as_of, tuple(quotes))
