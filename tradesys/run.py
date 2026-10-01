"""执行器（DESIGN §5）：读 playbook，按 rule 块调用工具，汇总结果。不含任何规则逻辑。"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from tradesys.models import Candidate, Check, RuleResult, RuleStatus, Snapshot
from tradesys.tools import call

HEADING = re.compile(r"^### (\S+)\s+(.*)$")
STATUS = {"veto": RuleStatus.VETO, "warn": RuleStatus.WARN}


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    blocks: tuple[dict, ...]  # 按出现顺序；首个命中的块决定结果


def parse(text: str) -> list[Rule]:
    """提取每个 `### ID 标题` 下的 ```rule 块（YAML）。没有 rule 块的条目也返回，表示未实现。"""
    rules: list[Rule] = []
    block: list[str] | None = None
    for line in text.splitlines():
        if block is not None:
            if line.strip() == "```":
                r = rules[-1]
                rules[-1] = Rule(r.id, r.title, (*r.blocks, yaml.safe_load("\n".join(block))))
                block = None
            else:
                block.append(line)
        elif m := HEADING.match(line):
            rules.append(Rule(m[1], m[2].strip(), ()))
        elif line.strip() == "```rule" and rules:
            block = []
    return rules


def check_all(when: list[dict], snap: Snapshot, candidate: Candidate | None) -> Check:
    """依次调用 when 中的工具，全部为 True 才命中（AND）。"""
    checks = []
    for item in when:
        ((name, args),) = item.items()
        checks.append(call(name, snap, args, candidate))
    evidence = tuple(e for c in checks for e in c.evidence)
    review = any(c.review for c in checks)
    if any(c.hit is False for c in checks):
        return Check(False, evidence, review)
    if any(c.hit is None for c in checks):
        return Check(None, evidence, review, missing=any(c.missing for c in checks))
    return Check(True, evidence, review)


def evaluate(rule: Rule, snap: Snapshot, candidate: Candidate | None = None) -> RuleResult:
    cid = candidate.id if candidate else None
    evidence: tuple[str, ...] = ()
    review = False
    for block in rule.blocks:
        if block["kind"] == "manual":
            return RuleResult(rule.id, rule.title, RuleStatus.MANUAL, (block["ask"],), cid)
        c = check_all(block["when"], snap, candidate)
        evidence, review = c.evidence, review or c.review
        if c.hit is None:
            status = RuleStatus.UNAVAILABLE if c.missing else RuleStatus.MANUAL
            return RuleResult(rule.id, rule.title, status, evidence, cid, review)
        if c.hit:
            return RuleResult(rule.id, rule.title, STATUS[block["kind"]], evidence, cid, review)
    return RuleResult(rule.id, rule.title, RuleStatus.PASS, evidence, cid, review)


def run(
    playbook: str | Path, snap: Snapshot, candidates: tuple[Candidate, ...] = ()
) -> list[RuleResult]:
    """运行整份 playbook。scope: candidate 的规则对每个候选买点各运行一次。"""
    results = []
    for rule in parse(Path(playbook).read_text(encoding="utf-8")):
        if not rule.blocks:
            continue
        if rule.blocks[0].get("scope") == "candidate":
            results += [evaluate(rule, snap, c) for c in candidates]
        else:
            results.append(evaluate(rule, snap))
    return results
