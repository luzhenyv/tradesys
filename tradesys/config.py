"""config.yaml 的加载与校验。键的含义见 rules_spec §6。"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class VetoConfig(_Frozen):
    min_rr: float = 1.0
    preferred_rr: float = 1.5
    max_stop_pct: float = 0.10
    disabled: tuple[str, ...] = ()


class UniverseConfig(_Frozen):
    min_market_cap: float = 5.0e9


class RecentConfig(_Frozen):
    lookback_days: int = 20
    break_days: int = 2


class VolumeConfig(_Frozen):
    shrink_ratio: float = 1.0
    expand_ratio: float = 1.0


class RsiConfig(_Frozen):
    periods: tuple[int, int] = (6, 24)


class StopConfig(_Frozen):
    buffer_pct: float = 0.01


class Band68Config(_Frozen):
    max_strike_gap_pct: float = 0.02
    expiry: str = "monthly"


class SwingConfig(_Frozen):
    k: int = 2


class DivergenceConfig(_Frozen):
    max_gap_days: int = 30


class CandleConfig(_Frozen):
    short_shadow_ratio: float = 0.1


class V07Config(_Frozen):
    earnings_window_days: int = 2
    min_drop_pct: float = 0.03


class V08Config(_Frozen):
    cooldown_days: int = 5


class V12Config(_Frozen):
    max_distance_pct: float = 0.10


class V13Config(_Frozen):
    min_room_pct: float = 0.02


class V15Config(_Frozen):
    rsi_fast_max: float = 90


class V16Config(_Frozen):
    rsi_overbought: float = 80


class LookbackConfig(_Frozen):
    lookback_days: int = 20


class S02Config(LookbackConfig):
    near_line_pct: float = 0.03


class S04Config(LookbackConfig):
    touch_pct: float = 0.02


class S05Config(_Frozen):
    min_streak: int = 5


class S06Config(_Frozen):
    dry_ratio: float = 0.6


class S09Config(_Frozen):
    rsi_oversold: float = 20


class Config(_Frozen):
    """字段顺序与 config.yaml、rules_spec §6 一致。"""

    veto: VetoConfig = VetoConfig()
    universe: UniverseConfig = UniverseConfig()
    recent: RecentConfig = RecentConfig()
    volume: VolumeConfig = VolumeConfig()
    rsi: RsiConfig = RsiConfig()
    stop: StopConfig = StopConfig()
    band68: Band68Config = Band68Config()
    swing: SwingConfig = SwingConfig()
    divergence: DivergenceConfig = DivergenceConfig()
    candle: CandleConfig = CandleConfig()
    v07: V07Config = V07Config()
    v08: V08Config = V08Config()
    v12: V12Config = V12Config()
    v13: V13Config = V13Config()
    v15: V15Config = V15Config()
    v16: V16Config = V16Config()
    s01: LookbackConfig = LookbackConfig()
    s02: S02Config = S02Config()
    s04: S04Config = S04Config()
    s05: S05Config = S05Config()
    s06: S06Config = S06Config()
    s09: S09Config = S09Config()


def load_config(path: str | Path) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return Config.model_validate(data)
