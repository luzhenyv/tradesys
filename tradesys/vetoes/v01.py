"""V01 · EP301§R01：收盘价创近期新低，不买。"""

from tradesys.features.price import new_low
from tradesys.models import AnalysisContext, RuleResult, RuleStatus

ID = "V01"


def evaluate(ctx: AnalysisContext) -> RuleResult:
    n = ctx.config.recent.lookback_days
    hit, k = new_low(ctx.bars.closes, n)
    evidence = (f"close={ctx.bars.last.close}", f"收盘价为 {k} 日新低", f"lookback={n}")
    if hit:
        return RuleResult(ID, RuleStatus.VETO, "收盘价创近期新低", evidence)
    return RuleResult(ID, RuleStatus.PASS, "收盘价未创近期新低", evidence)
