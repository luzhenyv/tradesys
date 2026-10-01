"""工具的纯函数部分：P-VOL、P-NEWLOW / P-NEWHIGH。"""

from tradesys.adapters.fake import fake_snapshot, make_bars
from tradesys.tools.price import extreme, new_low
from tradesys.tools.volume import classify, volume_ratios, volume_state

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
