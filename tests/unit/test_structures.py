"""YAML 结构加载：confirmed_at 过滤、proposed 跳过、多余键忽略。"""

from datetime import date

from tradesys.adapters.fake import fake_snapshot, make_bars
from tradesys.adapters.structures import Structures, load
from tradesys.adapters.yahoo import attach_structures
from tradesys.models import Fundamental, Line, Zone

SAMPLE = """
ticker: X
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


def test_load_filters_future_proposed_and_keeps_extra_keys(tmp_path):
    (tmp_path / "X.yaml").write_text(SAMPLE, encoding="utf-8")
    st = load("X", date(2026, 3, 1), root=tmp_path)
    zones, lines = st.zones, st.lines
    assert st.absent == ("flag",)
    assert st.confirmed == date(2026, 1, 15)
    assert zones == (Zone("old", "support", 1.0, 2.0),)
    assert lines == (Line("t1", "trendline", (date(2026, 1, 2), 10.0), (date(2026, 1, 10), 12.0)),)


def test_load_missing_file_is_empty(tmp_path):
    assert load("NOPE", date(2026, 1, 1), root=tmp_path) == Structures()


def test_amd_example_yaml_respects_confirmed_at():
    st = load("AMD", date(2026, 10, 2))
    assert len(st.zones) == 5 and len(st.lines) == 1
    assert set(st.absent) == {"flag", "neckline"}
    assert st.exchange == "NMS"
    assert load("AMD", date(2026, 8, 1)) == Structures(exchange="NMS")


def test_attach_structures_tags_none_without_yaml():
    snap = attach_structures(fake_snapshot(make_bars([100.0])))
    assert snap.zones == () and snap.lines == ()
    assert "structures=none" in snap.sources


def test_yaml_exchange_fills_historical_fundamental(tmp_path):
    # 复审 M3：历史 as_of 不取基本面，人工确认的交易所代码让 V10 主板检查可判定
    (tmp_path / "TEST.yaml").write_text("exchange: NMS\n", encoding="utf-8")
    snap = attach_structures(fake_snapshot(make_bars([100.0])), tmp_path)
    assert snap.fundamental == Fundamental(None, "NMS", None)
    assert "exchange=yaml" in snap.sources


def test_yahoo_exchange_wins_over_yaml(tmp_path):
    (tmp_path / "TEST.yaml").write_text("exchange: PNK\n", encoding="utf-8")
    snap = fake_snapshot(make_bars([100.0]), fundamental=Fundamental(1e11, "NYQ", None))
    assert attach_structures(snap, tmp_path).fundamental.exchange == "NYQ"
