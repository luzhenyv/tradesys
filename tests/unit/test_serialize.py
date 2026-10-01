"""serialize：dataclass ⇄ JSON 往返不失真。"""

from datetime import date

from tradesys.adapters.fake import fake_snapshot, make_bars, make_chain
from tradesys.models import Candidate, Line, RuleResult, RuleStatus, Snapshot, Zone
from tradesys.serialize import from_json, to_json


def test_rule_result_roundtrip():
    r = RuleResult("V14", "盈亏比不足", RuleStatus.WARN, ("rr=1.20",), "c1", review=True)
    assert from_json(RuleResult, to_json(r)) == r


def test_candidate_roundtrip_keeps_none():
    c = Candidate("c1", "S05", 100.0, 92.0, None, "B", ("first red bar",))
    assert from_json(Candidate, to_json(c)) == c


def test_snapshot_roundtrip_with_all_inputs():
    snap = fake_snapshot(
        make_bars([10.0, 11.0, 12.0]),
        zones=(Zone("z1", "support", 9.0, 10.0),),
        lines=(Line("l1", "trendline", (date(2026, 1, 5), 9.0), (date(2026, 1, 7), 11.0)),),
        next_earnings=date(2026, 2, 1),
        chain=make_chain([(12.0, 0.5, 0.5)]),
    )
    assert from_json(Snapshot, to_json(snap)) == snap
