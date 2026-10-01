"""P-VOL · EP010、EP301§R04：同时与前一日、前 5 日均量比较。"""

from tradesys.config import VolumeConfig
from tradesys.models import Bars, VolumeResult, VolumeState


def volume(bars: Bars, cfg: VolumeConfig) -> VolumeResult:
    vols = bars.volumes
    vs_prev: list[float | None] = []
    vs_ma5: list[float | None] = []
    states: list[VolumeState] = []

    for i, v in enumerate(vols):
        prev = v / vols[i - 1] if i >= 1 and vols[i - 1] else None
        ma5_base = sum(vols[i - 5 : i]) / 5 if i >= 5 else 0.0
        ma5 = v / ma5_base if ma5_base else None
        vs_prev.append(prev)
        vs_ma5.append(ma5)
        states.append(_state(prev, ma5, cfg))

    return VolumeResult(tuple(vs_prev), tuple(vs_ma5), tuple(states))


def _state(prev: float | None, ma5: float | None, cfg: VolumeConfig) -> VolumeState:
    if prev is None or ma5 is None:
        return "neutral"
    if prev < cfg.shrink_ratio and ma5 < cfg.shrink_ratio:
        return "shrink"
    if prev > cfg.expand_ratio and ma5 > cfg.expand_ratio:
        return "expand"
    return "neutral"
