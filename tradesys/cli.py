"""CLI 薄壳（命令见 README）：只做参数解析与 JSON 进出，不含逻辑。

Snapshot 从 stdin 读入，结果以 JSON 写到 stdout，可用管道串联，也可被 agent 直接调用。
"""

import sys
from pathlib import Path
from typing import Annotated

import typer
import yaml

from tradesys.calendar_utils import parse_as_of
from tradesys.models import Candidate, RunOutput, Snapshot
from tradesys.report import render
from tradesys.run import run as run_playbook
from tradesys.serialize import from_json, to_json
from tradesys.tools import TOOLS, call

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _snapshot() -> Snapshot:
    return from_json(Snapshot, sys.stdin.read())


@app.command()
def fetch(
    ticker: str,
    as_of: Annotated[
        str | None,
        typer.Option(
            help=(
                "时点，如 2026-09-30T17:00；时区由 --tz 决定（默认 UTC），"
                "也可直接带时区（如 +08:00 或 Z）；默认当前 UTC 时间"
            )
        ),
    ] = None,
    tz: Annotated[
        str,
        typer.Option(
            "--tz",
            "--timezone",
            help="as_of 的时区，如 UTC、Asia/Shanghai、America/New_York；默认 UTC",
        ),
    ] = "UTC",
) -> None:
    """取数：输出 Snapshot JSON（唯一的网络 I/O）。"""
    from tradesys.adapters.yahoo import fetch_snapshot  # 只有 fetch 需要加载 yfinance

    when = parse_as_of(as_of, tz)
    typer.echo(to_json(fetch_snapshot(ticker.upper(), when)))


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
    cand = from_json(Candidate, candidate.read_text(encoding="utf-8")) if candidate else None
    typer.echo(to_json(call(name, _snapshot(), kwargs, cand)))


@app.command()
def run(playbook: Path) -> None:
    """运行整份 playbook：stdin 读 Snapshot JSON，stdout 输出 RunOutput JSON。"""
    typer.echo(to_json(run_playbook(playbook, _snapshot())))


@app.command()
def report() -> None:
    """Markdown 备忘录。stdin 读 RunOutput JSON。"""
    out = from_json(RunOutput, sys.stdin.read())
    if out.snapshot is None:
        raise typer.BadParameter("RunOutput 无 snapshot")
    typer.echo(render(out))


if __name__ == "__main__":
    app()
