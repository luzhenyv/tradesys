"""工具的纯函数部分：P-VOL、P-NEWLOW / P-NEWHIGH。"""

import pytest

from tradesys.adapters.fake import fake_snapshot, make_bars
from tradesys.models import Fundamental
from tradesys.tools.listing import days_to_earnings, exchange_not_in, market_cap_below
from tradesys.tools.price import close_up, drop_pct, extreme, new_low
from tradesys.tools.rsi import rsi, rsi_above
from tradesys.tools.trend import classify as trend_classify
from tradesys.tools.volume import (
    classify,
    volume_declining,
    volume_ma5_turning_down,
    volume_ratios,
    volume_state,
)

BASE = (100.0,) * 6


def _state(vols: tuple[float, ...]) -> str:
    return classify(*volume_ratios(vols), shrink=1.0, expand=1.0)


def test_vol_both_lower_is_shrink():
    assert _state(BASE + (80.0,)) == "shrink"


def test_vol_both_higher_is_expand():
    assert _state(BASE + (150.0,)) == "expand"


def test_vol_mixed_is_neutral():
    # 高于前一日（50）但低于 MA5（90）
    assert _state((100.0,) * 5 + (50.0, 70.0)) == "neutral"


def test_vol_insufficient_history_is_neutral():
    assert _state((100.0, 50.0)) == "neutral"


def test_volume_state_tool_reports_both_ratios():
    snap = fake_snapshot(make_bars([10.0] * 7, list(BASE + (80.0,))))
    c = volume_state(snap, state="shrink")
    assert c.hit and c.evidence[:2] == ("vs_prev=0.8", "vs_ma5=0.8")


def test_new_low_reports_actual_k():
    closes = (130.0, 120.0) + (110.0,) * 25 + (105.0,)
    assert extreme(closes, 20, low=True) == (True, 27)


def test_new_low_equal_close_is_not_new_low():
    assert extreme((100.0,) * 21, 20, low=True) == (False, 0)


def test_new_high_mirror():
    assert extreme(tuple(float(x) for x in range(1, 22)), 20, low=False) == (True, 20)


def test_new_low_tool_evidence_has_k():
    c = new_low(fake_snapshot(make_bars([101.0] * 20 + [99.0])), n=20)
    assert c.hit and "收盘价为 20 日新低" in c.evidence


def test_close_up_compares_against_n_days_ago():
    snap = fake_snapshot(make_bars([100.0, 101.0, 102.0, 101.5]))
    assert close_up(snap, n=1).hit is False
    assert close_up(snap, n=3).hit is True


def test_drop_pct_hits_at_threshold():
    snap = fake_snapshot(make_bars([100.0, 97.0]))
    assert drop_pct(snap, min=0.03).hit is True
    assert drop_pct(snap, min=0.04).hit is False


def test_volume_declining_needs_strict_decrease():
    snap = fake_snapshot(make_bars([1.0] * 5, [50.0, 40.0, 30.0, 20.0, 10.0]))
    assert volume_declining(snap, n=5).hit
    assert not volume_declining(
        fake_snapshot(make_bars([1.0] * 5, [50.0, 40.0, 40.0, 20.0, 10.0])), n=5
    ).hit


def test_volume_ma5_turning_down_includes_today():
    # MA5[T]=(90+80+70+60+50)/5=70 < MA5[T-1]=(100+90+80+70+60)/5=80
    snap = fake_snapshot(make_bars([1.0] * 6, [100.0, 90.0, 80.0, 70.0, 60.0, 50.0]))
    assert volume_ma5_turning_down(snap).hit


def test_rsi_all_gains_is_100_all_losses_is_0():
    assert rsi(tuple(float(x) for x in range(10, 20)), 6) == 100.0
    assert rsi(tuple(float(x) for x in range(20, 10, -1)), 6) == 0.0
    assert rsi((10.0, 11.0), 6) is None


def test_rsi_wilder_smoothing_matches_hand_calc():
    # period=2: closes 10,12,11,13 → seed RSI 66.67, then 85.71
    assert rsi((10.0, 12.0, 11.0, 13.0), 2) == pytest.approx(100.0 - 100.0 / 7.0)
    from tradesys.tools.rsi import rsi_series

    series = rsi_series((10.0, 12.0, 11.0, 13.0), 2)
    assert series[-1] == rsi((10.0, 12.0, 11.0, 13.0), 2)
    assert series[1] is None and series[2] == pytest.approx(100.0 - 100.0 / 3.0)


def test_rsi_above_missing_history():
    c = rsi_above(fake_snapshot(make_bars([100.0] * 6)), period=6, x=90)
    assert c.hit is None and c.missing


def test_trend_down_when_close_and_ma20_falling():
    closes = tuple(130.0 - i for i in range(30))
    assert trend_classify(closes) == "down"
    assert trend_classify(tuple(100.0 + i for i in range(30))) == "up"
    assert trend_classify((100.0,) * 10) is None


def test_listing_tools_missing_data():
    snap = fake_snapshot(make_bars([100.0] * 5))
    assert days_to_earnings(snap, max=2).missing
    assert exchange_not_in(snap, codes=["NYQ"]).missing
    assert market_cap_below(snap, usd=5e9).missing


def test_listing_tools_hit_on_otc_and_small_cap():
    snap = fake_snapshot(make_bars([100.0] * 5), fundamental=Fundamental(1e9, "PNK", None))
    assert exchange_not_in(snap, codes=["NYQ", "NMS"]).hit
    assert market_cap_below(snap, usd=5e9).hit
