"""执行器（DESIGN §4）：读 playbook，按 rule 块调用工具，汇总结果。不含任何规则逻辑。"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from tradesys.models import Candidate, Check, RuleResult, RuleStatus, RunOutput, Snapshot
from tradesys.tools import call

HEADING = re.compile(r"^### (\S+)\s+(.*)$")
STATUS = {"veto": RuleStatus.VETO, "warn": RuleStatus.WARN, "advice": RuleStatus.WARN}
ASKS = ("manual", "todo")  # 只写 ask，不调用工具


KINDS = {"veto", "warn", "setup", "manual", "todo", "advice"}
KEYS = {"kind", "scope", "when", "trust", "ask", "say", "entry", "stop", "target"}


def _validate(rule_id: str, block: dict) -> dict:
    """拼写错误不得悄悄改变语义（如 `When:` 让 veto 变成无条件命中）。"""
    if not isinstance(block, dict) or block.get("kind") not in KINDS:
        raise ValueError(f"{rule_id}: kind 必须是 {sorted(KINDS)} 之一")
    kind = block["kind"]
    checks = (
        (not set(block) <= KEYS, f"未知键 {sorted(set(block) - KEYS)}"),
        (kind in ("veto", "warn", "setup") and not block.get("when"), "缺少 when"),
        (kind == "setup" and not block.get("entry"), "缺少 entry"),
        (kind in ASKS and not block.get("ask"), "缺少 ask"),
        (kind == "advice" and not (block.get("say") or block.get("when")), "缺少 say 或 when"),
        (block.get("trust") not in (None, "decide", "review", "memo"), "trust 不合法"),
        (block.get("scope") not in (None, "candidate"), "scope 不合法"),
    )
    for bad, problem in checks:
        if bad:
            raise ValueError(f"{rule_id}: {problem}")
    return block


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    blocks: tuple[dict, ...]  # 按出现顺序；首个命中的块决定结果


def parse(text: str) -> list[Rule]:
    """提取每个 `### ID 标题` 下的 ```rule 块（YAML）。没有 rule 块的条目也返回（文档段落）。"""
    rules: list[Rule] = []
    block: list[str] | None = None
    for line in text.splitlines():
        if block is not None:
            if line.strip() == "```":
                r = rules[-1]
                parsed = _validate(r.id, yaml.safe_load("\n".join(block)))
                rules[-1] = Rule(r.id, r.title, (*r.blocks, parsed))
                block = None
            else:
                block.append(line)
        elif m := HEADING.match(line):
            rules.append(Rule(m[1], m[2].strip(), ()))
        elif line.strip() == "```rule" and rules:
            block = []
    return rules


def check_all(
    when: list[dict], snap: Snapshot, candidate: Candidate | None, unknown_first: bool = False
) -> Check:
    """依次调用 when 中的工具，AND 组合。

    默认 Kleene：任一 False → False；否则有 None → None。
    unknown_first（setup 用）：有 None 即 None，缺结构时不因另一工具 False 而静默跳过。
    未知时 evidence 只取未知工具的证据。
    """
    checks = []
    for item in when:
        ((name, args),) = item.items()
        checks.append(call(name, snap, args, candidate))
    review = any(c.review for c in checks)
    grade = next((c.grade for c in checks if c.grade), None)
    unknown = [c for c in checks if c.hit is None]
    if unknown and (unknown_first or all(c.hit is not False for c in checks)):
        evidence = tuple(e for c in unknown for e in c.evidence)
        return Check(None, evidence, review, any(c.missing for c in unknown), grade=grade)
    evidence = tuple(e for c in checks for e in c.evidence)
    return Check(all(c.hit for c in checks), evidence, review, grade=grade)


def block_trust(block: dict) -> str:
    """decide 计入结论；review 只进参考；memo（manual / todo / advice）不参与判定。"""
    if block.get("trust"):
        return str(block["trust"])
    if block.get("kind") in (*ASKS, "advice"):
        return "memo"
    return "decide"


def _field(spec: dict | None, snap: Snapshot) -> Check:
    if not spec:
        return Check(True)
    ((name, args),) = spec.items()
    return call(name, snap, args or {})


def _unknown(rule: Rule, c: Check, block: dict, cid: str | None, review: bool) -> RuleResult:
    status = RuleStatus.UNAVAILABLE if c.missing else RuleStatus.MANUAL
    return RuleResult(
        rule.id, rule.title, status, c.evidence, cid, review, block_trust(block), block["kind"]
    )


def evaluate_setup(rule: Rule, snap: Snapshot) -> tuple[RuleResult, Candidate | None]:
    """首个产出的 setup 块给出至多一个 Candidate；未知的块记下后继续判断下一块。"""
    evidence: tuple[str, ...] = ()
    review, unknown, trust = False, None, "decide"
    for block in rule.blocks:
        if block.get("kind") != "setup":
            continue
        trust = block_trust(block)
        c = check_all(block["when"], snap, None, unknown_first=True)
        review = review or c.review
        if c.hit is None:
            unknown = unknown or _unknown(rule, c, block, None, review)
            continue
        evidence = c.evidence
        if not c.hit:
            continue
        entry, stop, target = (_field(block.get(k), snap) for k in ("entry", "stop", "target"))
        review = review or entry.review or stop.review or target.review
        evidence = evidence + entry.evidence + stop.evidence + target.evidence
        if entry.hit is None or entry.value is None:
            unknown = unknown or _unknown(rule, entry, block, None, review)
            continue
        grade = next(
            (g for g in (c.grade, entry.grade, stop.grade, target.grade) if g),
            "B" if review else "A",
        )
        cand = Candidate(rule.id, rule.id, entry.value, stop.value, target.value, grade, evidence)
        quotes = (f"entry={entry.value}", f"stop={stop.value}", f"target={target.value}")
        rr = RuleResult(
            rule.id, rule.title, RuleStatus.PASS, quotes + evidence, None, review, trust, "setup"
        )
        return rr, cand
    passed = RuleResult(
        rule.id, rule.title, RuleStatus.PASS, evidence, None, review, trust, "setup"
    )
    return unknown or passed, None


def evaluate(rule: Rule, snap: Snapshot, candidate: Candidate | None = None) -> RuleResult:
    """块按 if / elif 判断：首个命中的块决定结果；未知的块记下后继续，都不命中时报告未知。

    之前有未知的 veto 块时，只有后续命中的 veto 才能取代它。
    """
    cid = candidate.id if candidate else None
    evidence: tuple[str, ...] = ()
    review, unknown = False, None
    kind, trust = rule.blocks[0]["kind"], block_trust(rule.blocks[0])
    for block in rule.blocks:
        if block["kind"] == "setup":
            continue
        if block["kind"] in ASKS:
            return unknown or RuleResult(
                rule.id,
                rule.title,
                RuleStatus.MANUAL,
                (block["ask"],),
                cid,
                trust=block_trust(block),
                kind=block["kind"],
            )
        c = check_all(block.get("when") or [], snap, candidate)
        review = review or c.review
        if c.hit is None:
            unknown = unknown or _unknown(rule, c, block, cid, review)
            continue
        evidence = c.evidence
        if c.hit:
            if unknown and unknown.kind == "veto" and block["kind"] != "veto":
                return unknown  # 可能的否决不能被较弱的命中盖掉
            said = (block["say"],) if block.get("say") else ()
            status = STATUS[block["kind"]]
            return RuleResult(
                rule.id,
                rule.title,
                status,
                said + c.evidence,
                cid,
                review,
                block_trust(block),
                block["kind"],
            )
    return unknown or RuleResult(
        rule.id, rule.title, RuleStatus.PASS, evidence, cid, review, trust, kind
    )


def run(playbook: str | Path, snap: Snapshot, candidates: tuple[Candidate, ...] = ()) -> RunOutput:
    """先跑 setup 产出候选，再跑其余规则。scope: candidate 对每个候选各一次。"""
    results: list[RuleResult] = []
    produced: list[Candidate] = []
    rules = [r for r in parse(Path(playbook).read_text(encoding="utf-8")) if r.blocks]
    for rule in rules:
        if rule.blocks[0].get("kind") == "setup":
            rr, cand = evaluate_setup(rule, snap)
            results.append(rr)
            if cand:
                produced.append(cand)
    all_cands = candidates + tuple(produced)
    ids = [c.id for c in all_cands]
    if len(ids) != len(set(ids)):
        raise ValueError(f"候选 id 重复：{sorted(i for i in set(ids) if ids.count(i) > 1)}")
    idle: list[str] = []
    for rule in rules:
        if rule.blocks[0].get("kind") == "setup":
            continue
        if rule.blocks[0].get("scope") == "candidate":
            results += [evaluate(rule, snap, c) for c in all_cands]
            idle += [] if all_cands else [rule.id]
        else:
            results.append(evaluate(rule, snap))
    return RunOutput(tuple(results), all_cands, snap, tuple(idle))
