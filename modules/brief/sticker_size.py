"""Map Angélica's size words to the on-screen sticker box.

She pastes photos at whatever pixel size she found. In «Qué quieres» she
says how big they should *look* (grande / mediano / chico). Compose then
fits the file into that box. She never types ``max_w``.
"""

from __future__ import annotations

import re

# On-screen boxes (1080-wide reel). Keep height ≤ ~340 so stickers stay
# beside the head, below the Instagram crop, not on the hat.
DEFAULT_STICKER_SIZE_BOXES: dict[str, tuple[int, int]] = {
    "chico": (320, 260),
    "mediano": (400, 340),
    "grande": (480, 340),
}
DEFAULT_STICKER_SIZE_NAME = "mediano"


def fold_spanish(text: str) -> str:
    """Lowercase and strip accents so regexes can stay ASCII.

    Args:
        text: Raw «Qué quieres» cell (or empty).

    Returns:
        Folded string.
    """
    folded = str(text or "").strip().lower()
    for source, dest in (
        ("á", "a"),
        ("é", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ú", "u"),
        ("ü", "u"),
        ("ñ", "n"),
    ):
        folded = folded.replace(source, dest)
    return folded


def infer_sticker_size_name(notes: str) -> str:
    """Pick grande / mediano / chico from free Spanish.

    Args:
        notes: «Qué quieres» (or CSV ``notas_edicion``).

    Returns:
        One of ``chico``, ``mediano``, ``grande``. Default mediano when she
        says nothing about size — or says «no tan grande».
    """
    text = fold_spanish(notes)
    if not text:
        return DEFAULT_STICKER_SIZE_NAME
    if re.search(r"\bno (tan |muy )?grande\b", text):
        return DEFAULT_STICKER_SIZE_NAME
    if re.search(
        r"tamano (chico|pequeno)|mas (chico|pequeno|chica|pequena)|"
        r"chiquit[oa]|pequenit[oa]|bien chic[oa]|"
        r"\bchic[oa]s?\b|\bpequen[oa]s?\b",
        text,
    ):
        return "chico"
    if re.search(
        r"tamano grande|bien grande|grandote|enorme|"
        r"se vea grande|mas grande|\bgrandes?\b",
        text,
    ):
        return "grande"
    if re.search(r"tamano mediano|\bmediano\b|tamano normal", text):
        return "mediano"
    return DEFAULT_STICKER_SIZE_NAME


def sticker_box_for_notes(
    notes: str,
    boxes: dict[str, tuple[int, int]] | None = None,
) -> tuple[int, int, str]:
    """Return ``(max_w, max_h, size_name)`` for a sticker row.

    Args:
        notes: Free Spanish from the sheet.
        boxes: Optional brand override of ``DEFAULT_STICKER_SIZE_BOXES``.

    Returns:
        Pixel box and the name that selected it.
    """
    mapping = boxes or DEFAULT_STICKER_SIZE_BOXES
    name = infer_sticker_size_name(notes)
    width, height = mapping.get(name) or DEFAULT_STICKER_SIZE_BOXES[name]
    return int(width), int(height), name
