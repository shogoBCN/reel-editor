"""Smoke tests for jump-cut transition mixers."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from modules.video.transitions import (
    TRANSITION_STYLE_NAMES,
    SceneTransition,
    mix_transition_frames,
    parse_scene_transition,
    parse_transition_style_list,
)


def expect(condition: bool, message: str) -> None:
    """Fail the script when ``condition`` is false.

    Args:
        condition: Assertion.
        message: Shown on failure.

    Raises:
        SystemExit: The check failed.
    """
    if not condition:
        raise SystemExit(message)


def main() -> None:
    """Run mixer endpoint and parser checks."""
    height, width = 40, 80
    outgoing = np.zeros((height, width, 3), dtype=np.uint8)
    incoming = np.full((height, width, 3), 200, dtype=np.uint8)
    outgoing[:, :] = (10, 20, 30)
    incoming[:, :] = (200, 180, 40)

    for style in TRANSITION_STYLE_NAMES:
        start = mix_transition_frames(outgoing, incoming, 0.0, style)
        end = mix_transition_frames(outgoing, incoming, 1.0, style)
        expect(np.array_equal(start, outgoing), f"{style} progress 0")
        expect(np.array_equal(end, incoming), f"{style} progress 1")

    white_mid = mix_transition_frames(outgoing, incoming, 0.5, "fade_white")
    expect(int(white_mid.min()) >= 250, "fade_white midpoint should be near white")

    slide_mid = mix_transition_frames(outgoing, incoming, 0.5, "slide_left")
    expect(np.array_equal(slide_mid[:, : width // 2], outgoing[:, width // 2 :]), "slide left A")
    expect(np.array_equal(slide_mid[:, width // 2 :], incoming[:, : width // 2]), "slide left B")

    roll_mid = mix_transition_frames(outgoing, incoming, 0.5, "roll_up")
    # Seam shading darkens a band around the join; the far top/bottom stay pure.
    expect(np.array_equal(roll_mid[0], outgoing[height // 2]), "roll top row from A")
    expect(np.array_equal(roll_mid[-1], incoming[height // 2 - 1]), "roll bottom row from B")

    parsed = parse_scene_transition(
        {"id": "jump", "start": 12.8, "end": 13.4, "cut": 13.1, "style": "crossfade"}
    )
    expect(parsed.cut_seconds == 13.1, "parse cut")
    expect(abs(parsed.progress_at(13.1) - 0.5) < 1e-9, "progress at midpoint")
    expect(parsed.contains(13.1), "contains cut")
    expect(not parsed.contains(12.0), "outside window")

    styles = parse_transition_style_list("fade_white,slide_left,fade_white")
    expect(styles == ["fade_white", "slide_left"], f"dedupe styles {styles}")

    try:
        parse_scene_transition({"id": "bad", "start": 1, "end": 2, "style": "zoom"})
    except ValueError:
        pass
    else:
        raise SystemExit("unknown style should raise")

    default_cut = parse_scene_transition({"id": "mid", "start": 1, "end": 3})
    expect(isinstance(default_cut, SceneTransition), "type")
    expect(abs(default_cut.cut_seconds - 2.0) < 1e-9, "default cut is midpoint")
    print("transitions ok")


if __name__ == "__main__":
    main()
