"""候选买点的风险度量 · EP301§R05、§R14。scope: candidate 的工具。"""

from tradesys.models import Candidate, Check, Snapshot


def stop_wider_than(snap: Snapshot, candidate: Candidate, pct: float) -> Check:
    """止损无法确定，或止损幅度 (entry − stop) / entry 超过 pct。"""
    if candidate.stop is None:
        return Check(True, ("止损无法确定",))
    width = (candidate.entry - candidate.stop) / candidate.entry
    evidence = (f"entry={candidate.entry}", f"stop={candidate.stop}", f"止损幅度={width:.1%}")
    return Check(width > pct, evidence)


def rr_below(snap: Snapshot, candidate: Candidate, x: float) -> Check:
    """盈亏比 (target − entry) / (entry − stop) 低于 x；缺止损或目标时无法判断。"""
    rr = candidate.rr
    if rr is None:
        return Check(None, ("缺少止损或目标，请人工设定",))
    evidence = (f"entry={candidate.entry}", f"stop={candidate.stop}", f"target={candidate.target}")
    return Check(rr < x, (*evidence, f"rr={rr:.2f}"))
