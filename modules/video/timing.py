"""
Timestamp parsing and motion curves for overlay animation.

Brief times are always the SOURCE recording clock (what Angélica sees on her
phone), not the trimmed Instagram reel. ``convert_source_time_to_final_time``
subtracts ``trim_start`` when we need to talk about the published file.

Used by brief loading (spreadsheet cells) and the compose renderer (easing).
"""

from __future__ import annotations

import datetime
import re
from typing import Any


# Spreadsheet cells arrive as ``24``, ``0:24``, ``1:29,5``, or ``10:25,5``.
# Commas are decimals (Spanish). Tenths are enough; she does not mark frames.
TIMESTAMP_PATTERN = re.compile(
    r"^\s*(?:(?P<hours>\d+):)?(?P<minutes>\d+):(?P<seconds>\d+(?:\.\d+)?)\s*$"
    r"|^\s*(?P<plain_seconds>\d+(?:\.\d+)?)\s*$"
)


def parse_timestamp_to_seconds(value: Any) -> float:
    """Parse a brief/spreadsheet timestamp into seconds on the source clock.

    Accepts ``24``, ``24,5``, ``0:24``, ``1:29,5``, ``10:25,5`` (10 min 25.5 s),
    and the same with a period. Numeric cells pass through as seconds.
    ``datetime.time`` from Excel is read as h:mm:ss of a day.

    Args:
        value: Raw cell or YAML scalar.

    Returns:
        Time in seconds from the start of the source recording.

    Raises:
        ValueError: Empty value or unrecognised format.
    """
    if value is None or value == "":
        raise ValueError("Empty timestamp")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, datetime.datetime):
        value = value.time()
    if isinstance(value, datetime.time):
        return (
            value.hour * 3600.0
            + value.minute * 60.0
            + value.second
            + value.microsecond / 1_000_000.0
        )
    # Spanish sheets use a comma decimal: ``1:29,5`` → 89.5s.
    text = str(value).strip().replace(",", ".")
    if not text:
        raise ValueError("Empty timestamp")
    match = TIMESTAMP_PATTERN.match(text)
    if not match:
        raise ValueError(
            f"Cannot parse timestamp {value!r}. Use m:ss or m:ss,d (1:29,5)."
        )
    if match.group("plain_seconds") is not None:
        return float(match.group("plain_seconds"))
    hours = float(match.group("hours") or 0)
    minutes = float(match.group("minutes") or 0)
    seconds = float(match.group("seconds") or 0)
    return hours * 3600.0 + minutes * 60.0 + seconds


def format_seconds_as_timestamp(total_seconds: float) -> str:
    """Format seconds as ``m:ss.xx`` for engine logs and preview filenames.

    Args:
        total_seconds: Duration or source-clock time.

    Returns:
        String such as ``1:29.50``. Negative values clamp to zero so a bad
        trim cannot produce ``-0:04.00``.
    """
    if total_seconds < 0:
        total_seconds = 0.0
    minutes = int(total_seconds // 60)
    remainder = total_seconds - minutes * 60
    return f"{minutes}:{remainder:05.2f}"


def format_seconds_as_sheet_timestamp(total_seconds: float) -> str:
    """Format seconds the way Angélica writes them: ``m:ss`` or ``m:ss,d``.

    Tenths only (``1:29,5``). No frame counts. Comma decimal, as on a
    Spanish keyboard.

    Args:
        total_seconds: Duration or source-clock time.

    Returns:
        String such as ``0:28`` or ``10:25,5``.
    """
    if total_seconds < 0:
        total_seconds = 0.0
    tenths = int(total_seconds * 10.0 + 0.5)
    minutes, tenths_in_minute = divmod(tenths, 600)
    seconds, tenth = divmod(tenths_in_minute, 10)
    if tenth:
        return f"{minutes}:{seconds:02d},{tenth}"
    return f"{minutes}:{seconds:02d}"


def smoothstep(amount: float) -> float:
    """Cubic Hermite smoothstep so fades and wipes ease instead of linear cuts.

    Args:
        amount: Unclamped 0–1 (values outside are clipped).

    Returns:
        Smoothed 0–1.
    """
    amount = max(0.0, min(1.0, amount))
    return amount * amount * (3.0 - 2.0 * amount)


def convert_source_time_to_final_time(
    source_time_seconds: float, trim_start_seconds: float
) -> float:
    """Map a source-clock time onto the trimmed reel.

    The published file starts at ``trim_start`` of the recording, so final
    time is always ``source - trim``. Preview notes in Spanish ("final 0:24")
    use this conversion.

    Args:
        source_time_seconds: Time on Angélica's original file.
        trim_start_seconds: Seconds dropped from the start of that file.

    Returns:
        Time on the composed reel (may be negative if the event is in the
        discarded head — callers should not schedule overlays there).
    """
    return source_time_seconds - trim_start_seconds


def compute_pop_in_scale(progress: float) -> float:
    """Stamp-like overshoot so stickers do not fade in like a PowerPoint.

    This is the standard CSS ``ease-out-back`` curve (overshoot 1.70158).
    Values above 1.0 are intentional: the sticker grows past 100% then settles.

    Args:
        progress: 0–1 through the pop window (already clamped).

    Returns:
        Scale factor, typically 0 at start and ~1.07 at the overshoot peak.
    """
    progress = max(0.0, min(1.0, progress))
    overshoot = 1.70158
    overshoot_plus_one = overshoot + 1
    return (
        1
        + overshoot_plus_one * (progress - 1) ** 3
        + overshoot * (progress - 1) ** 2
    )


def compute_edge_fade_opacity(
    local_time_seconds: float,
    duration_seconds: float,
    fade_in_seconds: float = 0.22,
    fade_out_seconds: float = 0.28,
) -> float:
    """Linear fade at both ends of an overlay window so cuts never pop on/off.

    Hold is fully opaque in the middle. If the window is shorter than the
    fade-in + fade-out, the two ramps meet and the peak opacity drops — that
    is preferable to a hard cut on a 0.3s sting.

    Args:
        local_time_seconds: Seconds since this overlay's start.
        duration_seconds: Overlay window length.
        fade_in_seconds: Ramp up at the start.
        fade_out_seconds: Ramp down at the end.

    Returns:
        Opacity in 0–1. Zero outside the window.
    """
    if duration_seconds <= 0 or local_time_seconds < 0 or local_time_seconds > duration_seconds:
        return 0.0
    opacity = 1.0
    if local_time_seconds < fade_in_seconds:
        opacity = local_time_seconds / fade_in_seconds
    remaining = duration_seconds - local_time_seconds
    if remaining < fade_out_seconds:
        opacity = min(opacity, remaining / fade_out_seconds)
    return max(0.0, min(1.0, opacity))
