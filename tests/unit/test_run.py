"""执行器：规则来自 playbook，代码只提供工具。

EP301 的案例全部通过真实 playbook（playbooks/technical.md）运行。
"""

from datetime import datetime
from pathlib import Path

from tradesys.adapters.fake import fake_snapshot, make_bars
from tradesys.calendar_utils import make_snapshot
from tradesys.models import Candidate, RuleStatus
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
    assert {r.rule_id for r in run(PLAYBOOK, SNAP)}.isdisjoint({"V05", "V14"})


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
    assert rules["V02"].blocks == ()
    assert len(rules["V14"].blocks) == 2
