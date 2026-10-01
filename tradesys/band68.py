"""P-BAND68 · EP189：ATM straddle 推算 68% 波动区间。"""

from tradesys.models import Band68, Chain


def band68(close: float, chain: Chain, max_strike_gap_pct: float) -> Band68 | None:
    """close 必须是常规时段收盘价；只用 Ask。无法计算时返回 None（→ UNAVAILABLE）。"""
    strikes = {q.strike for q in chain.quotes}
    if not strikes:
        return None
    k = min(strikes, key=lambda s: abs(s - close))
    if abs(k - close) / close > max_strike_gap_pct:
        return None

    asks = {q.kind: q.ask for q in chain.quotes if q.strike == k}
    if "call" not in asks or "put" not in asks:
        return None

    x = asks["call"] + asks["put"]
    # K > C → X' = X − (K − C)；K < C → X' = X + (C − K)，两者合并为同一式
    x_adj = x - (k - close)
    return Band68(low=close - x_adj, high=close + x_adj, strike=k, expiry=chain.expiry)
