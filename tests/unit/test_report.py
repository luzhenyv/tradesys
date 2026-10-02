"""备忘录：结论规则与章节。"""

from dataclasses import replace
from datetime import date
from pathlib import Path

from tradesys.adapters.fake import fake_snapshot, make_bars, make_chain
from tradesys.models import Fundamental, RuleStatus, Zone
from tradesys.report import conclusion, render, verdict
from tradesys.run import run

PLAYBOOK = Path(__file__).parents[2] / "playbooks" / "technical.md"
PRIOR_20 = [100.0] + [101.0] * 19
# 震荡、等量：不触发新低 / RSI 超买，无 YAML → MANUAL
CHOP = fake_snapshot(make_bars([100.0 + (i % 3) for i in range(30)]))


def test_context_veto_is_do_not_buy():
    snap = fake_snapshot(make_bars(PRIOR_20 + [99.0]))
    out = run(PLAYBOOK, snap)
    assert conclusion(out) == "不买 · 否决"
    md = render(out)
    assert "**不买 · 否决**" in md
    assert "## 判定" in md
    assert "V01" in md


def test_no_setup_is_no_buy_point_and_lists_coverage():
    out = run(PLAYBOOK, CHOP)
    assert conclusion(out) == "不买 · 无买点"
    md = render(out)
    assert "**不买 · 无买点**" in md
    assert "## 待确认" in md and "（阻断）" in md
    assert "结构：无 YAML" in md
    assert "候选规则 4（无候选，未运行）：V05 V12 V13 V14" in md
    assert "请在 YAML 中标注结构" in md
    assert "## 未能评估的买点（不阻断）" in md
    assert "## 规则覆盖（过渡）" in md
    assert "- 人工清单：" in md
    assert "V06" in md


def test_simple_setup_is_reference_not_buy():
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 104.0]
    snap = fake_snapshot(make_bars(closes, lows=[*closes[:-1], 103.0]))
    out = run(PLAYBOOK, snap)
    assert conclusion(out) == "不买 · 无买点"
    md = render(out)
    assert "## 参考（近似，不计入结论）" in md
    assert "S05 · grade" in md
    assert "⚠ 近似" in md


S01_ZONE = Zone("z-100-120", "resistance", 100.0, 120.0)


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


def test_s01_without_target_waits_for_confirmation():
    # review #1：无上方阻力 → target None → V14 MANUAL；V10 缺基本面 → 不知道等于不买
    out = run(PLAYBOOK, _s01_snap())
    assert any(c.setup_id == "S01" for c in out.candidates)
    assert conclusion(out).startswith("不买 · 待确认")
    md = render(out)
    assert "S01 · grade" in md and "（待确认）" in md
    assert "V14" in md


def test_s01_with_target_and_known_context_is_buy():
    snap = _s01_snap(
        zones=(S01_ZONE, Zone("r2", "resistance", 160.0, 170.0)),
        absent=("trendline", "neckline", "flag"),
        fundamental=Fundamental(1e11, "NMS", None),
        next_earnings=date(2026, 6, 1),
    )
    out = run(PLAYBOOK, snap)
    assert conclusion(out) == "买（long）", render(out)
    md = render(out)
    assert "**买（long）**" in md
    assert "S01 · grade" in md and "（存活）" in md


def test_s01_vetoed_by_v05_wide_stop_is_listed_as_vetoed():
    # review #2：止损过宽被 V05 否决的成熟买点必须出现在「判定」里
    snap = _s01_snap(
        absent=("trendline", "neckline", "flag"),
        fundamental=Fundamental(1e11, "NMS", None),
    )
    snap = replace(snap, zones=(Zone("z-90-120", "resistance", 90.0, 120.0),))
    out = run(PLAYBOOK, snap)
    (c,) = [x for x in out.candidates if x.setup_id == "S01"]
    assert verdict(out, c) == "否决"
    assert conclusion(out) == "不买 · 否决"
    md = render(out)
    assert "S01 · grade" in md and "（否决）" in md
    assert "V05" in md.split("## 判定")[1].split("\n## ")[0]


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


def test_cli_report_from_snapshot():
    from typer.testing import CliRunner

    from tradesys.cli import app
    from tradesys.serialize import to_json

    runner = CliRunner()
    result = runner.invoke(app, ["report", str(PLAYBOOK)], input=to_json(CHOP))
    assert result.exit_code == 0
    assert "# TEST ·" in result.stdout
    assert "**不买 · 无买点**" in result.stdout


def test_unknown_warn_does_not_block_buy():
    # 历史回放：只知道交易所（YAML exchange），市值未知 → V10 落在 warn 块，不阻断
    snap = _s01_snap(
        zones=(S01_ZONE, Zone("r2", "resistance", 160.0, 170.0)),
        absent=("trendline", "neckline", "flag"),
        fundamental=Fundamental(None, "NMS", None),
        next_earnings=date(2026, 6, 1),
    )
    out = run(PLAYBOOK, snap)
    (v10,) = [r for r in out.results if r.rule_id == "V10"]
    assert (v10.status, v10.kind) == (RuleStatus.UNAVAILABLE, "warn")
    assert conclusion(out) == "买（long）"
    assert "（不阻断：warn）" in render(out)


def test_header_shows_structure_date_and_absent():
    snap = replace(_s01_snap(absent=("flag", "neckline")), structures_confirmed=date(2026, 1, 15))
    md = render(run(PLAYBOOK, snap))
    # 01-15 → 01-22，跳过 01-19 马丁·路德·金纪念日
    assert "结构：确认于 2026-01-15（4 个交易日前） · absent: flag, neckline" in md
