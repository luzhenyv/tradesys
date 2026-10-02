"""人工回答 · docs/WORKFLOW.md §2：读 Snapshot.facts。缺失或过期 → None，即向人提问。"""

from datetime import date, datetime

from tradesys.calendar_utils import trading_days_between
from tradesys.models import Check, Fact, Snapshot


def fresh(snap: Snapshot, key: str, ttl: int | None) -> tuple[Fact | None, str]:
    """有效的回答与说明；ttl 为交易日数（回答日到 T 少于 ttl 才有效），省略则不过期。"""
    f = snap.facts.get(key)
    if f is None:
        return None, f"请回答 {key}"
    if ttl is not None and trading_days_between(f.at, snap.session_date) >= ttl:
        return None, f"{key} 已过期（{f.at}），请重新回答"
    return f, f"{key}={f.value}（{f.at}）"


def _day(value: object, recorded: date) -> date | None:
    if value is True:
        return recorded
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _within(snap: Snapshot, key: str, f: Fact, n: int) -> Check:
    """value 为日期（true 用 at；false 表示没有）距 T 是否不足 n 个交易日。"""
    if f.value is False:
        return Check(False, (f"{key}=false",))
    day = _day(f.value, f.at)
    if day is None:
        return Check(None, (f"{key} 应为日期或 false，请重新回答",))
    if day > snap.session_date:
        return Check(False, (f"{key}={day}（晚于 T）",))
    days = trading_days_between(day, snap.session_date)
    return Check(days < n, (f"{key}={day}（{days} 个交易日前）",))


def fact(
    snap: Snapshot,
    key: str,
    ttl: int | None = None,
    min: float | None = None,
    max: float | None = None,
    within: int | None = None,
    **cond,
) -> Check:
    """`is` 相等；`min` / `max` 数字；`within` 日期距 T 的交易日数；无条件 = 已回答 → False。"""
    if set(cond) - {"is"}:
        raise TypeError(f"fact 不认识参数 {sorted(set(cond) - {'is'})}")
    f, note = fresh(snap, key, ttl)
    if f is None:
        return Check(None, (note,))
    if within is not None:
        return _within(snap, key, f, within)
    if "is" in cond:
        return Check(f.value == cond["is"], (note,))
    if min is None and max is None:
        return Check(False, (note,))
    if isinstance(f.value, bool) or not isinstance(f.value, int | float):
        return Check(None, (f"{key} 应为数字，请重新回答",))
    hit = (min is None or f.value >= min) and (max is None or f.value <= max)
    return Check(hit, (note,))


def checklist(snap: Snapshot, keys: list[str], min: int, ttl: int | None = None) -> Check:
    """一组是 / 否回答中为「是」的项数是否少于 min；任一项缺失或过期 → 列出待回答的项。"""
    answers = {k: fresh(snap, k, ttl) for k in keys}
    todo = [note for f, note in answers.values() if f is None]
    if todo:
        return Check(None, tuple(todo))
    unmet = [k for k, (f, _) in answers.items() if f.value is not True]
    yes = len(keys) - len(unmet)
    evidence = (f"{yes}/{len(keys)} 项满足（至少 {min}）", *(f"未满足 {k}" for k in unmet))
    return Check(yes < min, evidence)
