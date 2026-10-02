"""手动走完 fetch | run | report，便于下断点。不进 CLI。

临时稿放 scripts/local/（gitignore）。
"""

import argparse
from pathlib import Path

from tradesys.adapters.yahoo import fetch_snapshot
from tradesys.calendar_utils import parse_as_of
from tradesys.models import RunOutput, Snapshot
from tradesys.report import render
from tradesys.run import run
from tradesys.serialize import from_json, to_json

ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK = ROOT / "playbooks" / "technical.md"


def pipeline(
    ticker: str = "AMZN",
    playbook: str | Path = PLAYBOOK,
    as_of: str | None = None,
    tz: str = "UTC",
    snap_path: str | Path | None = None,
    *,
    roundtrip: bool = True,
) -> tuple[Snapshot, RunOutput, str]:
    """等价于: fetch TICKER | run PLAYBOOK | report。

    snap_path 有值时跳过 Yahoo，读已有 Snapshot JSON。
    roundtrip=True 时中间走 JSON，与 CLI 管道一致。
    """
    if snap_path:
        snap = from_json(Snapshot, Path(snap_path).read_text(encoding="utf-8"))
    else:
        snap = fetch_snapshot(ticker.upper(), parse_as_of(as_of, tz))
    if roundtrip:
        snap = from_json(Snapshot, to_json(snap))
    out = run(playbook, snap)
    if roundtrip:
        out = from_json(RunOutput, to_json(out))
    return snap, out, render(out)


def main() -> None:
    p = argparse.ArgumentParser(description="fetch | run | report，便于下断点")
    p.add_argument("ticker", nargs="?", default="AMZN")
    p.add_argument("--as-of")
    p.add_argument("--tz", default="UTC")
    p.add_argument("--playbook", type=Path, default=PLAYBOOK)
    p.add_argument("--from", dest="snap_path", help="已有 Snapshot JSON，跳过 fetch")
    p.add_argument("--no-roundtrip", action="store_true", help="对象直传，不走 JSON")
    args = p.parse_args()
    _, _, md = pipeline(
        args.ticker,
        args.playbook,
        args.as_of,
        args.tz,
        args.snap_path,
        roundtrip=not args.no_roundtrip,
    )
    print(md, end="")


if __name__ == "__main__":
    main()
