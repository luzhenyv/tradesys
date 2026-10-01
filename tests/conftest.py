from datetime import datetime

import pytest

from tradesys.adapters.fake import FakeMarket
from tradesys.config import Config
from tradesys.engine import build_context
from tradesys.models import AnalysisContext, Bars


@pytest.fixture
def make_ctx():
    """用 fake 数据在最后一根 bar 收盘后构建上下文。"""

    def _make(bars: Bars, config: Config | None = None) -> AnalysisContext:
        last = bars.last.d
        as_of = datetime(last.year, last.month, last.day, 17, 0)
        return build_context(bars.ticker, as_of, FakeMarket(bars), config or Config())

    return _make
