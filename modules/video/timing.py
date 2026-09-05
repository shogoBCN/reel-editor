"""
Clock parsing and motion easing for overlay animation.

Brief times are always the SOURCE recording clock (what Angélica sees in her
camera roll), not the trimmed reel. ``source_to_final`` converts after trim.
Used by brief loading and the compose renderer.
"""

from __future__ import annotations

import re


_CLOCK_RE = re.compile(
    r"^\s*(?:(?P<h>\d+):)?(?P<m>\d+):(?P<s>\d+(?:\.\d+)?)\s*$"
    r"|^\s*(?P<sec>\d+(?:\.\d+)?)\s*$"
)


def parse_clock(value) -> float:
    """
    Parse a timestamp into seconds.

    Accepts ``24``, ``24.5``, ``0:24``, ``0:24.80``, ``1:29.5``, and ``0:01:29.5``.
    Spreadsheet cells often arrive as ints/floats; those pass through as seconds.
    """
    if value is None or value == "":
        raise ValueError("Empty timestamp")
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().replace(",", ".")
    if not raw:
        raise ValueError("Empty timestamp")
    match = _CLOCK_RE.match(raw)
    if not match:
        raise ValueError(
            f"Cannot parse timestamp {value!r}. Use seconds (22.8) or m:ss (0:22.80)."
        )
    if match.group("sec") is not None:
        return float(match.group("sec"))
    hours = float(match.group("h") or 0)
    minutes = float(match.group("m") or 0)
    seconds = float(match.group("s") or 0)
    return hours * 3600.0 + minutes * 60.0 + seconds


def format_clock(seconds: float) -> str:
    """Format seconds as ``m:ss.xx`` for briefs and preview filenames."""
    if seconds < 0:
        seconds = 0.0
    minutes = int(seconds // 60)
    rem = seconds - minutes * 60
    return f"{minutes}:{rem:05.2f}"


def source_to_final(source_t: float, trim_start: float) -> float:
    """Map a source-clock time onto the trimmed reel."""
    return source_t - trim_start


def ease_out_back(t: float) -> float:
    """Pop-in scale curve: overshoots slightly so stickers feel like a stamp."""
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def fade_opacity(
    local_t: float,
    duration: float,
    fade_in: float = 0.22,
    fade_out: float = 0.28,
) -> float:
    """Linear fade at both ends of an overlay window so cuts never pop on/off."""
    if duration <= 0 or local_t < 0 or local_t > duration:
        return 0.0
    alpha = 1.0
    if local_t < fade_in:
        alpha = local_t / fade_in
    remaining = duration - local_t
    if remaining < fade_out:
        alpha = min(alpha, remaining / fade_out)
    return max(0.0, min(1.0, alpha))
