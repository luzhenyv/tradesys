"""唯一的编排者（AF §3.2）。Phase 0：只构建上下文并运行 context vetoes。"""

from datetime import datetime, timedelta

from tradesys.calendar_utils import session_date
from tradesys.config import Config
from tradesys.features.volume import volume
from tradesys.models import AnalysisContext, FeatureSet, RuleResult
from tradesys.protocols import CandidateVeto, ContextVeto, MarketDataSource
from tradesys.vetoes import v01, v05, v14

HISTORY_DAYS = 400

CONTEXT_VETOES: dict[str, ContextVeto] = {
    v01.ID: v01.evaluate,
}

CANDIDATE_VETOES: dict[str, CandidateVeto] = {
    v05.ID: v05.evaluate,
    v14.ID: v14.evaluate,
}


def build_context(
    ticker: str, as_of: datetime, market: MarketDataSource, config: Config
) -> AnalysisContext:
    raw = market.daily(ticker, as_of.date() - timedelta(days=HISTORY_DAYS), as_of.date())
    sd = session_date(raw, as_of)
    bars = raw.upto(sd)
    return AnalysisContext(
        ticker=ticker,
        as_of=as_of,
        session_date=sd,
        bars=bars,
        features=FeatureSet(volume=volume(bars, config.volume)),
        config=config,
        data_sources={"market": market.name},
    )


def run_context_vetoes(ctx: AnalysisContext) -> list[RuleResult]:
    disabled = set(ctx.config.veto.disabled)
    return [fn(ctx) for rule_id, fn in CONTEXT_VETOES.items() if rule_id not in disabled]
