"""把 RunOutput 收成 Markdown 备忘录（DESIGN §5、WORKFLOW §4）。

报告只按 status / trust / kind 与档案字段归类，不认识任何规则 ID。
"""

from tradesys.calendar_utils import trading_days_between
from tradesys.models import Candidate, RuleResult, RuleStatus, RunOutput

UNKNOWN = (RuleStatus.MANUAL, RuleStatus.UNAVAILABLE)


def _setup_trust(out: RunOutput, setup_id: str) -> str:
    for r in out.results:
        if r.rule_id == setup_id and r.kind == "setup":
            return r.trust
    return "decide"


def _decide(r: RuleResult) -> bool:
    return r.trust == "decide" and r.kind in ("veto", "warn")


def _blocking(r: RuleResult) -> bool:
    """未知的 veto 块阻断；未知的 warn 不阻断。"""
    return _decide(r) and r.status in UNKNOWN and r.kind == "veto"


def blockers(out: RunOutput, c: Candidate) -> tuple[list[RuleResult], list[RuleResult]]:
    """阻断该候选的 decide 结果：(VETO, 可能是 VETO 的未知)，含上下文与本候选。"""
    rows = [r for r in out.results if _decide(r) and r.candidate_id in (None, c.id)]
    return (
        [r for r in rows if r.status == RuleStatus.VETO],
        [r for r in rows if _blocking(r)],
    )


def plan_state(out: RunOutput, c: Candidate) -> str:
    """过期 / 暂停 / 可执行。过期与暂停不存档，由当次运行计算。"""
    snap = out.snapshot
    if c.expires is not None and snap is not None and snap.session_date > c.expires:
        return "过期"
    vetoes, unknown = blockers(out, c)
    if vetoes or unknown:
        return "暂停"
    return "可执行"


def _plans(out: RunOutput) -> list[Candidate]:
    return [c for c in out.candidates if c.expires is not None]


def _cause(r: RuleResult) -> str:
    return f"{r.rule_id} {r.title}"


def conclusion(out: RunOutput) -> str:
    """档案视图的一行结论（WORKFLOW §4）。"""
    snap = out.snapshot
    if snap is None or "idea.reason" not in snap.facts:
        return "先写想法理由"
    if plans := _plans(out):
        c = plans[0]
        state = plan_state(out, c)
        if state == "过期":
            return f"计划 {c.id} 已过期"
        if state == "暂停":
            vetoes, unknown = blockers(out, c)
            return f"计划 {c.id} 暂停（{_cause((vetoes or unknown)[0])}）"
        return f"计划 {c.id} 可执行"
    vetoes = [
        r
        for r in out.results
        if _decide(r) and r.candidate_id is None and r.status == RuleStatus.VETO
    ]
    if vetoes:
        return f"不买（{_cause(vetoes[0])}）"
    asks = [r for r in out.results if _blocking(r) and r.candidate_id is None]
    if asks:
        return f"待回答 {len(asks)} 项"
    return "审查通过，尚无计划"


def _price(c: Candidate) -> str:
    def fmt(v: float | None) -> str:
        return "—" if v is None else f"{v:.2f}"

    rr = f"{c.rr:.2f}" if c.rr is not None else "—"
    return f"entry {fmt(c.entry)} / stop {fmt(c.stop)} / target {fmt(c.target)} / rr {rr}"


def _line(r: RuleResult) -> str:
    who = f" · {r.candidate_id}" if r.candidate_id else ""
    mark = " ⚠ 近似" if r.review else ""
    ev = f" — {'；'.join(r.evidence)}" if r.evidence else ""
    return f"- **{r.rule_id} {r.title}**{who}{mark}{ev}"


def _cand_block(out: RunOutput, c: Candidate) -> list[str]:
    if c.expires is not None:
        tag, who = plan_state(out, c), c.id
    else:
        tag = "参考" if _setup_trust(out, c.setup_id) == "review" else c.grade
        who = f"{c.setup_id} · grade {c.grade}"
    rows = [r for r in out.results if r.candidate_id == c.id and r.status != RuleStatus.PASS]
    return [f"### {who}（{tag}）", f"- {_price(c)}", *map(_line, rows)]


def _header(out: RunOutput) -> list[str]:
    snap = out.snapshot
    lines = [f"# {snap.ticker} · {snap.session_date}", "", f"**{conclusion(out)}**"]
    close = f"{snap.bars.last.close:.2f}" if snap.bars.items else "—"
    data = [f"收盘 {close}", f"as_of {snap.as_of.isoformat()}"]
    if snap.next_earnings:
        n = trading_days_between(snap.session_date, snap.next_earnings)
        data.append(f"下次财报 {snap.next_earnings}（{n} 个交易日）")
    st = [f"已过期，请复核：{', '.join(snap.expired)}"] if snap.expired else []
    st += [f"absent: {', '.join(snap.absent)}"] if snap.absent else []
    st += [] if st or snap.zones or snap.lines else ["无档案结构"]
    return [*lines, "", " · ".join(data), "结构：" + " · ".join(st or ["有效"]), ""]


def render(out: RunOutput) -> str:
    """Markdown 备忘录。snapshot 取自 out.snapshot。"""
    if out.snapshot is None:
        raise ValueError("RunOutput 缺少 snapshot")
    parts = _header(out)
    if asks := [r for r in out.results if _blocking(r)]:
        parts += ["## 待回答", "", *map(_line, asks), ""]
    if plans := _plans(out):
        parts += ["## 计划", ""]
        for c in plans:
            parts += _cand_block(out, c)
        parts.append("")
    setups = [c for c in out.candidates if c.expires is None]
    unsure = [r for r in out.results if r.kind == "setup" and r.status in UNKNOWN]
    if setups or unsure:
        parts += ["## 系统建议买点", ""]
        for c in setups:
            parts += _cand_block(out, c)
        parts += [*map(_line, unsure), ""]
    advice = [r for r in out.results if r.kind == "advice" and r.status == RuleStatus.WARN]
    parts += ["## 提醒", "", *(f"- {'；'.join(r.evidence)}" for r in advice), ""]
    return "\n".join(parts).rstrip() + "\n"
