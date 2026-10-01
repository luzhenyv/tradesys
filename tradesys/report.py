"""把 RunOutput 收成 Markdown 备忘录（DESIGN §3 结论规则）。"""

from pathlib import Path

from tradesys.calendar_utils import weekdays_between
from tradesys.models import Candidate, RuleResult, RuleStatus, RunOutput, Snapshot
from tradesys.run import parse
from tradesys.tools.band68 import band68
from tradesys.tools.candle import shooting_star
from tradesys.tools.fib import impulse, retrace
from tradesys.tools.structure import current_role

FIXED = (
    "非财报盘前盘后大涨大跌不参与，以常规时段开盘为准",
    "美东 9:30–10:00 不下单",
    "分时图备忘待 EP095 / EP111 / EP161 入库",
)


def _ev(r: RuleResult) -> str:
    return "；".join(r.evidence) if r.evidence else ""


def _setup_trust(out: RunOutput, setup_id: str) -> str:
    for r in out.results:
        if r.rule_id == setup_id and r.candidate_id is None:
            return r.trust
    return "decide"


def survivors(out: RunOutput, trust: str = "decide") -> list[Candidate]:
    """trust=decide 的买点，且没被 decide 候选否决杀掉。"""
    killed = {
        r.candidate_id
        for r in out.results
        if r.status == RuleStatus.VETO and r.candidate_id and r.trust == "decide"
    }
    return [
        c for c in out.candidates if _setup_trust(out, c.setup_id) == trust and c.id not in killed
    ]


def conclusion(out: RunOutput) -> str:
    """只看 trust=decide：上下文 VETO → 不买；否则有存活买点 → 买（long）；否则不买。"""
    if any(
        r.status == RuleStatus.VETO and r.candidate_id is None and r.trust == "decide"
        for r in out.results
    ):
        return "不买"
    if survivors(out, "decide"):
        return "买（long）"
    return "不买"


def _call(out: RunOutput) -> list[str]:
    """报告头：买或不买，买则带上第一存活买点的价格。"""
    if conclusion(out) != "买（long）":
        return ["**不买**"]
    c = survivors(out, "decide")[0]
    rr = f"{c.rr:.2f}" if c.rr is not None else "—"
    stop = c.stop if c.stop is not None else "—"
    tgt = c.target if c.target is not None else "—"
    return [
        f"**买（long）**  {c.setup_id}  grade {c.grade}",
        f"entry {c.entry}  stop {stop}  target {tgt}  rr {rr}",
    ]


def _advice(snap: Snapshot) -> list[str]:
    lines = list(FIXED)
    if snap.next_earnings:
        n = weekdays_between(snap.session_date, snap.next_earnings)
        flag = " ⚠" if 0 <= n <= 5 else ""
        lines.append(f"距财报 {n} 个交易日（{snap.next_earnings}）{flag}")
    band = (
        band68(snap.bars.last.close, snap.chain, 0.02) if snap.chain and snap.bars.items else None
    )
    if band:
        low, high = band
        lines.append(f"Band68=[{low:.1f}, {high:.1f}]；expiry={snap.chain.expiry}")
        supports = [z for z in snap.zones if current_role(z, snap.bars) == "support"]
        if supports:
            z = max(supports, key=lambda z: z.high)
            if low < z.high:
                lines.append(f"Band68 下沿可能触及支撑 {z.low}-{z.high}")
        resists = [z for z in snap.zones if current_role(z, snap.bars) == "resistance"]
        if resists:
            z = min(resists, key=lambda z: z.low)
            if high > z.low:
                lines.append(f"Band68 上沿可能超出阻力 {z.low}-{z.high}")
        imp = impulse(snap.bars.closes)
        if imp:
            fib = retrace(*imp, 0.618)
            if low < fib:
                lines.append(f"Band68 下沿低于 Fib 61.8%（{fib:.1f}）")
    top = shooting_star(snap)
    if top.hit:
        lines.append("见顶形态（流星线），当天不宜抄底 / 追高")
    return lines


def _cand_block(c: Candidate, results: tuple[RuleResult, ...]) -> list[str]:
    rr = f"{c.rr:.2f}" if c.rr is not None else "—"
    tgt = c.target if c.target is not None else "—"
    stop = c.stop if c.stop is not None else "—"
    related = [r for r in results if r.candidate_id == c.id]
    vetoes = [r for r in related if r.status == RuleStatus.VETO]
    tag = "否决" if vetoes else "存活"
    lines = [
        f"### {c.setup_id} · grade {c.grade}（{tag}）",
        f"- entry {c.entry} / stop {stop} / target {tgt} / rr {rr}",
    ]
    for r in related:
        extra = f"：{_ev(r)}" if r.evidence else ""
        lines.append(f"- {r.rule_id} {r.title} **{r.status}**{extra}")
    return lines


def render(out: RunOutput, playbook: str | Path | None = None) -> str:
    """Markdown 备忘录。snapshot 取自 out.snapshot。"""
    snap = out.snapshot
    if snap is None:
        raise ValueError("RunOutput 缺少 snapshot")
    close = snap.bars.last.close if snap.bars.items else "—"
    parts = [
        f"# {snap.ticker} · {snap.session_date}",
        "",
        *_call(out),
        "",
        f"收盘 {close} · as_of {snap.as_of.isoformat()}",
        "",
    ]

    def line(r: RuleResult) -> str:
        who = f" · {r.candidate_id}" if r.candidate_id else ""
        ev = f" — {_ev(r)}" if r.evidence else ""
        return f"- **{r.rule_id} {r.title}**{who}{ev}"

    decide_hits = [
        r
        for r in out.results
        if r.trust == "decide"
        and r.status in (RuleStatus.VETO, RuleStatus.WARN)
        and r.candidate_id is None
    ]
    decide_cands = survivors(out, "decide")
    parts += ["## 判定", ""]
    if decide_hits or decide_cands:
        for r in decide_hits:
            parts.append(line(r))
        for c in decide_cands:
            parts += _cand_block(c, out.results)
    else:
        parts.append("成熟规则未给出买点。")
    parts.append("")

    review_hits = [
        r
        for r in out.results
        if r.trust == "review" and r.status in (RuleStatus.VETO, RuleStatus.WARN)
    ]
    review_cands = [c for c in out.candidates if _setup_trust(out, c.setup_id) == "review"]
    if review_hits or review_cands:
        parts += ["## 参考（近似，不计入结论）", ""]
        for r in review_hits:
            parts.append(line(r))
        for c in review_cands:
            parts += _cand_block(c, out.results)
        parts.append("")

    memos = [r for r in out.results if r.status in (RuleStatus.MANUAL, RuleStatus.UNAVAILABLE)]
    undone: list[str] = []
    if playbook:
        undone = [
            r.id
            for r in parse(Path(playbook).read_text(encoding="utf-8"))
            if not r.blocks and r.id[:1] in "VS" and r.id[1:2].isdigit()
        ]
    if memos or undone:
        parts += ["## 备忘", ""]
        for r in memos:
            parts.append(line(r))
        for uid in undone:
            parts.append(f"- **{uid}** 尚未实现")
        parts.append("")
    parts += ["## 提醒", ""]
    parts += [f"- {x}" for x in _advice(snap)]
    parts.append("")
    return "\n".join(parts).rstrip() + "\n"
