"""数据源边界（AF §4）。业务层只依赖这些 Protocol，不依赖具体数据源。

所有方法都遵守 as_of：不得返回 as_of 时点之后才可获得的数据。
"""

from datetime import date, datetime
from typing import Protocol

from tradesys.models import AnalysisContext, Bars, Candidate, Chain, Fundamental, RuleResult


class MarketDataSource(Protocol):
    name: str

    def daily(self, ticker: str, start: date, end: date) -> Bars: ...


class OptionChainSource(Protocol):
    name: str

    def chain(self, ticker: str, expiry: date, as_of: datetime) -> Chain | None:
        """无法提供 as_of 时点的期权链时返回 None。"""
        ...


class CalendarSource(Protocol):
    name: str

    def next_earnings(self, ticker: str, as_of: datetime) -> date | None: ...


class FundamentalSource(Protocol):
    name: str

    def snapshot(self, ticker: str, as_of: datetime) -> Fundamental | None: ...


class ContextVeto(Protocol):
    def __call__(self, ctx: AnalysisContext) -> RuleResult: ...


class CandidateVeto(Protocol):
    def __call__(self, ctx: AnalysisContext, candidate: Candidate) -> RuleResult: ...
