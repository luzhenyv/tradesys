"""yfinance 取数（DESIGN §7）：唯一的网络 I/O，输出 Snapshot。

as_of 约束：日线可以回溯；基本面、财报日、期权链只有"现在"的数据，
因此只在 as_of 为今天时获取，否则留空（依赖它们的规则得到 UNAVAILABLE）。
期权链还要求 session_date 收盘后尚无新的常规时段开盘，使 Band68 的收盘价与期权报价属于同一交易日
（如上海 13:00 = 美东 01:00 仍可取前一日收盘后的报价）。
pandas 只在本文件内出现，立即转换为 dataclass。
"""

from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import yfinance as yf

from tradesys.adapters.dossier import DEFAULT_ROOT
from tradesys.adapters.dossier import load as load_dossier
from tradesys.calendar_utils import (
    is_monthly_opex,
    make_snapshot,
    now_utc,
    session_open_since,
    to_et,
)
from tradesys.models import Bar, Bars, Chain, Fundamental, OptionQuote, Snapshot

HISTORY_DAYS = 400
STRIKE_WINDOW = 0.10  # 只保留收盘价 ±10% 的行权价；Band68 只用最近一档


def bars_from_history(ticker: str, df) -> Bars:
    """yfinance history（auto_adjust=False）→ Bars。丢弃缺收盘价的行。"""
    rows = (r for r in df.itertuples() if r.Close == r.Close)  # NaN != NaN
    return Bars(
        ticker,
        tuple(
            Bar(
                r.Index.date(),
                float(r.Open),
                float(r.High),
                float(r.Low),
                float(r.Close),
                float(r.Volume),
            )
            for r in rows
        ),
    )


def pick_expiry(expiries: tuple[str, ...], after: date, kind: str = "monthly") -> date | None:
    """session_date 之后最近的到期日；monthly 只取每月第三个周五。"""
    days = [date.fromisoformat(e) for e in expiries]
    return min(
        (d for d in days if d > after and (kind == "weekly" or is_monthly_opex(d))), default=None
    )


def chain_from_frames(
    ticker: str, expiry: date, as_of: datetime, calls, puts, close: float
) -> Chain:
    """option_chain 的 calls / puts → Chain，只保留 close ±STRIKE_WINDOW 的行权价。"""
    lo, hi = close * (1 - STRIKE_WINDOW), close * (1 + STRIKE_WINDOW)
    quotes = tuple(
        OptionQuote(float(r.strike), kind, float(r.bid), float(r.ask))
        for kind, df in (("call", calls), ("put", puts))
        for r in df.itertuples()
        if lo <= r.strike <= hi
    )
    return Chain(ticker, expiry, as_of, quotes)


def fetch_snapshot(
    ticker: str, as_of: datetime, expiry: str = "monthly", now: datetime | None = None
) -> Snapshot:
    current = to_et(now or now_utc())
    local = to_et(as_of)
    if local > current:
        raise ValueError(f"as_of {as_of} 晚于当前时间，会把未收盘的日线当作已收盘")
    t = yf.Ticker(ticker)
    end = local.date() + timedelta(days=1)  # history 的 end 不含当天；使用美东交易日
    history = t.history(
        start=local.date() - timedelta(days=HISTORY_DAYS), end=end, auto_adjust=False
    )
    bars = bars_from_history(ticker, history)
    session = make_snapshot(bars, as_of).session_date

    if local.date() != current.date():
        return attach_dossier(
            make_snapshot(bars, as_of, sources=("market=yahoo", "其余=none（as_of 不是今天）"))
        )

    info = t.info
    fundamental = Fundamental(info.get("marketCap"), info.get("exchange"), info.get("sector"))
    earnings = min(
        (d for d in (t.calendar or {}).get("Earnings Date", []) if d >= session), default=None
    )
    chain, options = None, "options=none（已有新的交易时段）"
    if not session_open_since(session, current) and (
        exp := pick_expiry(t.options, session, expiry)
    ):
        oc = t.option_chain(exp.isoformat())
        chain = chain_from_frames(
            ticker, exp, as_of, oc.calls, oc.puts, bars.upto(session).last.close
        )
        options = f"options=yahoo（{exp}）"
    return attach_dossier(
        make_snapshot(
            bars,
            as_of,
            fundamental=fundamental,
            next_earnings=earnings,
            chain=chain,
            sources=("market=yahoo", "fundamental=yahoo", options),
        )
    )


def attach_dossier(snap: Snapshot, root: Path = DEFAULT_ROOT) -> Snapshot:
    """把档案中 as_of 可见的结构与回答挂到 Snapshot 上；缺交易所代码时用档案的 exchange。"""
    st = load_dossier(snap.ticker, snap.session_date, root)
    tags = ["structures=yaml" if st.zones or st.lines or st.absent else "structures=none"]
    tags += [f"expired={','.join(st.expired)}"] if st.expired else []
    fund = snap.fundamental
    if st.exchange and (fund is None or fund.exchange is None):
        fund = replace(fund or Fundamental(None, None, None), exchange=st.exchange)
        tags.append("exchange=yaml")
    return replace(
        snap,
        zones=st.zones,
        lines=st.lines,
        absent=st.absent,
        expired=st.expired,
        facts=st.facts,
        fundamental=fund,
        sources=(*snap.sources, *tags),
    )
