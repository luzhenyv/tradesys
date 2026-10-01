"""P-VOL、P-NEWLOW / P-NEWHIGH。"""

from pathlib import Path

from tradesys.adapters.fake import make_bars
from tradesys.config import Config, VolumeConfig, load_config
from tradesys.features.price import new_high, new_low
from tradesys.features.volume import volume

CFG = VolumeConfig()
BASE = [100.0] * 6


def _last_state(vols: list[float]) -> str:
    return volume(make_bars([10.0] * len(vols), vols), CFG).state[-1]


def test_vol_both_lower_is_shrink():
    assert _last_state(BASE + [80.0]) == "shrink"


def test_vol_both_higher_is_expand():
    assert _last_state(BASE + [150.0]) == "expand"


def test_vol_mixed_is_neutral():
    # 高于前一日（50）但低于 MA5（90）
    assert _last_state([100.0] * 5 + [50.0, 70.0]) == "neutral"


def test_vol_insufficient_history_is_neutral():
    assert _last_state([100.0, 50.0]) == "neutral"


def test_new_low_reports_actual_k():
    closes = (130.0, 120.0) + (110.0,) * 25 + (105.0,)
    assert new_low(closes, 20) == (True, 27)


def test_new_low_equal_close_is_not_new_low():
    assert new_low((100.0,) * 21, 20) == (False, 0)


def test_new_high_mirror():
    assert new_high(tuple(range(1, 22)), 20) == (True, 20)


def test_config_yaml_matches_defaults():
    path = Path(__file__).parents[2] / "config" / "config.yaml"
    assert load_config(path) == Config()
