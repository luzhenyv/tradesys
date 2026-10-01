"""engine 端到端：fake 数据 → 上下文 → context vetoes。"""

from datetime import datetime

from tradesys.adapters.fake import FakeMarket, make_bars
from tradesys.config import Config, VetoConfig
from tradesys.engine import build_context, run_context_vetoes
from tradesys.models import RuleStatus

# 最后一根 bar 为新低；倒数第二根不是
BARS = make_bars([100.0 + i for i in range(20)] + [118.0, 90.0])


def _ctx(as_of: datetime, config: Config | None = None):
    return build_context("TEST", as_of, FakeMarket(BARS), config or Config())


def test_intraday_as_of_uses_previous_session():
    last = BARS.last.d
    ctx = _ctx(datetime(last.year, last.month, last.day, 10, 30))
    assert ctx.session_date == BARS.items[-2].d
    assert ctx.bars.last.close == 118.0


def test_after_close_runs_v01_veto():
    last = BARS.last.d
    ctx = _ctx(datetime(last.year, last.month, last.day, 16, 30))
    results = run_context_vetoes(ctx)
    assert [(r.rule_id, r.status) for r in results] == [("V01", RuleStatus.VETO)]
    assert ctx.data_sources == {"market": "fake"}


def test_disabled_veto_is_skipped():
    last = BARS.last.d
    config = Config(veto=VetoConfig(disabled=("V01",)))
    ctx = _ctx(datetime(last.year, last.month, last.day, 16, 30), config)
    assert run_context_vetoes(ctx) == []
