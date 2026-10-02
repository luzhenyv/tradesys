"""档案加载：confirmed_at 过滤、proposed 跳过、多余键忽略、结构按类过期、人的回答。"""

from datetime import date

from tradesys.adapters.dossier import Dossier, load
from tradesys.adapters.fake import fake_snapshot, make_bars
from tradesys.adapters.yahoo import attach_dossier
from tradesys.models import Fact, Fundamental, Line, Snapshot, Zone
from tradesys.serialize import from_json, to_json
from tradesys.tools.structure import zone_broken_within

SAMPLE = """
ticker: X
idea:
  reason: 订单超预期
  source: news
  at: 2026-01-16
facts:
  v07.no_bad_news: {value: true, at: 2026-01-19}
  v09.tracked: {value: 6, at: 2026-01-02}
  later: {value: true, at: 2026-02-01}
  no_date: {value: true}
zones:
  - id: old
    kind: support
    low: 1
    high: 2
    confirmed_at: 2026-01-01
    strength: strong
    note: extra
  - id: future
    kind: support
    low: 3
    high: 4
    confirmed_at: 2026-06-01
  - id: draft
    kind: support
    low: 5
    high: 6
    confirmed_at: 2026-01-01
    status: proposed
lines:
  - id: t1
    kind: trendline
    points: [[2026-01-02, 10], [2026-01-10, 12]]
    confirmed_at: 2026-01-15
absent:
  - {kind: flag, confirmed_at: 2026-01-01}
  - {kind: neckline, confirmed_at: 2026-06-01}
"""


def _load(tmp_path, text, session):
    (tmp_path / "X.yaml").write_text(text, encoding="utf-8")
    return load("X", session, root=tmp_path)


def test_load_filters_future_proposed_and_keeps_extra_keys(tmp_path):
    d = _load(tmp_path, SAMPLE, date(2026, 1, 20))
    assert d.absent == ("flag",)
    assert d.expired == ()
    assert d.zones == (Zone("old", "support", 1.0, 2.0),)
    assert d.lines == (
        Line("t1", "trendline", (date(2026, 1, 2), 10.0), (date(2026, 1, 10), 12.0)),
    )


def test_idea_and_facts_load_as_answers(tmp_path):
    d = _load(tmp_path, SAMPLE, date(2026, 1, 20))
    assert d.facts == {
        "v07.no_bad_news": Fact(True, date(2026, 1, 19)),
        "v09.tracked": Fact(6, date(2026, 1, 2)),
        "idea.reason": Fact("订单超预期", date(2026, 1, 16)),
        "idea.source": Fact("news", date(2026, 1, 16)),
    }  # later（晚于 session_date）与 no_date（无 at）不载入


def test_structure_group_expires_after_20_trading_days(tmp_path):
    # 01-01 → 02-03 为 21 个交易日（跳过 01-19 MLK）：zone 与 absent flag 整类过期
    # trendline 01-15 仍有效
    d = _load(tmp_path, SAMPLE, date(2026, 2, 3))
    assert d.expired == ("flag", "zone")
    assert d.zones == () and d.absent == ()
    assert len(d.lines) == 1


def test_one_stale_zone_expires_the_whole_group(tmp_path):
    text = """
zones:
  - {id: a, kind: support, low: 1, high: 2, confirmed_at: 2026-01-02}
  - {id: b, kind: support, low: 3, high: 4, confirmed_at: 2026-02-02}
"""
    d = _load(tmp_path, text, date(2026, 2, 4))
    assert d.expired == ("zone",) and d.zones == ()


def test_load_missing_file_is_empty(tmp_path):
    assert load("NOPE", date(2026, 1, 1), root=tmp_path) == Dossier()


def test_amd_dossier_respects_confirmed_at_and_expiry():
    d = load("AMD", date(2026, 9, 10))
    assert len(d.zones) == 5 and len(d.lines) == 1
    assert set(d.absent) == {"flag", "neckline"}
    assert d.exchange == "NMS"
    assert load("AMD", date(2026, 8, 1)) == Dossier(exchange="NMS")
    stale = load("AMD", date(2026, 10, 2))  # 08-20 确认，已超过 20 个交易日
    assert stale.expired == ("flag", "neckline", "trendline", "zone")
    assert stale.zones == () and stale.lines == () and stale.absent == ()


def test_expired_structure_asks_for_review():
    snap = fake_snapshot(make_bars([100.0, 101.0]), expired=("zone",))
    check = zone_broken_within(snap, kind="support", days=2)
    assert check.hit is None
    assert check.evidence == ("zone 已过期，请复核后更新 confirmed_at",)


def test_attach_dossier_tags_none_without_yaml():
    snap = attach_dossier(fake_snapshot(make_bars([100.0])))
    assert snap.zones == () and snap.lines == () and snap.facts == {}
    assert "structures=none" in snap.sources


def test_attach_dossier_carries_facts_and_expired(tmp_path):
    (tmp_path / "TEST.yaml").write_text(SAMPLE, encoding="utf-8")
    snap = attach_dossier(fake_snapshot(make_bars([100.0] * 30)), tmp_path)  # T = 2026-02-13
    assert snap.expired == ("flag", "zone")
    assert "expired=flag,zone" in snap.sources
    assert snap.facts["idea.reason"].value == "订单超预期"


def test_snapshot_with_facts_round_trips_through_json():
    snap = fake_snapshot(make_bars([100.0]), facts={"v09.tracked": Fact(6, date(2026, 1, 2))})
    assert from_json(Snapshot, to_json(snap)) == snap


def test_yaml_exchange_fills_historical_fundamental(tmp_path):
    # 复审 M3：历史 as_of 不取基本面，人工确认的交易所代码让 V10 主板检查可判定
    (tmp_path / "TEST.yaml").write_text("exchange: NMS\n", encoding="utf-8")
    snap = attach_dossier(fake_snapshot(make_bars([100.0])), tmp_path)
    assert snap.fundamental == Fundamental(None, "NMS", None)
    assert "exchange=yaml" in snap.sources


def test_yahoo_exchange_wins_over_yaml(tmp_path):
    (tmp_path / "TEST.yaml").write_text("exchange: PNK\n", encoding="utf-8")
    snap = fake_snapshot(make_bars([100.0]), fundamental=Fundamental(1e11, "NYQ", None))
    assert attach_dossier(snap, tmp_path).fundamental.exchange == "NYQ"
