"""Smoke tests for timestamp parsing (source-clock brief times)."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from modules.video.timing import (
    convert_source_time_to_final_time,
    format_seconds_as_timestamp,
    parse_timestamp_to_seconds,
)


def expect(raw, seconds: float) -> None:
    """Assert ``parse_timestamp_to_seconds(raw)`` equals ``seconds``.

    Args:
        raw: Spreadsheet-style timestamp.
        seconds: Expected source-clock seconds.

    Raises:
        SystemExit: Mismatch.
    """
    got = parse_timestamp_to_seconds(raw)
    if abs(got - seconds) > 1e-6:
        raise SystemExit(
            f"parse_timestamp_to_seconds({raw!r}) -> {got}, expected {seconds}"
        )


def main() -> None:
    """Run the timestamp round-trip checks."""
    expect(24, 24.0)
    expect(24.5, 24.5)
    expect("24", 24.0)
    expect("0:24", 24.0)
    expect("0:24.80", 24.80)
    expect("1:29.5", 89.5)
    expect("0:01:29.5", 89.5)
    expect("1:06.20", 66.20)
    expect("1:20.00", 80.0)
    if abs(convert_source_time_to_final_time(28.0, 4.0) - 24.0) > 1e-9:
        raise SystemExit("convert_source_time_to_final_time failed")
    formatted = format_seconds_as_timestamp(89.5)
    if formatted != "1:29.50":
        raise SystemExit(f"format_seconds_as_timestamp 89.5 -> {formatted}")
    print("timing ok")


if __name__ == "__main__":
    main()
