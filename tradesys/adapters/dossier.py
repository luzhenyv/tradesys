"""一只股票的档案：data/tickers/<TICKER>.yaml → 结构、absent、人的回答（规则见 DESIGN §8）。"""

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml

from tradesys.calendar_utils import add_trading_days, next_trading_day, trading_days_between
from tradesys.models import Candidate, Fact, Line, Zone

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data" / "tickers"
KEYS = ("zones", "lines", "absent")
STRUCTURE_TTL = 20  # 交易日；约一个月复核一次 watchlist


def _as_date(v: object) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def _fact_value(v: object) -> bool | float | str:
    """YAML 日期写成 ISO 文本，与 Fact.value 的类型一致。"""
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return v  # type: ignore[return-value]


def _skip(raw: dict, cutoff: date) -> bool:
    if raw.get("status") == "proposed" or "confirmed_at" not in raw:
        return True
    return _as_date(raw["confirmed_at"]) > cutoff


def _group(section: str, raw: dict) -> str:
    """结构所属的类，与 absent 的 kind 一致。"""
    if section == "zones":
        return "zone"
    kind = str(raw["kind"])
    return "flag" if kind.startswith("flag") else kind


def _facts(data: dict, cutoff: date) -> dict[str, Fact]:
    raw = {str(k): v for k, v in (data.get("facts") or {}).items()}
    idea = data.get("idea") or {}
    for f in ("reason", "source"):
        if idea.get(f):
            raw[f"idea.{f}"] = {"value": idea[f], "at": idea.get("at")}
    return {
        k: Fact(_fact_value(v["value"]), _as_date(v["at"]))
        for k, v in raw.items()
        if isinstance(v, dict) and "value" in v and v.get("at") is not None
        if _as_date(v["at"]) <= cutoff
    }


def _plans(data: dict, cutoff: date) -> tuple[Candidate, ...]:
    out = []
    for raw in data.get("plans") or []:
        if raw.get("status") == "cancelled" or "at" not in raw:
            continue
        at = _as_date(raw["at"])
        if at > cutoff:
            continue
        expires = _as_date(raw["expires"]) if raw.get("expires") else add_trading_days(at, 20)
        stop, target = raw.get("stop"), raw.get("target")
        out.append(
            Candidate(
                str(raw["id"]),
                "",
                float(raw["entry"]),
                None if stop is None else float(stop),
                None if target is None else float(target),
                "",
                expires=expires,
            )
        )
    return tuple(out)


@dataclass(frozen=True)
class Dossier:
    zones: tuple[Zone, ...] = ()
    lines: tuple[Line, ...] = ()
    absent: tuple[str, ...] = ()
    expired: tuple[str, ...] = ()  # 过期的结构类
    exchange: str | None = None  # 人工确认的交易所代码，供历史回放
    facts: dict[str, Fact] = field(default_factory=dict)
    plans: tuple[Candidate, ...] = ()


def load(ticker: str, session_date: date, root: Path = DEFAULT_ROOT) -> Dossier:
    """读档案；文件不存在时返回空。

    日期 ≤ T 的下一个交易日即可见：盘后到次日开盘前补写的结构与回答属于对 T 的判断。
    """
    path = Path(root) / f"{ticker}.yaml"
    if not path.is_file():
        return Dossier()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cutoff = next_trading_day(session_date)
    kept = {k: [r for r in data.get(k) or [] if not _skip(r, cutoff)] for k in KEYS}
    oldest: dict[str, date] = {}
    for k in KEYS:
        for r in kept[k]:
            g, d = _group(k, r), _as_date(r["confirmed_at"])
            oldest[g] = min(oldest.get(g, d), d)
    stale = (g for g, d in oldest.items() if trading_days_between(d, session_date) > STRUCTURE_TTL)
    expired = tuple(sorted(stale))
    kept = {k: [r for r in kept[k] if _group(k, r) not in expired] for k in KEYS}
    zones = tuple(
        Zone(str(r["id"]), r["kind"], float(r["low"]), float(r["high"])) for r in kept["zones"]
    )
    lines = tuple(
        Line(str(r["id"]), r["kind"], (_as_date(d1), float(v1)), (_as_date(d2), float(v2)))
        for r in kept["lines"]
        for (d1, v1), (d2, v2) in [r["points"]]
    )
    absent = tuple(str(r["kind"]) for r in kept["absent"])
    exchange = str(data["exchange"]) if data.get("exchange") else None
    return Dossier(
        zones, lines, absent, expired, exchange, _facts(data, cutoff), _plans(data, cutoff)
    )
