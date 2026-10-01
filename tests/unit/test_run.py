"""执行器：规则来自 playbook，代码只提供工具。

EP301 的案例全部通过真实 playbook（playbooks/technical.md）运行。
"""

from datetime import date, datetime, timedelta
from pathlib import Path

from tradesys.adapters.fake import fake_snapshot, make_bars
from tradesys.calendar_utils import make_snapshot
from tradesys.models import Candidate, Fundamental, Line, RuleStatus, Zone
from tradesys.run import parse, run

PLAYBOOK = Path(__file__).parents[2] / "playbooks" / "technical.md"
PRIOR_20 = [100.0] + [101.0] * 19  # 前 20 日收盘最低 100
SNAP = fake_snapshot(make_bars(PRIOR_20 + [105.0]))


def _status(results, rule_id, candidate_id=None):
    (r,) = [r for r in results if r.rule_id == rule_id and r.candidate_id == candidate_id]
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
    results = run(PLAYBOOK, SNAP)
    assert {r.rule_id for r in results if r.status == RuleStatus.MANUAL} >= {"V06", "V08", "V09"}


def test_candidate_rules_skip_without_candidates():
    assert {r.rule_id for r in run(PLAYBOOK, SNAP)}.isdisjoint({"V05", "V12", "V13", "V14"})


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


def test_parse_keeps_rules_without_blocks_as_unimplemented():
    rules = {r.id: r for r in parse(PLAYBOOK.read_text(encoding="utf-8"))}
    assert rules["V16"].blocks == ()
    assert len(rules["V02"].blocks) == 1
    assert len(rules["V03"].blocks) == 2
    assert len(rules["V04"].blocks) == 2
    assert len(rules["V10"].blocks) == 3
    assert len(rules["V14"].blocks) == 2


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
    r = next(x for x in results if x.rule_id == "V07")
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


def test_v10_large_cap_on_nasdaq_is_manual():
    snap = fake_snapshot(
        make_bars(PRIOR_20 + [105.0]),
        fundamental=Fundamental(1e11, "NMS", None),
    )
    assert _status(run(PLAYBOOK, snap), "V10") == RuleStatus.MANUAL


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


def test_v03_no_lines_is_manual():
    assert _status(run(PLAYBOOK, SNAP), "V03") == RuleStatus.MANUAL


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
