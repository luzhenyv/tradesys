"""人工回答工具：fact / checklist。T = 2026-01-09（周五）。"""

from datetime import date

import pytest

from tradesys.adapters.fake import fake_snapshot, make_bars
from tradesys.models import Fact, RuleStatus
from tradesys.run import run
from tradesys.tools.answer import checklist, fact

T = date(2026, 1, 9)
KEYS = [f"k{i}" for i in range(9)]


def _snap(**facts):
    snap = fake_snapshot(make_bars([100.0] * 5), facts=facts)
    assert snap.session_date == T
    return snap


def test_missing_answer_asks():
    c = fact(_snap(), "v07.no_bad_news", ttl=1, **{"is": False})
    assert (c.hit, c.missing, c.evidence) == (None, False, ("请回答 v07.no_bad_news",))


def test_ttl_1_is_valid_only_for_t_and_the_morning_after():
    same_day = _snap(k=Fact(True, T))
    next_morning = _snap(k=Fact(True, date(2026, 1, 10)))  # 周六补写，判断的仍是 T
    day_before = _snap(k=Fact(True, date(2026, 1, 8)))
    assert fact(same_day, "k", ttl=1, **{"is": True}).hit is True
    assert fact(next_morning, "k", ttl=1, **{"is": True}).hit is True
    stale = fact(day_before, "k", ttl=1, **{"is": True})
    assert (stale.hit, stale.evidence) == (None, ("k 已过期（2026-01-08），请重新回答",))


def test_without_ttl_answer_never_expires():
    assert fact(_snap(k=Fact(True, date(2025, 1, 2))), "k", **{"is": True}).hit is True


def test_numeric_thresholds():
    snap = _snap(months=Fact(6, T), text=Fact("abc", T), flag=Fact(True, T))
    assert fact(snap, "months", min=3).hit is True
    assert fact(snap, "months", max=3).hit is False
    assert fact(snap, "months", min=3, max=5).hit is False
    assert fact(snap, "text", min=3).hit is None
    assert fact(snap, "flag", min=1).hit is None  # 布尔不当数字


def test_without_condition_only_requires_an_answer():
    # I01 写下想法理由：有回答 → 无可否决；没有 → 提问
    assert fact(_snap(**{"idea.reason": Fact("订单", T)}), "idea.reason").hit is False
    assert fact(_snap(), "idea.reason").hit is None


def test_unknown_condition_is_an_error():
    with pytest.raises(TypeError):
        fact(_snap(k=Fact(True, T)), "k", iss=True)


def test_within_uses_stop_date_not_daily_bool():
    # T=2026-01-09 周五；within 5：不足 5 个交易日 → True
    assert fact(_snap(k=Fact("2026-01-05", T)), "k", within=5).hit is True  # 4 日前
    assert fact(_snap(k=Fact("2026-01-02", T)), "k", within=5).hit is False  # 5 日前
    assert fact(_snap(k=Fact(False, T)), "k", within=5).hit is False
    assert fact(_snap(k=Fact(True, date(2026, 1, 6))), "k", within=5).hit is True  # true → at
    assert fact(_snap(), "k", within=5).hit is None
    bad = fact(_snap(k=Fact("soon", T)), "k", within=5)
    assert (bad.hit, bad.evidence) == (None, ("k 应为日期或 false，请重新回答",))


def test_checklist_lists_missing_items():
    c = checklist(_snap(k0=Fact(True, T)), KEYS[:3], min=2, ttl=63)
    assert c.hit is None
    assert c.evidence == ("请回答 k1", "请回答 k2")


def test_v09_checklist_6_of_9_vetoes_and_7_of_9_passes():
    six = {k: Fact(i < 6, T) for i, k in enumerate(KEYS)}
    seven = {k: Fact(i < 7, T) for i, k in enumerate(KEYS)}
    c = checklist(_snap(**six), KEYS, min=7, ttl=63)
    assert c.hit is True
    assert c.evidence[0] == "6/9 项满足（至少 7）"
    assert checklist(_snap(**seven), KEYS, min=7, ttl=63).hit is False


def test_is_works_inside_a_rule_block(tmp_path):
    # `is` 是 Python 关键字：rule 块里的 YAML 键经 **kwargs 传入
    path = tmp_path / "p.md"
    path.write_text(
        "### X01 测试\n```rule\nkind: veto\nwhen:\n  - fact: {key: k, is: false, ttl: 1}\n```\n",
        encoding="utf-8",
    )
    (r,) = run(path, _snap(k=Fact(False, T))).results
    assert r.status == RuleStatus.VETO
    (r,) = run(path, _snap()).results
    assert (r.status, r.evidence) == (RuleStatus.MANUAL, ("请回答 k",))
