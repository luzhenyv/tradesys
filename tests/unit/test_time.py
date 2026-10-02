"""系统时间统一管理单元测试：UTC 统一、时区转换与美东交易日映射。"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from tradesys.adapters.fake import fake_snapshot, make_bars
from tradesys.calendar_utils import (
    ET,
    is_monthly_opex,
    make_snapshot,
    now_utc,
    parse_as_of,
    session_date,
    session_open_since,
    to_et,
    to_utc,
    trading_days_between,
)
from tradesys.serialize import from_json, to_json


def test_to_utc_naive_treated_as_utc():
    dt = datetime(2026, 9, 30, 17, 0)
    utc_dt = to_utc(dt)
    assert utc_dt.tzinfo == UTC
    assert (utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour) == (2026, 9, 30, 17)


def test_to_utc_aware_converts_properly():
    shanghai = ZoneInfo("Asia/Shanghai")
    dt = datetime(2026, 10, 1, 1, 0, tzinfo=shanghai)  # 01:00 CST = 17:00 UTC (9/30)
    utc_dt = to_utc(dt)
    assert utc_dt.tzinfo == UTC
    assert (utc_dt.year, utc_dt.month, utc_dt.day, utc_dt.hour) == (2026, 9, 30, 17)


def test_to_et_from_utc_and_dst():
    # 2026-07-01 为夏令时（EDT, UTC-4）
    edt_utc = datetime(2026, 7, 1, 20, 0, tzinfo=UTC)
    assert to_et(edt_utc).hour == 16
    assert to_et(edt_utc).date() == date(2026, 7, 1)

    # 2026-01-15 为冬令时（EST, UTC-5）
    est_utc = datetime(2026, 1, 15, 21, 0, tzinfo=UTC)
    assert to_et(est_utc).hour == 16
    assert to_et(est_utc).date() == date(2026, 1, 15)


def test_parse_as_of_none_returns_now_utc():
    t = parse_as_of(None)
    assert t.tzinfo == UTC
    assert abs((t - now_utc()).total_seconds()) < 2.0


def test_parse_as_of_default_utc():
    t = parse_as_of("2026-09-30T17:00")
    assert t == datetime(2026, 9, 30, 17, 0, tzinfo=UTC)


def test_parse_as_of_with_shanghai_tz():
    # 上海时间 2026-10-01 01:00 (UTC+8) -> UTC 2026-09-30 17:00
    t = parse_as_of("2026-10-01T01:00", tz="Asia/Shanghai")
    assert t == datetime(2026, 9, 30, 17, 0, tzinfo=UTC)


def test_parse_as_of_with_tokyo_tz():
    # 东京时间 2026-10-01 02:00 (UTC+9) -> UTC 2026-09-30 17:00
    t = parse_as_of("2026-10-01T02:00", tz="Asia/Tokyo")
    assert t == datetime(2026, 9, 30, 17, 0, tzinfo=UTC)


def test_parse_as_of_with_explicit_offset_takes_precedence():
    # 字符串自带 +08:00，即便 tz 参数传了 Asia/Tokyo 也不受影响
    t = parse_as_of("2026-10-01T01:00+08:00", tz="Asia/Tokyo")
    assert t == datetime(2026, 9, 30, 17, 0, tzinfo=UTC)


def test_parse_as_of_with_z_suffix():
    t = parse_as_of("2026-09-30T17:00Z")
    assert t == datetime(2026, 9, 30, 17, 0, tzinfo=UTC)


def test_parse_as_of_invalid_tz_raises_value_error():
    with pytest.raises(ValueError, match="未知时区"):
        parse_as_of("2026-09-30T17:00", tz="Invalid/Zone_Name")


def test_trading_days_between_counts_open_interval():
    friday, monday, tuesday = date(2026, 1, 9), date(2026, 1, 12), date(2026, 1, 13)
    assert trading_days_between(friday, friday) == 0
    assert trading_days_between(friday, monday) == 1
    assert trading_days_between(friday, tuesday) == 2
    assert trading_days_between(monday, friday) == -1


def test_trading_days_between_skips_holidays():
    # 2026-07-03（7/4 周六补休）休市：周四 → 下周一只隔 1 个交易日
    assert trading_days_between(date(2026, 7, 2), date(2026, 7, 6)) == 1


def test_good_friday_opex_moves_to_thursday():
    # 2025-04-18 是第三个周五也是 Good Friday，月度交割提前到 04-17
    assert is_monthly_opex(date(2025, 4, 17))
    assert not is_monthly_opex(date(2025, 4, 18))
    assert is_monthly_opex(date(2026, 4, 17))
    assert not is_monthly_opex(date(2026, 4, 16))


def test_session_open_since_crosses_weekend_and_holiday():
    fri = date(2026, 10, 2)
    assert not session_open_since(fri, datetime(2026, 10, 3, 1, 0, tzinfo=ET))
    assert not session_open_since(fri, datetime(2026, 10, 5, 9, 29, tzinfo=ET))
    assert session_open_since(fri, datetime(2026, 10, 5, 9, 30, tzinfo=ET))
    # 2026-09-04 周五 → 09-07 劳动节休市 → 09-08 才开盘
    assert not session_open_since(date(2026, 9, 4), datetime(2026, 9, 7, 12, 0, tzinfo=ET))


def test_session_date_with_shanghai_user_time():
    # 2026-09-29 至 2026-10-01 日线
    bars = make_bars([100.0, 101.0, 102.0], start=date(2026, 9, 29))
    # 2026-09-29, 2026-09-30, 2026-10-01

    # 用户在上海：2026-10-02 05:00 (CST) -> UTC 2026-10-01 21:00 -> EDT 2026-10-01 17:00
    # 美东 17:00 已收盘，session_date 应为 2026-10-01
    as_of = parse_as_of("2026-10-02T05:00", tz="Asia/Shanghai")
    assert session_date(bars, as_of) == date(2026, 10, 1)

    # 用户在上海：2026-10-01 22:00 (CST) -> UTC 2026-10-01 14:00 -> EDT 2026-10-01 10:00
    # 美东 10:00 属于盘中（未收盘），session_date 应回溯至前一交易日 2026-09-30
    as_of_intraday = parse_as_of("2026-10-01T22:00", tz="Asia/Shanghai")
    assert session_date(bars, as_of_intraday) == date(2026, 9, 30)


def test_make_snapshot_guarantees_utc_as_of():
    bars = make_bars([100.0, 101.0], start=date(2026, 9, 29))
    # 传入美东时间的 aware datetime
    et_dt = datetime(2026, 9, 30, 17, 0, tzinfo=ET)
    snap = make_snapshot(bars, et_dt)
    assert snap.as_of.tzinfo == UTC
    assert snap.as_of == datetime(2026, 9, 30, 21, 0, tzinfo=UTC)


def test_snapshot_roundtrip_preserves_utc_and_timezone_aware():
    bars = make_bars([100.0, 101.0], start=date(2026, 9, 29))
    snap = fake_snapshot(bars)
    assert snap.as_of.tzinfo == UTC

    json_str = to_json(snap)
    assert "+00:00" in json_str or "Z" in json_str

    from tradesys.models import Snapshot

    restored = from_json(Snapshot, json_str)
    assert restored.as_of.tzinfo == UTC
    assert restored.as_of == snap.as_of


def test_cli_fetch_time_options(monkeypatch):
    from typer.testing import CliRunner

    from tradesys.cli import app

    recorded = {}

    def fake_fetch_snapshot(ticker, when, expiry):
        recorded["ticker"] = ticker
        recorded["when"] = when
        bars = make_bars([100.0])
        return make_snapshot(bars, when)

    monkeypatch.setattr("tradesys.adapters.yahoo.fetch_snapshot", fake_fetch_snapshot)

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["fetch", "META", "--as-of", "2026-10-01T17:00", "--tz", "Asia/Shanghai"],
    )
    assert result.exit_code == 0
    # 2026-10-01 17:00 CST -> 2026-10-01 09:00 UTC
    assert recorded["when"] == datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
