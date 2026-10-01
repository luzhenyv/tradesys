"""CLI 薄壳（DESIGN §7）：只做参数解析与 JSON 进出，不含逻辑。

Snapshot 从 stdin 读入，结果以 JSON 写到 stdout，可用管道串联，也可被 agent 直接调用。
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
import yaml

from tradesys.calendar_utils import ET
from tradesys.models import Candidate, Snapshot
from tradesys.run import run as run_playbook
from tradesys.serialize import from_json, from_plain, to_json
from tradesys.tools import TOOLS

app = typer.Typer(no_args_is_help=True, add_completion=False)

Candidates = Annotated[Path | None, typer.Option(help="候选买点 JSON 文件（列表）")]


def _snapshot() -> Snapshot:
    return from_json(Snapshot, sys.stdin.read())


def _candidates(path: Path | None) -> tuple[Candidate, ...]:
    if path is None:
        return ()
    return from_plain(tuple[Candidate, ...], yaml.safe_load(path.read_text(encoding="utf-8")))


@app.command()
def fetch(
    ticker: str,
    as_of: Annotated[
        str | None, typer.Option(help="美东时间，如 2026-10-01T17:00；默认现在")
    ] = None,
    expiry: Annotated[str, typer.Option(help="期权到期日：monthly | weekly")] = "monthly",
) -> None:
    """取数：输出 Snapshot JSON（唯一的网络 I/O）。"""
    from tradesys.adapters.yahoo import fetch_snapshot  # 只有 fetch 需要加载 yfinance

    when = datetime.fromisoformat(as_of) if as_of else datetime.now(ET)
    typer.echo(to_json(fetch_snapshot(ticker.upper(), when, expiry)))


@app.command()
def tools() -> None:
    """列出所有工具及其说明。"""
    for name, fn in TOOLS.items():
        typer.echo(f"{name:18} {(fn.__doc__ or '').strip().splitlines()[0]}")


@app.command()
def tool(
    name: str,
    arg: Annotated[list[str], typer.Option(help="工具参数 k=v，可重复")] = [],  # noqa: B006
    candidate: Annotated[Path | None, typer.Option(help="单个候选买点 JSON 文件")] = None,
) -> None:
    """运行单个工具：stdin 读 Snapshot JSON，stdout 输出 Check JSON。"""
    kwargs = {k: yaml.safe_load(v) for k, v in (a.split("=", 1) for a in arg)}
    extra = (from_json(Candidate, candidate.read_text(encoding="utf-8")),) if candidate else ()
    typer.echo(to_json(TOOLS[name](_snapshot(), *extra, **kwargs)))


@app.command()
def run(playbook: Path, candidates: Candidates = None) -> None:
    """运行整份 playbook：stdin 读 Snapshot JSON，stdout 输出 RuleResult 列表 JSON。"""
    typer.echo(to_json(run_playbook(playbook, _snapshot(), _candidates(candidates))))


if __name__ == "__main__":
    app()
