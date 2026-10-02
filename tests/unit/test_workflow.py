"""一只股票从想法到计划过期：fake 行情 + 真实 playbook（WORKFLOW §1）。"""

from datetime import date
from pathlib import Path

from tradesys.adapters.fake import fake_snapshot, make_bars
from tradesys.adapters.yahoo import attach_dossier
from tradesys.models import Fundamental
from tradesys.report import conclusion, render
from tradesys.run import run

PLAYBOOK = Path(__file__).parents[2] / "playbooks" / "technical.md"
V09 = (
    "business",
    "revenue_mix",
    "last_earnings",
    "growth",
    "margin",
    "guidance",
    "competitors",
    "catalyst",
    "tracked",
)
# 阻力 100–120 放量突破，T 回踩收在区间内
N = 12
CLOSES = [110.0] * N + [125.0, 108.0]
VOLS = [1e6] * N + [2e6, 3e6]
OPENS = [110.0] * N + [125.0, 105.0]


def _yaml(t: date, *, idea=False, answers=False, plan=False, expires: date | None = None) -> str:
    lines = ["ticker: TEST", "exchange: NMS"]
    if idea or answers:
        lines += [f"idea:\n  reason: 回踩突破区间\n  source: chart\n  at: {t}"]
    if answers:
        lines.append("facts:")
        for key, val in (
            ("v06.sector_top_loser", "false"),
            ("v08.stopped_out", "false"),
            ("v10b.social_hype", "false"),
        ):
            lines.append(f"  {key}: {{value: {val}, at: {t}}}")
        for k in V09:
            lines.append(f"  v09.{k}: {{value: true, at: {t}}}")
    if idea or answers:
        lines += [
            "zones:",
            f"  - {{id: z-100-120, kind: resistance, low: 100, high: 120, confirmed_at: {t}}}",
            f"  - {{id: r2, kind: resistance, low: 160, high: 170, confirmed_at: {t}}}",
            "absent:",
            f"  - {{kind: trendline, confirmed_at: {t}}}",
            f"  - {{kind: neckline, confirmed_at: {t}}}",
            f"  - {{kind: flag, confirmed_at: {t}}}",
        ]
    if plan:
        exp = f", expires: {expires}" if expires else ""
        lines += [
            "plans:",
            f"  - {{id: p1, entry: 108, stop: 99, target: 160, at: {t}{exp}}}",
        ]
    return "\n".join(lines) + "\n"


def _snap(tmp_path, closes: list[float], text: str):
    (tmp_path / "TEST.yaml").write_text(text, encoding="utf-8")
    n = len(closes)
    extra = n - len(CLOSES)
    vols = VOLS + [1e6] * extra
    opens = OPENS + closes[len(OPENS) :]
    lows = OPENS + closes[len(OPENS) :]
    snap = fake_snapshot(
        make_bars(closes, vols, opens=opens, highs=closes, lows=lows),
        fundamental=Fundamental(1e11, "NMS", None),
        next_earnings=date(2026, 6, 1),
    )
    return run(PLAYBOOK, attach_dossier(snap, tmp_path))


def test_one_ticker_from_idea_to_expired_plan(tmp_path):
    # 1. 只有 ticker
    out = _snap(tmp_path, CLOSES, "ticker: TEST\n")
    assert conclusion(out) == "先写想法理由"

    t = out.snapshot.session_date
    # 2. 写入 idea
    out = _snap(tmp_path, CLOSES, _yaml(t, idea=True))
    assert conclusion(out).startswith("待回答 ")
    md = render(out)
    for key in ("v06.sector_top_loser", "v08.stopped_out", "v10b.social_hype", "v09.business"):
        assert f"请回答 {key}" in md

    # 3. 写入回答 → 审查通过，尚无计划，附系统建议买点
    out = _snap(tmp_path, CLOSES, _yaml(t, answers=True))
    assert conclusion(out) == "审查通过，尚无计划", render(out)
    assert "## 系统建议买点" in render(out) and "S01 · grade" in render(out)

    # 4. 写入 plan → 可执行
    out = _snap(tmp_path, CLOSES, _yaml(t, answers=True, plan=True))
    assert conclusion(out) == "计划 p1 可执行", render(out)

    # 5. 次日收盘跌破区间下沿：突破收回 → 下方无支撑 → V12 暂停
    pause = CLOSES + [99.0]
    t1 = fake_snapshot(make_bars(pause)).session_date
    out = _snap(tmp_path, pause, _yaml(t1, answers=True, plan=True))
    assert conclusion(out) == "计划 p1 暂停（V12 突破后悬空、远离支撑）", render(out)

    # 再次日重新站上区间上沿 → 恢复可执行
    resume = pause + [125.0]
    t2 = fake_snapshot(make_bars(resume)).session_date
    out = _snap(tmp_path, resume, _yaml(t2, answers=True, plan=True))
    assert conclusion(out) == "计划 p1 可执行", render(out)

    # 6. 超过 expires
    out = _snap(tmp_path, resume, _yaml(t2, answers=True, plan=True, expires=date(2026, 1, 8)))
    assert conclusion(out) == "计划 p1 已过期"
