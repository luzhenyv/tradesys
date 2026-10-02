"""人工确认的结构：data/structures/<TICKER>.yaml → Zone / Line / absent。

只加载 confirmed_at ≤ session_date、且 status 不是 proposed 的条目。
absent 列出人已确认不存在的结构 kind（zone / trendline / neckline / flag），相关规则判为不适用。
顶层 exchange 为人工确认的交易所代码，只在取不到当天基本面时补上（历史回放）。
strength / note / source 等多余键忽略，供人阅读与将来提案器用。
"""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

from tradesys.models import Line, Zone

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data" / "structures"
KEYS = ("zones", "lines", "absent")


def _as_date(v: object) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def _skip(raw: dict, session_date: date) -> bool:
    if raw.get("status") == "proposed":
        return True
    if "confirmed_at" not in raw:
        return True
    return _as_date(raw["confirmed_at"]) > session_date


@dataclass(frozen=True)
class Structures:
    zones: tuple[Zone, ...] = ()
    lines: tuple[Line, ...] = ()
    absent: tuple[str, ...] = ()
    confirmed: date | None = None  # 已载入条目中最新的 confirmed_at
    exchange: str | None = None  # 人工确认的交易所代码，供历史回放（DESIGN §8）


def load(ticker: str, session_date: date, root: Path = DEFAULT_ROOT) -> Structures:
    """读 YAML；文件不存在时返回空。"""
    path = Path(root) / f"{ticker}.yaml"
    if not path.is_file():
        return Structures()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    kept = {k: [r for r in data.get(k) or [] if not _skip(r, session_date)] for k in KEYS}
    zones = tuple(
        Zone(str(r["id"]), r["kind"], float(r["low"]), float(r["high"])) for r in kept["zones"]
    )
    lines = tuple(
        Line(str(r["id"]), r["kind"], (_as_date(d1), float(v1)), (_as_date(d2), float(v2)))
        for r in kept["lines"]
        for (d1, v1), (d2, v2) in [r["points"]]
    )
    absent = tuple(str(r["kind"]) for r in kept["absent"])
    dates = [_as_date(r["confirmed_at"]) for k in KEYS for r in kept[k]]
    exchange = str(data["exchange"]) if data.get("exchange") else None
    return Structures(zones, lines, absent, max(dates, default=None), exchange)
