"""yahoo adapter：转换函数用手工 DataFrame 测试；真实取数标记为 network。"""

from datetime import date, datetime

import pandas as pd
import pytest

from tradesys.adapters.yahoo import (
    bars_from_history,
    chain_from_frames,
    fetch_snapshot,
    pick_expiry,
)
from tradesys.calendar_utils import ET
from tradesys.run import run
from tradesys.tools.band68 import band68_range


def _history(rows):
    idx = pd.DatetimeIndex([r[0] for r in rows], tz=ET)
    cols = ["Open", "High", "Low", "Close", "Volume"]
    return pd.DataFrame([r[1:] for r in rows], index=idx, columns=cols)


def test_bars_from_history_converts_and_drops_nan_close():
    df = _history(
        [
            ("2026-09-29", 725.0, 740.4, 720.0, 735.0, 1.2e7),
            ("2026-09-30", 730.2, 738.2, 726.0, float("nan"), 0.0),
            ("2026-10-01", 728.5, 735.8, 722.1, 731.6, 9.8e6),
        ]
    )
    bars = bars_from_history("AMD", df)
    assert [b.d for b in bars.items] == [date(2026, 9, 29), date(2026, 10, 1)]
    assert bars.last.close == 731.6 and isinstance(bars.last.volume, float)


def test_pick_expiry_monthly_is_next_third_friday_after_session():
    expiries = ("2026-10-02", "2026-10-09", "2026-10-16", "2026-11-20")
    assert pick_expiry(expiries, date(2026, 10, 1)) == date(2026, 10, 16)
    assert pick_expiry(expiries, date(2026, 10, 16)) == date(2026, 11, 20)


def test_pick_expiry_weekly_is_next_expiry():
    assert pick_expiry(("2026-10-02", "2026-10-09"), date(2026, 10, 1), "weekly") == date(
        2026, 10, 2
    )


def test_chain_keeps_strikes_near_close_and_feeds_band68():
    calls = pd.DataFrame(
        {"strike": [100.0, 165.0, 300.0], "bid": [0, 6.1, 0], "ask": [70, 6.30, 0]}
    )
    puts = pd.DataFrame(
        {"strike": [100.0, 165.0, 300.0], "bid": [0, 5.8, 0], "ask": [0, 6.00, 140]}
    )
    as_of = datetime(2026, 4, 12, 17, 0)
    chain = chain_from_frames("TSLA", date(2026, 4, 17), as_of, calls, puts, close=164.9)
    assert {q.strike for q in chain.quotes} == {165.0}

    from tradesys.adapters.fake import fake_snapshot, make_bars

    snap = fake_snapshot(make_bars([164.9]), chain=chain)
    assert band68_range(snap).evidence[0] == "Band68=[152.7, 177.1]"  # EP189 TSLA


def test_fetch_rejects_future_as_of_before_any_network_call():
    now = datetime(2026, 10, 1, 11, 0, tzinfo=ET)
    with pytest.raises(ValueError, match="晚于当前时间"):
        fetch_snapshot("AMD", datetime(2026, 10, 1, 17, 0, tzinfo=ET), now=now)
    with pytest.raises(ValueError, match="晚于当前时间"):
        # naive 视为 UTC（17:00 UTC = 13:00 EDT > 11:00 EDT）
        fetch_snapshot("AMD", datetime(2026, 10, 1, 17, 0), now=now)


@pytest.mark.network
def test_fetch_AMD_live_runs_through_playbook():
    snap = fetch_snapshot("AMD", datetime.now(ET))
    assert len(snap.bars.items) > 200
    assert snap.fundamental is not None and snap.fundamental.market_cap > 1e11
    results = run("playbooks/technical.md", snap).results
    assert {r.rule_id for r in results} >= {"V01", "V11"}


@pytest.mark.network
def test_fetch_past_as_of_has_no_present_only_data():
    snap = fetch_snapshot("AMD", datetime(2026, 9, 1, 17, 0, tzinfo=ET))
    assert snap.session_date == date(2026, 9, 1)
    assert (snap.fundamental, snap.next_earnings, snap.chain) == (None, None, None)


class _FakeTicker:
    """只实现 fetch_snapshot 用到的 yfinance 接口。"""

    def __init__(self, ticker):
        self.info = {"marketCap": 1e12, "exchange": "NMS", "sector": "Tech"}
        self.calendar = {"Earnings Date": [date(2026, 10, 28)]}
        self.options = ("2026-10-16",)

    def history(self, start, end, auto_adjust):
        return _history(
            [("2026-10-01", 100, 101, 99, 100, 1e6), ("2026-10-02", 100, 103, 99, 102, 1e6)]
        )

    def option_chain(self, expiry):
        calls = pd.DataFrame({"strike": [102.0], "bid": [0.0], "ask": [3.0]})
        puts = pd.DataFrame({"strike": [102.0], "bid": [0.0], "ask": [3.0]})
        return type("OC", (), {"calls": calls, "puts": puts})()


def test_band68_fetched_at_0100_et_next_day(monkeypatch):
    # review #8：上海 13:00 = 美东 01:00，新交易时段尚未开盘，期权报价仍是 10-02 收盘后的
    import tradesys.adapters.yahoo as yahoo

    monkeypatch.setattr(yahoo.yf, "Ticker", _FakeTicker)
    monkeypatch.setattr(yahoo, "attach_dossier", lambda s: s)
    now = datetime(2026, 10, 3, 1, 0, tzinfo=ET)
    snap = fetch_snapshot("X", now, now=now)
    assert snap.session_date == date(2026, 10, 2)
    assert snap.chain is not None and snap.chain.expiry == date(2026, 10, 16)
    assert band68_range(snap).evidence[0] == "Band68=[96.0, 108.0]"


def test_no_chain_once_next_session_opened(monkeypatch):
    import tradesys.adapters.yahoo as yahoo

    monkeypatch.setattr(yahoo.yf, "Ticker", _FakeTicker)
    monkeypatch.setattr(yahoo, "attach_dossier", lambda s: s)
    now = datetime(2026, 10, 5, 9, 45, tzinfo=ET)  # 周一开盘后，as_of 取周一盘中
    snap = fetch_snapshot("X", now, now=now)
    assert snap.session_date == date(2026, 10, 2)
    assert snap.chain is None
