"""V05 · EP301§R05：止损无法确定或幅度超出承受力，不买。"""

from tradesys.models import AnalysisContext, Candidate, RuleResult, RuleStatus

ID = "V05"


def evaluate(ctx: AnalysisContext, candidate: Candidate) -> RuleResult:
    cid = candidate.id
    if candidate.stop is None:
        return RuleResult(ID, RuleStatus.VETO, "止损无法确定", candidate_id=cid)

    limit = ctx.config.veto.max_stop_pct
    pct = (candidate.entry - candidate.stop) / candidate.entry
    evidence = (f"entry={candidate.entry}", f"stop={candidate.stop}", f"止损幅度={pct:.1%}")
    if pct > limit:
        return RuleResult(ID, RuleStatus.VETO, f"止损幅度超过 {limit:.0%}", evidence, cid)
    return RuleResult(ID, RuleStatus.PASS, f"止损幅度在 {limit:.0%} 以内", evidence, cid)
