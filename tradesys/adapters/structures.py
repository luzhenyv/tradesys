"""人工确认的结构：data/structures/<TICKER>.yaml → Zone / Line。

只加载 confirmed_at ≤ session_date、且 status 不是 proposed 的条目。
strength / note / source 等多余键忽略，供人阅读与将来提案器用。
"""

from datetime import date, datetime
from pathlib import Path

import yaml

from tradesys.models import Line, Zone

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data" / "structures"


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


def load(
    ticker: str, session_date: date, root: Path = DEFAULT_ROOT
) -> tuple[tuple[Zone, ...], tuple[Line, ...]]:
    """读 YAML；文件不存在时返回空。"""
    path = Path(root) / f"{ticker}.yaml"
    if not path.is_file():
        return (), ()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    zones, lines = [], []
    for raw in data.get("zones") or []:
        if _skip(raw, session_date):
            continue
        zones.append(Zone(str(raw["id"]), raw["kind"], float(raw["low"]), float(raw["high"])))
    for raw in data.get("lines") or []:
        if _skip(raw, session_date):
            continue
        (d1, v1), (d2, v2) = raw["points"]
        lines.append(
            Line(str(raw["id"]), raw["kind"], (_as_date(d1), float(v1)), (_as_date(d2), float(v2)))
        )
    return tuple(zones), tuple(lines)
