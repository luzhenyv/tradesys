"""P-BAND68 · EP189 案例。"""

from pytest import approx

from tradesys.adapters.fake import fake_snapshot, make_bars, make_chain
from tradesys.tools.band68 import band68, band68_range


def test_band68_ep189_tsla_strike_above_close():
    chain = make_chain([(162.5, 7.5, 5.0), (165.0, 6.30, 6.00)])
    assert band68(164.9, chain, max_strike_gap_pct=0.02) == (approx(152.7), approx(177.1))


def test_band68_ep189_nvda_strike_at_close():
    b = band68(880.0, make_chain([(880.0, 29.0, 27.1)]), max_strike_gap_pct=0.02)
    assert b == (approx(823.9), approx(936.1))


def test_band68_strike_below_close_widens_band():
    # K < C → X' = X + (C − K)：X = 4, C − K = 1 → X' = 5
    b = band68(101.0, make_chain([(100.0, 2.0, 2.0)]), max_strike_gap_pct=0.02)
    assert b == (approx(96.0), approx(106.0))


def test_band68_strike_gap_over_2pct_unavailable():
    assert band68(100.0, make_chain([(105.0, 3.0, 3.0)]), max_strike_gap_pct=0.02) is None


def test_band68_range_without_chain_is_missing():
    c = band68_range(fake_snapshot(make_bars([100.0] * 3)))
    assert (c.hit, c.missing) == (None, True)
