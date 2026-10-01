"""V01、V05、V14：rules_spec 中的 Test Case。"""

import pytest

from tradesys.adapters.fake import make_bars
from tradesys.models import Candidate, RuleStatus
from tradesys.vetoes import v01, v05, v14

PRIOR_20 = [100.0] + [101.0] * 19  # 前 20 日收盘最低 100


def _cand(entry, stop, target=None) -> Candidate:
    return Candidate("c1", "S01", entry, stop, target, grade="B")


@pytest.fixture
def ctx(make_ctx):
    return make_ctx(make_bars(PRIOR_20 + [105.0]))


def test_v01_close_below_20d_low_vetoes(make_ctx):
    assert v01.evaluate(make_ctx(make_bars(PRIOR_20 + [99.5]))).status == RuleStatus.VETO


def test_v01_close_above_20d_low_passes(make_ctx):
    assert v01.evaluate(make_ctx(make_bars(PRIOR_20 + [100.2]))).status == RuleStatus.PASS


def test_v05_ep301_entry119_stop100_vetoes(ctx):
    assert v05.evaluate(ctx, _cand(119, 100)).status == RuleStatus.VETO


def test_v05_ep301_entry109_stop100_passes(ctx):
    assert v05.evaluate(ctx, _cand(109, 100)).status == RuleStatus.PASS


def test_v05_no_stop_vetoes(ctx):
    assert v05.evaluate(ctx, _cand(109, None)).status == RuleStatus.VETO


def test_v14_ep301_entry125_stop100_target142_vetoes(ctx):
    assert v14.evaluate(ctx, _cand(125, 100, 142)).status == RuleStatus.VETO


def test_v14_rr_between_1_and_1_5_warns(ctx):
    assert v14.evaluate(ctx, _cand(100, 90, 112)).status == RuleStatus.WARN


def test_v14_rr_at_least_1_5_passes(ctx):
    assert v14.evaluate(ctx, _cand(100, 90, 115)).status == RuleStatus.PASS


def test_v14_no_target_is_manual(ctx):
    assert v14.evaluate(ctx, _cand(100, 90, None)).status == RuleStatus.MANUAL
