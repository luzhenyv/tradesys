"""数据对象（DESIGN §2）。全部为 frozen dataclass，可经 serialize.py 与 JSON 互转。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Literal

# ---------- 市场数据 ----------


@dataclass(frozen=True)
class Bar:
    d: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Bars:
    """按日期升序的日线序列。"""

    ticker: str
    items: tuple[Bar, ...]

    @property
    def closes(self) -> tuple[float, ...]:
        return tuple(b.close for b in self.items)

    @property
    def volumes(self) -> tuple[float, ...]:
        return tuple(b.volume for b in self.items)

    @property
    def highs(self) -> tuple[float, ...]:
        return tuple(b.high for b in self.items)

    @property
    def lows(self) -> tuple[float, ...]:
        return tuple(b.low for b in self.items)

    @property
    def last(self) -> Bar:
        return self.items[-1]

    def upto(self, d: date) -> Bars:
        return Bars(self.ticker, tuple(b for b in self.items if b.d <= d))


@dataclass(frozen=True)
class OptionQuote:
    strike: float
    kind: Literal["call", "put"]
    bid: float
    ask: float


@dataclass(frozen=True)
class Chain:
    ticker: str
    expiry: date
    as_of: datetime  # UTC 时间
    quotes: tuple[OptionQuote, ...]


@dataclass(frozen=True)
class Fundamental:
    market_cap: float | None
    exchange: str | None
    sector: str | None


# ---------- 档案中人写的内容（data/tickers/<TICKER>.yaml） ----------


@dataclass(frozen=True)
class Zone:
    id: str
    kind: Literal["support", "resistance"]
    low: float
    high: float


@dataclass(frozen=True)
class Line:
    id: str
    kind: Literal["trendline", "neckline", "flag_upper", "flag_lower", "flag_pole"]
    p1: tuple[date, float]
    p2: tuple[date, float]

    def value_at(self, d: date) -> float:
        (d1, v1), (d2, v2) = self.p1, self.p2
        slope = (v2 - v1) / (d2.toordinal() - d1.toordinal())
        return v1 + slope * (d.toordinal() - d1.toordinal())


@dataclass(frozen=True)
class Fact:
    """人的回答：值（布尔、数字或文本）+ 回答日期。有效期由读取它的 rule 块决定。"""

    value: bool | float | str
    at: date


# ---------- 工具的输入与输出 ----------


@dataclass(frozen=True)
class Snapshot:
    """某只股票在 as_of 时点的全部输入。

    as_of 为带时区的 UTC 时间；session_date 为对应的美东交易日，bars 已截止 session_date。
    """

    ticker: str
    as_of: datetime
    session_date: date
    bars: Bars
    zones: tuple[Zone, ...] = ()
    lines: tuple[Line, ...] = ()
    absent: tuple[str, ...] = ()  # 人已确认不存在的结构：zone / trendline / neckline / flag
    expired: tuple[str, ...] = ()  # 过期而未载入的结构类，需人复核
    facts: dict[str, Fact] = field(default_factory=dict)  # 人的回答，含 idea.reason / idea.source
    plans: tuple[Candidate, ...] = ()  # 档案中的计划（cancelled 已过滤）
    fundamental: Fundamental | None = None
    next_earnings: date | None = None
    chain: Chain | None = None
    sources: tuple[str, ...] = ()  # 数据来源，如 ("market=yahoo",)


@dataclass(frozen=True)
class Candidate:
    id: str
    setup_id: str
    entry: float
    stop: float | None
    target: float | None
    grade: str
    evidence: tuple[str, ...] = ()
    expires: date | None = None  # setup 产出不填；计划默认 at+20 个交易日
    status: str = "active"  # YAML：active | cancelled；暂停 / 过期由报告计算

    @property
    def rr(self) -> float | None:
        if self.stop is None or self.target is None or self.entry <= self.stop:
            return None
        return (self.target - self.entry) / (self.entry - self.stop)


@dataclass(frozen=True)
class Check:
    """一个工具的输出。hit=None 表示工具无法判断；missing=True 表示原因是缺数据。"""

    hit: bool | None
    evidence: tuple[str, ...] = ()
    review: bool = False  # simple 近似算法，需人工复核
    missing: bool = False
    value: float | None = None  # setup 的 entry / stop / target
    grade: str | None = None  # setup 形态等级，如 C=中性


# ---------- 执行器的输出 ----------


class RuleStatus(StrEnum):
    PASS = "pass"
    VETO = "veto"
    WARN = "warn"
    MANUAL = "manual"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    title: str
    status: RuleStatus
    evidence: tuple[str, ...] = ()
    candidate_id: str | None = None
    review: bool = False
    trust: str = "decide"  # decide | review；报告用，执行器原样搬运
    kind: str = ""  # 决定结果的块：veto | warn | setup | advice


@dataclass(frozen=True)
class RunOutput:
    """一次 playbook 运行：规则结果 + 候选买点；snapshot 供 report 使用。"""

    results: tuple[RuleResult, ...]
    candidates: tuple[Candidate, ...] = ()
    snapshot: Snapshot | None = None
