"""
Scene-cut transitions for talking-head jump cuts.

A brief lists windows (start / cut / end) on the source clock. During the
window the outgoing take (frozen at the last frame before ``cut``) mixes
into the incoming take (frozen at the first frame after ``cut``) using one
of the named styles. Sequential compose can keep the live side moving and
only freeze the other side.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from modules.video.timing import parse_timestamp_to_seconds, smoothstep


TRANSITION_STYLE_NAMES = (
    "fade_white",
    "crossfade",
    "slide_left",
    "roll_up",
    "wipe_right",
    "fade_teal",
    "iris",
    "zoom_in",
)

# Same RGB as brands/dra_angelica/brand.yaml colours.teal — used only by fade_teal.
BRAND_TEAL_RGB = (6, 138, 147)


@dataclass(frozen=True)
class SceneTransition:
    """One jump-cut window on the source recording clock."""

    transition_id: str
    start_seconds: float
    end_seconds: float
    cut_seconds: float
    style: str

    @property
    def duration_seconds(self) -> float:
        """Length of the mix window.

        Returns:
            ``end - start`` in seconds.
        """
        return self.end_seconds - self.start_seconds

    def progress_at(self, source_time_seconds: float) -> float:
        """0–1 mix amount at a source-clock time.

        Args:
            source_time_seconds: Clock of the original recording.

        Returns:
            Clipped 0–1 progress through this window.
        """
        if self.duration_seconds <= 0:
            return 1.0
        return max(
            0.0,
            min(
                1.0,
                (source_time_seconds - self.start_seconds) / self.duration_seconds,
            ),
        )

    def contains(self, source_time_seconds: float) -> bool:
        """Whether this window covers ``source_time_seconds``.

        Args:
            source_time_seconds: Clock of the original recording.

        Returns:
            True when the time is inside ``[start, end]``.
        """
        return self.start_seconds <= source_time_seconds <= self.end_seconds


def parse_scene_transition(row: dict) -> SceneTransition:
    """Build a ``SceneTransition`` from a brief mapping.

    Args:
        row: YAML item with ``id`` / ``start`` / ``end`` and optional ``cut``
            and ``style``.

    Returns:
        Validated transition.

    Raises:
        ValueError: Times are inverted or the style is unknown.
    """
    transition_id = str(row.get("id") or "transition")
    start_seconds = parse_timestamp_to_seconds(row.get("start"))
    end_seconds = parse_timestamp_to_seconds(row.get("end"))
    if end_seconds <= start_seconds:
        raise ValueError(
            f"Transition {transition_id}: end ({end_seconds}) must be after start "
            f"({start_seconds})"
        )
    if "cut" in row and row.get("cut") not in (None, ""):
        cut_seconds = parse_timestamp_to_seconds(row.get("cut"))
    else:
        cut_seconds = (start_seconds + end_seconds) / 2.0
    if not (start_seconds < cut_seconds < end_seconds):
        raise ValueError(
            f"Transition {transition_id}: cut ({cut_seconds}) must sit strictly "
            f"between start ({start_seconds}) and end ({end_seconds})"
        )
    style = str(row.get("style") or "fade_white").strip()
    if style not in TRANSITION_STYLE_NAMES:
        raise ValueError(
            f"Transition {transition_id}: unknown style {style!r}. "
            f"Use one of {', '.join(TRANSITION_STYLE_NAMES)}."
        )
    return SceneTransition(
        transition_id=transition_id,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        cut_seconds=cut_seconds,
        style=style,
    )


def parse_transition_style_list(raw: str | None) -> list[str]:
    """Split a comma-separated style list from the CLI.

    Args:
        raw: e.g. ``fade_white,iris,zoom_in``. Empty = none.

    Returns:
        Deduped style names in the given order.

    Raises:
        ValueError: An unknown style name appears.
    """
    if not raw or not str(raw).strip():
        return []
    styles: list[str] = []
    seen: set[str] = set()
    for part in str(raw).split(","):
        name = part.strip()
        if not name or name in seen:
            continue
        if name not in TRANSITION_STYLE_NAMES:
            raise ValueError(
                f"Unknown transition style {name!r}. "
                f"Use one of {', '.join(TRANSITION_STYLE_NAMES)}."
            )
        seen.add(name)
        styles.append(name)
    return styles


def _blend(outgoing: np.ndarray, incoming: np.ndarray, amount: float) -> np.ndarray:
    """Linear mix of two RGB frames.

    Args:
        outgoing: ``H×W×3`` uint8.
        incoming: Same shape.
        amount: 0 = outgoing, 1 = incoming.

    Returns:
        Mixed uint8 frame.
    """
    amount = max(0.0, min(1.0, amount))
    mixed = outgoing.astype(np.float32) * (1.0 - amount) + incoming.astype(
        np.float32
    ) * amount
    return mixed.astype(np.uint8)


def _fade_white(outgoing: np.ndarray, incoming: np.ndarray, progress: float) -> np.ndarray:
    """Fade outgoing to white, then white into incoming.

    Args:
        outgoing: Frame before the cut.
        incoming: Frame after the cut.
        progress: 0–1 through the window.

    Returns:
        Mixed uint8 frame.
    """
    eased = smoothstep(progress)
    white = np.full_like(outgoing, 255, dtype=np.uint8)
    if eased <= 0.5:
        return _blend(outgoing, white, smoothstep(eased * 2.0))
    return _blend(white, incoming, smoothstep((eased - 0.5) * 2.0))


def _crossfade(outgoing: np.ndarray, incoming: np.ndarray, progress: float) -> np.ndarray:
    """Dissolve outgoing into incoming.

    Args:
        outgoing: Frame before the cut.
        incoming: Frame after the cut.
        progress: 0–1 through the window.

    Returns:
        Mixed uint8 frame.
    """
    return _blend(outgoing, incoming, smoothstep(progress))


def _slide_left(outgoing: np.ndarray, incoming: np.ndarray, progress: float) -> np.ndarray:
    """Push outgoing left while incoming enters from the right.

    Args:
        outgoing: Frame before the cut.
        incoming: Frame after the cut.
        progress: 0–1 through the window.

    Returns:
        Mixed uint8 frame.
    """
    height, width = outgoing.shape[:2]
    shift = int(round(smoothstep(progress) * width))
    shift = max(0, min(width, shift))
    if shift == 0:
        return outgoing
    if shift >= width:
        return incoming
    frame = np.empty_like(outgoing)
    frame[:, : width - shift] = outgoing[:, shift:]
    frame[:, width - shift :] = incoming[:, :shift]
    return frame


def _roll_up(outgoing: np.ndarray, incoming: np.ndarray, progress: float) -> np.ndarray:
    """Push outgoing up while incoming rolls in from below, with a seam band.

    Args:
        outgoing: Frame before the cut.
        incoming: Frame after the cut.
        progress: 0–1 through the window.

    Returns:
        Mixed uint8 frame.
    """
    height, width = outgoing.shape[:2]
    shift = int(round(smoothstep(progress) * height))
    shift = max(0, min(height, shift))
    if shift == 0:
        return outgoing
    if shift >= height:
        return incoming
    frame = np.empty_like(outgoing)
    frame[: height - shift] = outgoing[shift:]
    frame[height - shift :] = incoming[:shift]
    seam_half = 14
    seam = height - shift
    y0 = max(0, seam - seam_half)
    y1 = min(height, seam + seam_half)
    if y1 > y0:
        band = frame[y0:y1].astype(np.float32)
        rows = np.arange(y1 - y0, dtype=np.float32)
        # Darken the join so it reads as a roll rather than a hard push.
        centre = (seam - y0)
        distance = np.abs(rows - centre) / max(1.0, float(seam_half))
        shade = 0.72 + 0.28 * np.clip(distance, 0.0, 1.0)
        frame[y0:y1] = (band * shade[:, None, None]).astype(np.uint8)
    return frame


def _wipe_right(outgoing: np.ndarray, incoming: np.ndarray, progress: float) -> np.ndarray:
    """Hard wipe: a vertical edge travels left to right, revealing incoming in place.

    Unlike ``slide_left``, neither take moves — B is uncovered where it already sits.

    Args:
        outgoing: Frame before the cut.
        incoming: Frame after the cut.
        progress: 0–1 through the window.

    Returns:
        Mixed uint8 frame.
    """
    width = outgoing.shape[1]
    edge = int(round(smoothstep(progress) * width))
    edge = max(0, min(width, edge))
    if edge == 0:
        return outgoing
    if edge >= width:
        return incoming
    frame = outgoing.copy()
    frame[:, :edge] = incoming[:, :edge]
    return frame


def _fade_teal(outgoing: np.ndarray, incoming: np.ndarray, progress: float) -> np.ndarray:
    """Fade outgoing through brand teal, then teal into incoming.

    Args:
        outgoing: Frame before the cut.
        incoming: Frame after the cut.
        progress: 0–1 through the window.

    Returns:
        Mixed uint8 frame.
    """
    eased = smoothstep(progress)
    teal = np.empty_like(outgoing)
    teal[..., 0] = BRAND_TEAL_RGB[0]
    teal[..., 1] = BRAND_TEAL_RGB[1]
    teal[..., 2] = BRAND_TEAL_RGB[2]
    if eased <= 0.5:
        return _blend(outgoing, teal, smoothstep(eased * 2.0))
    return _blend(teal, incoming, smoothstep((eased - 0.5) * 2.0))


def _iris(outgoing: np.ndarray, incoming: np.ndarray, progress: float) -> np.ndarray:
    """Circular reveal from the centre, with a short feathered rim.

    Args:
        outgoing: Frame before the cut.
        incoming: Frame after the cut.
        progress: 0–1 through the window.

    Returns:
        Mixed uint8 frame.
    """
    height, width = outgoing.shape[:2]
    centre_y = (height - 1) / 2.0
    centre_x = (width - 1) / 2.0
    max_radius = float(np.hypot(centre_x, centre_y))
    radius = smoothstep(progress) * max_radius
    rows = np.arange(height, dtype=np.float32)[:, None]
    cols = np.arange(width, dtype=np.float32)[None, :]
    distance = np.sqrt((rows - centre_y) ** 2 + (cols - centre_x) ** 2)
    feather = 42.0
    alpha = np.clip((radius - distance) / feather + 0.5, 0.0, 1.0)[:, :, None]
    mixed = outgoing.astype(np.float32) * (1.0 - alpha) + incoming.astype(np.float32) * alpha
    return mixed.astype(np.uint8)


def _scale_about_centre(frame: np.ndarray, scale: float) -> np.ndarray:
    """Enlarge a frame and crop back to the original canvas (centre-weighted).

    Args:
        frame: ``H×W×3`` uint8.
        scale: Factor ≥ 1. Values below 1.0 return the input.

    Returns:
        Same-shape uint8 frame.
    """
    if scale <= 1.001:
        return frame
    height, width = frame.shape[:2]
    new_width = max(width, int(round(width * scale)))
    new_height = max(height, int(round(height * scale)))
    resized = np.array(
        Image.fromarray(frame).resize((new_width, new_height), Image.Resampling.BILINEAR)
    )
    y0 = max(0, (new_height - height) // 2)
    x0 = max(0, (new_width - width) // 2)
    return resized[y0 : y0 + height, x0 : x0 + width]


def _zoom_in(outgoing: np.ndarray, incoming: np.ndarray, progress: float) -> np.ndarray:
    """Punch through the cut: A zooms in as B zooms down from a slight oversize.

    Args:
        outgoing: Frame before the cut.
        incoming: Frame after the cut.
        progress: 0–1 through the window.

    Returns:
        Mixed uint8 frame.
    """
    eased = smoothstep(progress)
    outgoing_scale = 1.0 + 0.22 * eased
    incoming_scale = 1.22 - 0.22 * eased
    zoomed_out = _scale_about_centre(outgoing, outgoing_scale)
    zoomed_in = _scale_about_centre(incoming, incoming_scale)
    return _blend(zoomed_out, zoomed_in, eased)


_STYLE_MIXERS = {
    "fade_white": _fade_white,
    "crossfade": _crossfade,
    "slide_left": _slide_left,
    "roll_up": _roll_up,
    "wipe_right": _wipe_right,
    "fade_teal": _fade_teal,
    "iris": _iris,
    "zoom_in": _zoom_in,
}


def mix_transition_frames(
    outgoing: np.ndarray,
    incoming: np.ndarray,
    progress: float,
    style: str,
) -> np.ndarray:
    """Composite two RGB frames with a named transition.

    Args:
        outgoing: Take A (before the cut).
        incoming: Take B (after the cut).
        progress: 0–1 through the window (0 = all outgoing).
        style: One of ``TRANSITION_STYLE_NAMES``.

    Returns:
        Mixed uint8 frame. Progress outside 0–1 is clipped; unknown styles
        raise ``ValueError``.
    """
    mixer = _STYLE_MIXERS.get(style)
    if mixer is None:
        raise ValueError(
            f"Unknown transition style {style!r}. "
            f"Use one of {', '.join(TRANSITION_STYLE_NAMES)}."
        )
    progress = max(0.0, min(1.0, float(progress)))
    if progress <= 0.0:
        return outgoing
    if progress >= 1.0:
        return incoming
    return mixer(outgoing, incoming, progress)


def apply_scene_transitions(
    composited: np.ndarray,
    source_time_seconds: float,
    transitions: list[SceneTransition],
    outgoing_holds: dict[str, np.ndarray],
    incoming_holds: dict[str, np.ndarray],
    style_override: str | None = None,
) -> np.ndarray:
    """Mix hold frames over any transition window covering this timestamp.

    Before ``cut`` the live ``composited`` frame is take A and the incoming
    hold is take B. After ``cut`` the outgoing hold is take A and the live
    frame is take B.

    Args:
        composited: Overlays + captions for the current source time.
        source_time_seconds: Clock of the original recording.
        transitions: Brief windows.
        outgoing_holds: Last take-A frame per transition id.
        incoming_holds: First take-B frame per transition id.
        style_override: If set, use this style for every window.

    Returns:
        Frame after any active mix (unchanged when outside all windows).
    """
    frame = composited
    for transition in transitions:
        if not transition.contains(source_time_seconds):
            continue
        style = style_override or transition.style
        progress = transition.progress_at(source_time_seconds)
        if source_time_seconds < transition.cut_seconds:
            outgoing = frame
            incoming = incoming_holds[transition.transition_id]
        else:
            outgoing = outgoing_holds[transition.transition_id]
            incoming = frame
        frame = mix_transition_frames(outgoing, incoming, progress, style)
    return frame
