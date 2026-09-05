"""Smoke tests for clock parsing (source-clock brief times)."""

from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

from modules.video.timing import format_clock, parse_clock, source_to_final


def expect(raw, seconds: float) -> None:
    got = parse_clock(raw)
    if abs(got - seconds) > 1e-6:
        raise SystemExit(f"parse_clock({raw!r}) -> {got}, expected {seconds}")


def main() -> None:
    expect(24, 24.0)
    expect(24.5, 24.5)
    expect("24", 24.0)
    expect("0:24", 24.0)
    expect("0:24.80", 24.80)
    expect("1:29.5", 89.5)
    expect("0:01:29.5", 89.5)
    expect("1:06.20", 66.20)
    expect("1:20.00", 80.0)
    if abs(source_to_final(28.0, 4.0) - 24.0) > 1e-9:
        raise SystemExit("source_to_final failed")
    if format_clock(89.5) != "1:29.50":
        raise SystemExit(f"format_clock 89.5 -> {format_clock(89.5)}")
    print("timing ok")


if __name__ == "__main__":
    main()
