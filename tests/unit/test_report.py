"""备忘录：结论规则与章节。"""

from dataclasses import replace
from datetime import date
from pathlib import Path

from tradesys.adapters.fake import fake_snapshot, make_bars, make_chain
from tradesys.models import Candidate, Fact, Fundamental, RuleStatus, RunOutput, Zone
from tradesys.report import conclusion, plan_state, render
from tradesys.run import run

PLAYBOOK = Path(__file__).parents[2] / "playbooks" / "technical.md"
PRIOR_20 = [100.0] + [101.0] * 19
# 震荡、等量：不触发新低 / RSI 超买，无 YAML → MANUAL
CHOP = fake_snapshot(make_bars([100.0 + (i % 3) for i in range(30)]))


def test_no_idea_asks_to_write_reason():
    out = run(PLAYBOOK, CHOP)
    assert conclusion(out) == "先写想法理由"
    md = render(out)
    assert "**先写想法理由**" in md
    assert "## 待回答" in md
    assert "请回答 v06.sector_top_loser" in md
    assert "结构：无档案结构" in md
    assert "请在 YAML 中标注结构" in md
    assert "## 系统建议买点" in md


def test_simple_setup_is_suggestion_not_buy():
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 104.0]
    snap = fake_snapshot(make_bars(closes, lows=[*closes[:-1], 103.0]))
    out = run(PLAYBOOK, snap)
    assert conclusion(out) == "先写想法理由"
    md = render(out)
    assert "## 系统建议买点" in md
    assert "S05 · grade" in md
    assert "⚠ 近似" in md


S01_ZONE = Zone("z-100-120", "resistance", 100.0, 120.0)
S01_T = date(2026, 1, 22)
V09 = ("business", "revenue_mix", "last_earnings", "growth", "margin", "guidance")
V09 += ("competitors", "catalyst", "tracked")


def _clean(t: date) -> dict:
    """人的回答全部「无问题」：有理由，非板块领跌，未被止损，熟悉基本面，社群正常。"""
    return {
        "idea.reason": Fact("回踩突破区间", t),
        "v06.sector_top_loser": Fact(False, t),
        "v08.stopped_out": Fact(False, t),
        "v10b.social_hype": Fact(False, t),
        **{f"v09.{k}": Fact(True, t) for k in V09},
    }


CLEAN = _clean(S01_T)


def _s01_snap(zones=(S01_ZONE,), **inputs):
    """阻力 100–120 放量突破，T 缩量回踩收在区间内并收出止跌形态。"""
    n = 12
    closes = [110.0] * n + [125.0, 108.0]
    vols = [1e6] * n + [2e6, 3e6]
    opens = [110.0] * n + [125.0, 105.0]
    return fake_snapshot(
        make_bars(closes, vols, opens=opens, highs=closes, lows=opens),
        zones=zones,
        **inputs,
    )


def test_s01_without_target_is_still_a_suggestion():
    out = run(PLAYBOOK, _s01_snap())
    assert any(c.setup_id == "S01" for c in out.candidates)
    assert conclusion(out) == "先写想法理由"
    md = render(out)
    assert "S01 · grade" in md
    assert "V14" in md


def test_reviewed_without_plan_is_ready():
    snap = _s01_snap(
        zones=(S01_ZONE, Zone("r2", "resistance", 160.0, 170.0)),
        absent=("trendline", "neckline", "flag"),
        fundamental=Fundamental(1e11, "NMS", None),
        next_earnings=date(2026, 6, 1),
        facts=CLEAN,
    )
    out = run(PLAYBOOK, snap)
    assert conclusion(out) == "审查通过，尚无计划", render(out)
    md = render(out)
    assert "**审查通过，尚无计划**" in md
    assert "## 系统建议买点" in md and "S01 · grade" in md


def test_s01_vetoed_by_v05_is_listed_under_suggestions():
    snap = _s01_snap(
        absent=("trendline", "neckline", "flag"),
        fundamental=Fundamental(1e11, "NMS", None),
    )
    snap = replace(snap, zones=(Zone("z-90-120", "resistance", 90.0, 120.0),))
    out = run(PLAYBOOK, snap)
    assert any(c.setup_id == "S01" for c in out.candidates)
    assert conclusion(out) == "先写想法理由"
    assert "V05" in render(out).split("## 系统建议买点")[1]


def test_report_warn_and_advice_and_band68():
    snap = fake_snapshot(
        make_bars([100.0 + (i % 3) for i in range(30)]),
        next_earnings=date(2026, 3, 1),
        chain=make_chain([(102.0, 3.0, 3.0)]),
        zones=(Zone("s", "support", 90.0, 95.0),),
    )
    md = render(run(PLAYBOOK, snap))
    tips = md.split("## 提醒")[1]
    assert "美东 9:30–10:00 不下单" in tips
    assert "Band68=" in tips
    assert "下次财报 2026-03-01" in md


def test_cli_report_from_run_output():
    from typer.testing import CliRunner

    from tradesys.cli import app
    from tradesys.serialize import to_json

    runner = CliRunner()
    result = runner.invoke(app, ["report"], input=to_json(run(PLAYBOOK, CHOP)))
    assert result.exit_code == 0
    assert "# TEST ·" in result.stdout
    assert "**先写想法理由**" in result.stdout


def test_unknown_warn_does_not_block_buy():
    # 历史回放：只知道交易所（YAML exchange），市值未知 → V10 落在 warn 块，不阻断
    snap = _s01_snap(
        zones=(S01_ZONE, Zone("r2", "resistance", 160.0, 170.0)),
        absent=("trendline", "neckline", "flag"),
        fundamental=Fundamental(None, "NMS", None),
        next_earnings=date(2026, 6, 1),
        facts=CLEAN,
    )
    out = run(PLAYBOOK, snap)
    (v10,) = [r for r in out.results if r.rule_id == "V10"]
    assert (v10.status, v10.kind) == (RuleStatus.UNAVAILABLE, "warn")
    assert conclusion(out) == "审查通过，尚无计划"
    assert "待回答" not in conclusion(out)


def test_header_shows_expired_groups_and_absent():
    snap = replace(_s01_snap(absent=("flag", "neckline")), expired=("trendline",))
    md = render(run(PLAYBOOK, snap))
    assert "结构：已过期，请复核：trendline · absent: flag, neckline" in md


def test_unanswered_question_blocks_buy_until_answered():
    # 不知道 = 不买，并提问：同一买点，少答 V09 一项 → 待确认，并列出要填写的 key
    kw = dict(
        zones=(S01_ZONE, Zone("r2", "resistance", 160.0, 170.0)),
        absent=("trendline", "neckline", "flag"),
        fundamental=Fundamental(1e11, "NMS", None),
        next_earnings=date(2026, 6, 1),
    )
    partial = {k: v for k, v in CLEAN.items() if k != "v09.tracked"}
    out = run(PLAYBOOK, _s01_snap(facts=partial, **kw))
    assert conclusion(out) == "待回答 1 项"
    assert "请回答 v09.tracked" in render(out)
    assert conclusion(run(PLAYBOOK, _s01_snap(facts=CLEAN, **kw))) == "审查通过，尚无计划"


def test_plan_expires_the_session_after_expires():
    snap = fake_snapshot(make_bars([125.0] * 5))
    live = Candidate("p1", "", 125.0, 119.0, 140.0, "", expires=snap.session_date)
    dead = Candidate("p1", "", 125.0, 119.0, 140.0, "", expires=date(2026, 1, 8))
    assert plan_state(RunOutput((), (live,), snap), live) == "可执行"
    assert plan_state(RunOutput((), (dead,), snap), dead) == "过期"


def _plan_snap(entry, stop, target):
    plan = Candidate("p1", "", entry, stop, target, "", expires=date(2026, 2, 20))
    return fake_snapshot(
        make_bars([125.0] * 14),
        zones=(Zone("z-100-120", "support", 100.0, 120.0),),
        absent=("trendline", "neckline", "flag"),
        fundamental=Fundamental(1e11, "NMS", None),
        next_earnings=date(2026, 6, 1),
        facts=CLEAN,
        plans=(plan,),
    )


def test_plan_paused_by_v12_and_resumes_when_near_support():
    far = run(PLAYBOOK, _plan_snap(140.0, 130.0, 155.0))
    (p,) = [c for c in far.candidates if c.id == "p1"]
    assert plan_state(far, p) == "暂停"
    assert conclusion(far) == "计划 p1 暂停（V12 突破后悬空、远离支撑）"
    assert "## 计划" in render(far)
    near = run(PLAYBOOK, _plan_snap(125.0, 119.0, 140.0))
    (p,) = [c for c in near.candidates if c.id == "p1"]
    assert plan_state(near, p) == "可执行"
    assert conclusion(near) == "计划 p1 可执行"


def test_new_low_without_plan_is_do_not_buy():
    bars = make_bars(PRIOR_20 + [99.0])
    snap = fake_snapshot(bars, facts=_clean(bars.last.d))
    out = run(PLAYBOOK, snap)
    assert conclusion(out) == "不买（V01 收盘价创近期新低）"


def test_idea_without_answers_is_pending():
    t = CHOP.session_date
    out = run(PLAYBOOK, replace(CHOP, facts={"idea.reason": Fact("想买", t)}))
    assert conclusion(out).startswith("待回答 ")


def test_expired_plan_headline():
    snap = _plan_snap(125.0, 119.0, 140.0)
    (plan,) = snap.plans
    out = run(PLAYBOOK, replace(snap, plans=(replace(plan, expires=date(2026, 1, 8)),)))
    assert conclusion(out) == "计划 p1 已过期"
