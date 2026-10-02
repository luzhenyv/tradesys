"""执行器：规则来自 playbook，代码只提供工具。

EP301 的案例全部通过真实 playbook（playbooks/technical.md）运行。
"""

from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from tradesys.adapters.fake import fake_snapshot, make_bars, trading_days
from tradesys.calendar_utils import make_snapshot
from tradesys.models import Candidate, Fundamental, Line, RuleStatus, Zone
from tradesys.run import parse, run

PLAYBOOK = Path(__file__).parents[2] / "playbooks" / "technical.md"
PRIOR_20 = [100.0] + [101.0] * 19  # 前 20 日收盘最低 100
SNAP = fake_snapshot(make_bars(PRIOR_20 + [105.0]))


def _rows(out):
    return out.results if hasattr(out, "results") else out


def _status(results, rule_id, candidate_id=None):
    (r,) = [r for r in _rows(results) if r.rule_id == rule_id and r.candidate_id == candidate_id]
    return r.status


def _cand(entry, stop, target=None, cid="c1"):
    return Candidate(cid, "S01", entry, stop, target, grade="B")


# ---------- 真实 playbook 上的 EP 案例 ----------


def test_v01_close_below_20d_low_vetoes():
    snap = fake_snapshot(make_bars(PRIOR_20 + [99.5]))
    assert _status(run(PLAYBOOK, snap), "V01") == RuleStatus.VETO


def test_v01_close_above_20d_low_passes():
    snap = fake_snapshot(make_bars(PRIOR_20 + [100.2]))
    assert _status(run(PLAYBOOK, snap), "V01") == RuleStatus.PASS


def test_v05_ep301_entry119_stop100_vetoes_and_entry109_passes():
    results = run(PLAYBOOK, SNAP, (_cand(119, 100, cid="a"), _cand(109, 100, cid="b")))
    assert _status(results, "V05", "a") == RuleStatus.VETO
    assert _status(results, "V05", "b") == RuleStatus.PASS


def test_v05_no_stop_vetoes():
    assert _status(run(PLAYBOOK, SNAP, (_cand(109, None),)), "V05", "c1") == RuleStatus.VETO


def test_v14_ep301_entry125_stop100_target142_vetoes():
    assert _status(run(PLAYBOOK, SNAP, (_cand(125, 100, 142),)), "V14", "c1") == RuleStatus.VETO


def test_v14_rr_between_1_and_1_5_warns():
    assert _status(run(PLAYBOOK, SNAP, (_cand(100, 90, 112),)), "V14", "c1") == RuleStatus.WARN


def test_v14_rr_at_least_1_5_passes():
    assert _status(run(PLAYBOOK, SNAP, (_cand(100, 90, 115),)), "V14", "c1") == RuleStatus.PASS


def test_v14_no_target_is_manual():
    assert _status(run(PLAYBOOK, SNAP, (_cand(100, 90),)), "V14", "c1") == RuleStatus.MANUAL


def test_v11_shrinking_new_high_vetoes():
    snap = fake_snapshot(make_bars([float(x) for x in range(80, 101)], [1e6] * 20 + [5e5]))
    assert _status(run(PLAYBOOK, snap), "V11") == RuleStatus.VETO


def test_manual_rules_need_no_code():
    results = run(PLAYBOOK, SNAP).results
    assert {r.rule_id for r in results if r.status == RuleStatus.MANUAL} >= {"V06", "V08", "V09"}


def test_candidate_rules_skip_without_candidates():
    assert {r.rule_id for r in run(PLAYBOOK, SNAP).results}.isdisjoint({"V05", "V12", "V13", "V14"})


def test_intraday_as_of_uses_previous_session():
    bars = make_bars(PRIOR_20 + [101.0, 99.5])
    last = bars.last.d
    snap = make_snapshot(bars, datetime(last.year, last.month, last.day, 10, 30))
    assert snap.bars.last.close == 101.0
    assert _status(run(PLAYBOOK, snap), "V01") == RuleStatus.PASS


# ---------- 规则驱动代码：只改 playbook，结果随之改变 ----------

RULE = """
### X01 收盘价创 {n} 日新低
```rule
kind: veto
when:
  - new_low: {{n: {n}}}
```
"""


def test_changing_playbook_threshold_changes_result(tmp_path):
    snap = fake_snapshot(make_bars([90.0] + [101.0] * 10 + [99.5]))  # 11 日新低，非 20 日新低
    for n, expected in ((10, RuleStatus.VETO), (20, RuleStatus.PASS)):
        path = tmp_path / f"p{n}.md"
        path.write_text(RULE.format(n=n), encoding="utf-8")
        assert _status(run(path, snap), "X01") == expected


BLOCKS = """
### X02 未知后仍可命中
```rule
kind: veto
when:
  - days_to_earnings: {max: 5}
```

```rule
kind: warn
when:
  - new_low: {n: 3}
```

### X03 只有未知
```rule
kind: veto
when:
  - days_to_earnings: {max: 5}
```

```rule
kind: warn
when:
  - new_high: {n: 3}
```

### X04 提醒
```rule
kind: advice
say: 固定提醒
```

### X05 占位
```rule
kind: todo
ask: 待实现
```
"""


def test_unknown_block_does_not_stop_later_blocks(tmp_path):
    path = tmp_path / "p.md"
    path.write_text(BLOCKS, encoding="utf-8")
    snap = fake_snapshot(make_bars([100.0, 101.0, 102.0, 99.0]))  # 无财报日；3 日新低
    rows = {r.rule_id: r for r in run(path, snap).results}
    assert rows["X02"].status == RuleStatus.WARN
    assert rows["X03"].status == RuleStatus.UNAVAILABLE
    assert rows["X03"].trust == "decide"
    assert rows["X03"].evidence == ("缺少财报日期",)
    assert (rows["X04"].status, rows["X04"].trust, rows["X04"].evidence) == (
        RuleStatus.WARN,
        "memo",
        ("固定提醒",),
    )
    assert (rows["X05"].status, rows["X05"].kind) == (RuleStatus.MANUAL, "todo")


def test_v07_uptrend_without_earnings_is_pass():
    # Kleene：趋势向上已可判定 False，缺财报日不改变结论（review #6）
    prior = [100.0 + i for i in range(29)]
    snap = fake_snapshot(make_bars(prior + [prior[-1] * 0.96], [1e6] * 29 + [2e6]))
    assert _status(run(PLAYBOOK, snap), "V07") == RuleStatus.PASS


def test_duplicate_candidate_id_is_rejected():
    with pytest.raises(ValueError, match="候选 id 重复"):
        run(PLAYBOOK, SNAP, (_cand(109, 100, cid="x"), _cand(108, 100, cid="x")))


def test_parse_keeps_rules_without_blocks_as_unimplemented():
    rules = {r.id: r for r in parse(PLAYBOOK.read_text(encoding="utf-8"))}
    assert len(rules["S01"].blocks) == 2
    assert len(rules["V02"].blocks) == 1
    assert len(rules["V03"].blocks) == 3
    assert len(rules["V04"].blocks) == 2
    assert len(rules["V10"].blocks) == 2
    assert len(rules["V14"].blocks) == 2
    assert len(rules["V16"].blocks) == 1
    assert len(rules["S05"].blocks) == 2


def _weekdays_after(d, n):
    cur = d
    added = 0
    while added < n:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            added += 1
    return cur


def test_v04_up_day_with_shrinking_volume_vetoes():
    snap = fake_snapshot(make_bars([100.0] * 6 + [101.0], [1e6] * 6 + [5e5]))
    assert _status(run(PLAYBOOK, snap), "V04") == RuleStatus.VETO


def test_v04_five_day_rise_with_declining_volume_vetoes():
    # T 日收跌，条件 1 不成立；相对 T-5 仍上涨，量能逐日萎缩且 MA5 拐头
    closes = [100.0, 101.0, 102.0, 103.0, 106.0, 105.0]
    vols = [100.0, 90.0, 80.0, 70.0, 60.0, 50.0]
    assert _status(run(PLAYBOOK, fake_snapshot(make_bars(closes, vols))), "V04") == RuleStatus.VETO


def test_v04_expanding_drop_passes():
    closes = [105.0, 104.0, 103.0, 102.0, 101.0, 100.0]
    vols = [1e6] * 5 + [2e6]
    assert _status(run(PLAYBOOK, fake_snapshot(make_bars(closes, vols))), "V04") == RuleStatus.PASS


def test_v07_downtrend_earnings_drop_and_expand_vetoes():
    prior = [130.0 - 0.4 * i for i in range(29)]
    bars = make_bars(prior + [prior[-1] * 0.96], [1e6] * 29 + [2e6])
    snap = fake_snapshot(bars, next_earnings=_weekdays_after(bars.last.d, 2))
    results = run(PLAYBOOK, snap)
    r = next(x for x in results.results if x.rule_id == "V07")
    assert r.status == RuleStatus.VETO
    assert r.review
    assert "请确认无明显利空消息" in r.evidence


def test_v07_no_earnings_is_unavailable():
    prior = [130.0 - 0.4 * i for i in range(29)]
    snap = fake_snapshot(make_bars(prior + [prior[-1] * 0.96], [1e6] * 29 + [2e6]))
    assert _status(run(PLAYBOOK, snap), "V07") == RuleStatus.UNAVAILABLE


def test_v07_uptrend_passes():
    prior = [100.0 + i for i in range(29)]
    bars = make_bars(prior + [prior[-1] * 0.96], [1e6] * 29 + [2e6])
    snap = fake_snapshot(bars, next_earnings=_weekdays_after(bars.last.d, 2))
    assert _status(run(PLAYBOOK, snap), "V07") == RuleStatus.PASS


def test_v10_otc_vetoes():
    snap = fake_snapshot(
        make_bars(PRIOR_20 + [105.0]),
        fundamental=Fundamental(1e11, "PNK", None),
    )
    assert _status(run(PLAYBOOK, snap), "V10") == RuleStatus.VETO


def test_v10_small_cap_on_nyse_warns():
    snap = fake_snapshot(
        make_bars(PRIOR_20 + [105.0]),
        fundamental=Fundamental(3e9, "NYQ", None),
    )
    assert _status(run(PLAYBOOK, snap), "V10") == RuleStatus.WARN


def test_v10_large_cap_on_nasdaq_passes():
    snap = fake_snapshot(
        make_bars(PRIOR_20 + [105.0]),
        fundamental=Fundamental(1e11, "NMS", None),
    )
    assert _status(run(PLAYBOOK, snap), "V10") == RuleStatus.PASS


def test_v10b_social_heat_asked_even_when_small_cap_warns():
    snap = fake_snapshot(
        make_bars(PRIOR_20 + [105.0]),
        fundamental=Fundamental(3e9, "NYQ", None),
    )
    out = run(PLAYBOOK, snap)
    assert _status(out, "V10") == RuleStatus.WARN
    assert _status(out, "V10b") == RuleStatus.MANUAL


def test_v10_missing_fundamental_is_unavailable():
    assert _status(run(PLAYBOOK, SNAP), "V10") == RuleStatus.UNAVAILABLE


def test_v15_rsi6_above_90_vetoes():
    snap = fake_snapshot(make_bars([100.0 + i for i in range(30)]))
    assert _status(run(PLAYBOOK, snap), "V15") == RuleStatus.VETO


def test_v15_rsi6_not_overbought_passes():
    snap = fake_snapshot(make_bars([130.0 - i for i in range(30)]))
    assert _status(run(PLAYBOOK, snap), "V15") == RuleStatus.PASS


def test_v02_ep272_support_broken_yesterday_vetoes():
    snap = fake_snapshot(
        make_bars([125.0] * 5 + [99.0, 98.0]),
        zones=(Zone("z-100-120", "support", 100.0, 120.0),),
    )
    assert _status(run(PLAYBOOK, snap), "V02") == RuleStatus.VETO


def test_v02_no_zones_is_manual():
    assert _status(run(PLAYBOOK, SNAP), "V02") == RuleStatus.MANUAL


def test_v02_intact_support_passes():
    snap = fake_snapshot(
        make_bars([125.0] * 7),
        zones=(Zone("z-100-120", "support", 100.0, 120.0),),
    )
    assert _status(run(PLAYBOOK, snap), "V02") == RuleStatus.PASS


def test_v03_uptrend_close_below_vetoes():
    from tradesys.adapters.fake import trading_days

    days = trading_days(date(2026, 1, 5), 10)
    line = Line("up", "trendline", (days[0], 90.0), (days[4], 94.0))
    snap = fake_snapshot(make_bars([100.0] * 8 + [70.0, 70.0]), lines=(line,))
    assert _status(run(PLAYBOOK, snap), "V03") == RuleStatus.VETO


def test_v12_entry_far_from_support_vetoes():
    snap = fake_snapshot(
        make_bars([125.0] * 7),
        zones=(Zone("z-100-120", "support", 100.0, 120.0),),
    )
    assert _status(run(PLAYBOOK, snap, (_cand(140, 119),)), "V12", "c1") == RuleStatus.VETO


def test_v12_entry_near_support_passes():
    snap = fake_snapshot(
        make_bars([125.0] * 7),
        zones=(Zone("z-100-120", "support", 100.0, 120.0),),
    )
    assert _status(run(PLAYBOOK, snap, (_cand(125, 100),)), "V12", "c1") == RuleStatus.PASS


def test_v12_no_zones_is_manual():
    assert _status(run(PLAYBOOK, SNAP, (_cand(125, 100),)), "V12", "c1") == RuleStatus.MANUAL


def test_v12_broken_support_leaves_entry_hanging():
    snap = fake_snapshot(
        make_bars([125.0] * 5 + [90.0]),
        zones=(Zone("z-100-120", "support", 100.0, 120.0),),
    )
    assert _status(run(PLAYBOOK, snap, (_cand(90, 80),)), "V12", "c1") == RuleStatus.VETO


def test_v13_ep301_gap_into_next_resistance_vetoes():
    snap = fake_snapshot(
        make_bars([75.0] * 8 + [99.0]),
        zones=(
            Zone("r1", "resistance", 80.0, 90.0),
            Zone("r2", "resistance", 100.0, 110.0),
        ),
    )
    assert _status(run(PLAYBOOK, snap, (_cand(99, 90),)), "V13", "c1") == RuleStatus.VETO


def test_v13_room_to_next_resistance_passes():
    snap = fake_snapshot(
        make_bars([75.0] * 8 + [99.0]),
        zones=(
            Zone("r1", "resistance", 80.0, 90.0),
            Zone("r2", "resistance", 120.0, 130.0),
        ),
    )
    assert _status(run(PLAYBOOK, snap, (_cand(99, 90),)), "V13", "c1") == RuleStatus.PASS


def test_v03_fib618_recent_break_vetoes():
    closes = [100.0 + i for i in range(59)] + [119.0]
    assert _status(run(PLAYBOOK, fake_snapshot(make_bars(closes))), "V03") == RuleStatus.VETO


def test_s05_first_red_pullback_to_ma5_emits_candidate():
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 104.0]
    snap = fake_snapshot(make_bars(closes, lows=[*closes[:-1], 103.0]))
    out = run(PLAYBOOK, snap)
    (cand,) = [c for c in out.candidates if c.setup_id == "S05"]
    assert cand.entry == 104.0
    assert cand.stop == pytest.approx(103.0 * 0.99)
    assert _status(out, "S05") == RuleStatus.PASS


def test_s06_dry_then_engulfing_emits_candidate():
    prior = [130.0 - i for i in range(28)]
    opens = prior + [103.0, 97.0]
    highs = prior + [103.0, 104.0]
    lows = prior + [98.0, 97.0]
    closes = prior + [99.0, 104.0]
    vols = [1e6] * 28 + [4e5, 2e6]
    snap = fake_snapshot(make_bars(closes, vols, opens=opens, highs=highs, lows=lows))
    out = run(PLAYBOOK, snap)
    (cand,) = [c for c in out.candidates if c.setup_id == "S06"]
    assert cand.entry == 104.0
    assert cand.grade == "B"
    assert _status(out, "S06") == RuleStatus.PASS


def test_s07_hammer_after_shrinking_new_low():
    prior = [130.0 - i for i in range(29)]  # 130..102
    closes = prior + [100.0]
    opens = prior + [101.0]
    highs = prior + [101.0]
    lows = prior + [96.0]
    vols = [1e6] * 28 + [5e5, 2e6]
    snap = fake_snapshot(make_bars(closes, vols, opens=opens, highs=highs, lows=lows))
    out = run(PLAYBOOK, snap)
    (cand,) = [c for c in out.candidates if c.setup_id == "S07"]
    assert cand.grade == "C"
    assert cand.stop == pytest.approx(96.0 * 0.99)
    assert _status(out, "S07") == RuleStatus.PASS
    assert _status(out, "V01") == RuleStatus.VETO


def test_v16_top_divergence_in_overbought_vetoes():
    # 长上涨把 RSI-6 顶到 100，再做一个更高的第二高点但中间深回落压低 RSI
    up = [100.0 + i for i in range(40)]
    pull = [up[-1] - 2 * i for i in range(1, 8)]
    # 第二峰略高于第一峰：第一峰 = up[-1]=139；回落后再抬
    rally = [pull[-1] + 3 * i for i in range(1, 10)]
    tail = [rally[-1] - 0.5, rally[-1] - 1.0]  # 右侧两根略低，RSI 仍 > 80
    closes = up + pull + rally + tail
    assert _status(run(PLAYBOOK, fake_snapshot(make_bars(closes))), "V16") == RuleStatus.VETO


def test_s01_s04_without_structure_are_manual():
    out = run(PLAYBOOK, SNAP)
    for sid in ("S01", "S02", "S03", "S04"):
        assert _status(out, sid) == RuleStatus.MANUAL


def test_s01_breakout_retest_emits_candidate():
    z = Zone("z-100-120", "resistance", 100.0, 120.0)
    n = 12
    closes = [110.0] * n + [125.0, 115.0]
    vols = [1e6] * n + [2e6, 3e6]
    opens = [110.0] * n + [125.0, 112.0]
    snap = fake_snapshot(
        make_bars(closes, vols, opens=opens, highs=closes, lows=opens),
        zones=(z,),
    )
    out = run(PLAYBOOK, snap)
    (c,) = [x for x in out.candidates if x.setup_id == "S01"]
    assert c.entry == 115.0
    assert c.stop == pytest.approx(99.0)


def test_s02_downtrend_break_retest_emits_candidate():
    days = trading_days(date(2026, 1, 5), 10)
    line = Line("dn", "trendline", (days[0], 104.0), (days[9], 100.0))
    closes = [90.0] * 7 + [105.0, 102.0, 101.5]
    vols = [1e6] * 7 + [2e6, 1e6, 5e5]
    snap = fake_snapshot(make_bars(closes, vols), lines=(line,))
    out = run(PLAYBOOK, snap)
    (c,) = [x for x in out.candidates if x.setup_id == "S02"]
    lv = line.value_at(snap.session_date)
    assert c.stop == pytest.approx(lv * 0.99)


def test_s04_neckline_retest_emits_candidate():
    days = trading_days(date(2026, 1, 5), 8)
    line = Line("nk", "neckline", (days[0], 100.0), (days[5], 100.0))
    closes = [90.0] * 5 + [105.0, 103.0, 101.0]
    lows = [90.0] * 5 + [105.0, 103.0, 99.0]
    vols = [1e6] * 5 + [2e6, 1e6, 1e6]
    snap = fake_snapshot(make_bars(closes, vols, lows=lows), lines=(line,))
    out = run(PLAYBOOK, snap)
    (c,) = [x for x in out.candidates if x.setup_id == "S04"]
    assert c.stop == pytest.approx(100.0 * 0.99)


def _flag_snap(history: int):
    """history 根平静期 → 10 根放量旗杆 → 9 根缩量旗面 → T 放量阳线越过 A 线。"""
    n = history + 20
    days = trading_days(date(2025, 1, 6), n)
    pole = Line("P", "flag_pole", (days[history], 80.0), (days[history + 9], 116.0))
    a = Line("A", "flag_upper", (days[history + 10], 120.0), (days[n - 1], 114.0))
    b = Line("B", "flag_lower", (days[history + 10], 108.0), (days[n - 1], 102.0))
    # 平静期前段高价，使「全年最低到全年最高」与人画旗杆不同
    calm = [150.0] * (history - 20) + [80.0] * 20
    closes = calm + [80.0 + 4 * i for i in range(10)] + [110.0] * 9 + [116.0]
    vols = [5e5] * history + [2e6] * 10 + [6e5] * 9 + [2e6]
    opens = closes[:-1] + [111.0]  # T 阳线
    snap = fake_snapshot(
        make_bars(closes, vols, start=days[0], opens=opens, highs=closes, lows=opens),
        lines=(pole, a, b),
    )
    assert closes[-1] > a.value_at(snap.session_date)
    return snap


def test_s03_flag_break_emits_candidate():
    out = run(PLAYBOOK, _flag_snap(20))
    (c,) = [x for x in out.candidates if x.setup_id == "S03"]
    assert c.target == 116.0  # 人画旗杆顶
    assert c.stop == pytest.approx(102.0 * 0.99)


def test_s03_pole_from_yaml_on_400_bar_history():
    # review #3：yfinance 取 400 日历天 ≈ 250 根；旗杆不得退化为「全年」
    out = run(PLAYBOOK, _flag_snap(230))
    (c,) = [x for x in out.candidates if x.setup_id == "S03"]
    assert c.target == 116.0
    assert _status(out, "S03") == RuleStatus.PASS


def test_s03_without_pole_is_manual_and_absent_flag_is_not_applicable():
    snap = _flag_snap(20)
    no_pole = replace(snap, lines=tuple(ln for ln in snap.lines if ln.kind != "flag_pole"))
    assert _status(run(PLAYBOOK, no_pole), "S03") == RuleStatus.MANUAL
    declared = replace(no_pole, absent=("flag",))
    out = run(PLAYBOOK, declared)
    assert _status(out, "S03") == RuleStatus.PASS
    assert not any(c.setup_id == "S03" for c in out.candidates)


def test_v03_no_lines_is_manual():
    # review #5：无趋势线 / 颈线且未声明不存在 → 不可判定，不能静默落到 Fib 得 PASS
    assert _status(run(PLAYBOOK, SNAP), "V03") == RuleStatus.MANUAL


def test_v03_absent_lines_falls_through_to_fib():
    snap = replace(SNAP, absent=("trendline", "neckline"))
    assert _status(run(PLAYBOOK, snap), "V03") == RuleStatus.PASS


def test_s09_without_pattern_passes():
    assert _status(run(PLAYBOOK, SNAP), "S09") == RuleStatus.PASS
    assert not any(c.setup_id == "S09" for c in run(PLAYBOOK, SNAP).candidates)
