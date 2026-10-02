"""把 RunOutput 收成 Markdown 备忘录（DESIGN §5 结论规则）。

过渡形态：章节随规则实现进度增减。报告只按 status / trust / kind 归类，不认识任何规则。
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


def candidates(out: RunOutput, trust: str = "decide") -> list[Candidate]:
    return [c for c in out.candidates if _setup_trust(out, c.setup_id) == trust]


def blockers(out: RunOutput, c: Candidate) -> tuple[list[RuleResult], list[RuleResult]]:
    """阻断该候选的 decide 结果：(VETO, 可能是 VETO 的未知)，含上下文规则与本候选的规则。"""
    rows = [r for r in out.results if _decide(r) and r.candidate_id in (None, c.id)]
    return (
        [r for r in rows if r.status == RuleStatus.VETO],
        [r for r in rows if _blocking(r)],
    )


def _blocking(r: RuleResult) -> bool:
    """未知的 veto 块阻断买入；未知的 warn 块即使命中也只是 WARN，不阻断。"""
    return _decide(r) and r.status in UNKNOWN and r.kind == "veto"


def verdict(out: RunOutput, c: Candidate) -> str:
    vetoes, unknown = blockers(out, c)
    return "否决" if vetoes else "待确认" if unknown else "存活"


def plan_state(out: RunOutput, c: Candidate) -> str:
    """过期 / 暂停 / 可执行。过期与暂停不存档，由当次运行计算。"""
    snap = out.snapshot
    if c.expires is not None and snap is not None and snap.session_date > c.expires:
        return "过期"
    vetoes, unknown = blockers(out, c)
    if vetoes or unknown:
        return "暂停"
    return "可执行"


def conclusion(out: RunOutput) -> str:
    """不知道等于不买：只有全部 decide 规则可判定且未否决的候选才是买点。"""
    context_veto = any(
        _decide(r) and r.status == RuleStatus.VETO and r.candidate_id is None for r in out.results
    )
    cands = candidates(out)
    tags = [verdict(out, c) for c in cands]
    if context_veto:
        return "不买 · 否决"
    if "存活" in tags:
        return "买（long）"
    if "待确认" in tags:
        c = cands[tags.index("待确认")]
        return f"不买 · 待确认 {len(blockers(out, c)[1])} 项"
    return "不买 · 否决" if cands else "不买 · 无买点"


def _price(c: Candidate) -> str:
    def fmt(v: float | None) -> str:
        return "—" if v is None else f"{v:.2f}"

    rr = f"{c.rr:.2f}" if c.rr is not None else "—"
    return f"entry {fmt(c.entry)} / stop {fmt(c.stop)} / target {fmt(c.target)} / rr {rr}"


def _line(r: RuleResult) -> str:
    who = f" · {r.candidate_id}" if r.candidate_id else ""
    mark = " ⚠ 近似" if r.review else ""
    ev = f" — {'；'.join(r.evidence)}" if r.evidence else ""
    return f"- **{r.rule_id} {r.title}** {r.status}{who}{mark}{ev}"


def _cand_block(out: RunOutput, c: Candidate) -> list[str]:
    if c.expires is not None:
        tag, who = plan_state(out, c), c.id
    else:
        tag = verdict(out, c) if _setup_trust(out, c.setup_id) == "decide" else "参考"
        who = f"{c.setup_id} · grade {c.grade}"
    rows = [r for r in out.results if r.candidate_id == c.id and r.status != RuleStatus.PASS]
    return [f"### {who}（{tag}）", f"- {_price(c)}", *map(_line, rows)]


def _header(out: RunOutput) -> list[str]:
    snap = out.snapshot
    head = conclusion(out)
    lines = [f"# {snap.ticker} · {snap.session_date}", "", f"**{head}**"]
    if head == "买（long）":
        c = next(c for c in candidates(out) if verdict(out, c) == "存活")
        lines += [f"{c.setup_id} · grade {c.grade} · {_price(c)}"]
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

    hits = [
        r
        for r in out.results
        if _decide(r) and r.candidate_id is None and r.status in (RuleStatus.VETO, RuleStatus.WARN)
    ]
    parts += ["## 判定", "", *map(_line, hits)]
    for c in candidates(out):
        parts += _cand_block(out, c)
    if not hits and not candidates(out):
        parts.append("无成熟买点，无上下文否决。")
    parts.append("")

    pending = [r for r in out.results if _decide(r) and r.status in UNKNOWN]
    if pending:
        tag = {True: "（阻断）", False: "（不阻断：warn）"}
        parts += ["## 待确认", "", *(_line(r) + tag[_blocking(r)] for r in pending), ""]
    unsure = [r for r in out.results if r.kind == "setup" and r.status in UNKNOWN]
    if unsure:
        parts += ["## 未能评估的买点（不阻断）", "", *map(_line, unsure), ""]

    ref_hits = [
        r
        for r in out.results
        if r.trust == "review" and r.status in (RuleStatus.VETO, RuleStatus.WARN)
    ]
    if ref_hits or candidates(out, "review"):
        parts += ["## 参考（近似，不计入结论）", "", *map(_line, ref_hits)]
        for c in candidates(out, "review"):
            parts += _cand_block(out, c)
        parts.append("")

    advice = [r for r in out.results if r.kind == "advice" and r.status == RuleStatus.WARN]
    parts += ["## 提醒", "", *(f"- {'；'.join(r.evidence)}" for r in advice), ""]
    return "\n".join(parts).rstrip() + "\n"
