"""备忘录：结论规则与章节。"""

from datetime import date
from pathlib import Path

from tradesys.adapters.fake import fake_snapshot, make_bars, make_chain
from tradesys.models import Zone
from tradesys.report import conclusion, render
from tradesys.run import run

PLAYBOOK = Path(__file__).parents[2] / "playbooks" / "technical.md"
PRIOR_20 = [100.0] + [101.0] * 19
# 震荡、等量：不触发新低 / RSI 超买，无 YAML → MANUAL
CHOP = fake_snapshot(make_bars([100.0 + (i % 3) for i in range(30)]))


def test_context_veto_is_do_not_buy():
    snap = fake_snapshot(make_bars(PRIOR_20 + [99.0]))
    out = run(PLAYBOOK, snap)
    assert conclusion(out) == "不买"
    md = render(out, PLAYBOOK)
    assert "**不买**" in md
    assert "## VETO" in md


def test_manual_without_veto_needs_human():
    out = run(PLAYBOOK, CHOP)
    assert conclusion(out) == "待人工确认"
    md = render(out, PLAYBOOK)
    assert "## 人工检查" in md
    assert "请在 YAML 中标注结构" in md


def test_report_lists_setup_candidate():
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 104.0]
    snap = fake_snapshot(make_bars(closes, lows=[*closes[:-1], 103.0]))
    md = render(run(PLAYBOOK, snap), PLAYBOOK)
    assert "## 候选买点" in md
    assert "S05" in md
    assert "entry 104.0" in md


def test_report_warn_and_advice_and_band68():
    snap = fake_snapshot(
        make_bars([100.0 + (i % 3) for i in range(30)]),
        next_earnings=date(2026, 3, 1),
        chain=make_chain([(102.0, 3.0, 3.0)]),
        zones=(Zone("s", "support", 90.0, 95.0),),
    )
    md = render(run(PLAYBOOK, snap), PLAYBOOK)
    assert "## 提醒" in md
    assert "美东 9:30–10:00 不下单" in md
    assert "距财报" in md
    assert "Band68=" in md
    assert "近似算法" in md


def test_cli_report_from_snapshot():
    from typer.testing import CliRunner

    from tradesys.cli import app
    from tradesys.serialize import to_json

    runner = CliRunner()
    result = runner.invoke(app, ["report", str(PLAYBOOK)], input=to_json(CHOP))
    assert result.exit_code == 0
    assert "# TEST ·" in result.stdout
    assert "**待人工确认**" in result.stdout
