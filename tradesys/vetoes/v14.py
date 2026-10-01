"""V14 · EP301§R14、EP302：盈亏比至少 1:1（否则否决），最好 1:1.5 以上（否则警告）。"""

from tradesys.models import AnalysisContext, Candidate, RuleResult, RuleStatus

ID = "V14"


def evaluate(ctx: AnalysisContext, candidate: Candidate) -> RuleResult:
    cid = candidate.id
    rr = candidate.rr
    if rr is None:
        return RuleResult(ID, RuleStatus.MANUAL, "缺少止损或目标，请人工设定", candidate_id=cid)

    cfg = ctx.config.veto
    evidence = (
        f"entry={candidate.entry}",
        f"stop={candidate.stop}",
        f"target={candidate.target}",
        f"rr={rr:.2f}",
    )
    if rr < cfg.min_rr:
        return RuleResult(ID, RuleStatus.VETO, f"盈亏比低于 1:{cfg.min_rr}", evidence, cid)
    if rr < cfg.preferred_rr:
        return RuleResult(ID, RuleStatus.WARN, f"盈亏比低于 1:{cfg.preferred_rr}", evidence, cid)
    return RuleResult(ID, RuleStatus.PASS, "盈亏比达标", evidence, cid)
