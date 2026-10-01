"""跨层领域模型（AF §6）。全部为 frozen dataclass。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from tradesys.config import Config


# ---------- market data ----------


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
    as_of: datetime
    quotes: tuple[OptionQuote, ...]


@dataclass(frozen=True)
class Fundamental:
    market_cap: float | None
    exchange: str | None
    sector: str | None


# ---------- structures（来自 YAML，AF §10） ----------


@dataclass(frozen=True)
class Zone:
    id: str
    kind: Literal["support", "resistance"]
    low: float
    high: float


@dataclass(frozen=True)
class Line:
    id: str
    kind: Literal["trendline", "neckline", "flag_upper", "flag_lower"]
    p1: tuple[date, float]
    p2: tuple[date, float]

    def value_at(self, d: date) -> float:
        (d1, v1), (d2, v2) = self.p1, self.p2
        slope = (v2 - v1) / (d2.toordinal() - d1.toordinal())
        return v1 + slope * (d.toordinal() - d1.toordinal())


BreakState = Literal["intact", "false_break", "broken", "reclaimed"]


@dataclass(frozen=True)
class BreakVerdict:
    """相对结构原始角色的判定：broken = 原极性被收盘价打破并翻转，reclaimed = 恢复原极性。"""

    target_id: str
    state: BreakState
    on: date | None


# ---------- features ----------

VolumeState = Literal["shrink", "expand", "neutral"]


@dataclass(frozen=True)
class VolumeResult:
    vs_prev: tuple[float | None, ...]
    vs_ma5: tuple[float | None, ...]
    state: tuple[VolumeState, ...]


@dataclass(frozen=True)
class FeatureSet:
    volume: VolumeResult


# ---------- rules ----------


@dataclass(frozen=True)
class Candidate:
    id: str
    setup_id: str
    entry: float
    stop: float | None
    target: float | None
    grade: str
    evidence: tuple[str, ...] = ()

    @property
    def rr(self) -> float | None:
        if self.stop is None or self.target is None or self.entry <= self.stop:
            return None
        return (self.target - self.entry) / (self.entry - self.stop)


class RuleStatus(StrEnum):
    PASS = "pass"
    VETO = "veto"
    WARN = "warn"
    MANUAL = "manual"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    status: RuleStatus
    reason: str
    evidence: tuple[str, ...] = ()
    candidate_id: str | None = None
    review: bool = False  # simple 实现产生的结果，需人工复核


@dataclass(frozen=True)
class Band68:
    low: float
    high: float
    strike: float
    expiry: date


# ---------- context（AF §7） ----------


@dataclass(frozen=True)
class AnalysisContext:
    ticker: str
    as_of: datetime
    session_date: date
    bars: Bars
    features: FeatureSet
    config: Config
    data_sources: Mapping[str, str]
    zones: tuple[Zone, ...] = ()
    lines: tuple[Line, ...] = ()
    fundamental: Fundamental | None = None
    next_earnings: date | None = None
    band68: Band68 | None = None
    journal: object | None = None  # JournalSlice，V1 未实现
