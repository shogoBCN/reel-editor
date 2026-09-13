"""Gemini image-edit fill for a screen-fixed CapCut watermark crop.

Sends a tight 1:1 patch around the logo (upscaled, magenta guide box), asks
the model to reconstruct that branch/sky, then pastes only the logo region
back with a feathered mask so the rest of the frame is original pixels.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any
import time

import cv2
import numpy as np
from PIL import Image as PilImage

from modules.modules_initialiser import get_module

# Native CapCut export is 478x850. Tight 1:1 around the top-left logo.
CROP_X, CROP_Y, CROP_W, CROP_H = 0, 0, 176, 176
SEND_SIZE = 768
# Logo on this export (padded). Used for the paste mask and the guide box.
LOGO_X, LOGO_Y, LOGO_W, LOGO_H = 10, 8, 152, 44
FEATHER_PIXELS = 14
GUIDE_BGR = (255, 0, 255)

PROMPT = (
    "This is a tight crop from a video frame. A white logo and text overlay "
    "sits inside the magenta rectangle (CapCut scissors + wordmark, or a faint "
    "white ghost of it). Remove that white overlay and the magenta rectangle. "
    "Reconstruct the tree bark, leaves, and sky that belong in that exact spot. "
    "Do not invent a new scene, camera angle, or different branches. "
    "Do not change anything outside the marked area. "
    "Keep the identical lighting, color, and grain. Photorealistic."
)

PROMPT_RETRY = (
    "Remove the faint white graphic on the diagonal branch and any remaining "
    "white lettering. Fill with the real bark and sky behind it. Keep every "
    "leaf, branch, and the rest of the photo identical. Same framing."
)


def logo_crop(frame_bgr: np.ndarray) -> np.ndarray:
    """Return the 1:1 patch around the watermark.

    Args:
        frame_bgr: Full video frame in OpenCV BGR.

    Returns:
        BGR crop ``CROP_W`` x ``CROP_H``.
    """
    return frame_bgr[CROP_Y : CROP_Y + CROP_H, CROP_X : CROP_X + CROP_W].copy()


def _logo_xy_in_crop() -> tuple[int, int, int, int]:
    """Logo box in crop coordinates.

    Returns:
        ``x, y, w, h`` relative to ``logo_crop``.
    """
    return LOGO_X - CROP_X, LOGO_Y - CROP_Y, LOGO_W, LOGO_H


def _pil_from_bgr(frame_bgr: np.ndarray) -> PilImage.Image:
    """Convert an OpenCV BGR array to RGB PIL.

    Args:
        frame_bgr: BGR uint8 image.

    Returns:
        RGB PIL image.
    """
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    return PilImage.fromarray(rgb)


def _bgr_from_pil(image: PilImage.Image) -> np.ndarray:
    """Convert a PIL image to OpenCV BGR.

    Args:
        image: RGB or RGBA PIL image.

    Returns:
        BGR uint8 array.
    """
    rgb = image.convert("RGB")
    return cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)


def _pil_from_genai_image(genai_image: Any) -> PilImage.Image | None:
    """Unwrap google-genai ``Image`` (bytes, not PIL) to RGB PIL.

    Args:
        genai_image: SDK Image model or None.

    Returns:
        RGB PIL image, or None if empty.
    """
    if genai_image is None:
        return None
    data = getattr(genai_image, "image_bytes", None)
    if not data:
        return None
    return PilImage.open(BytesIO(data)).convert("RGB")


def _response_debug_text(response: Any) -> str:
    """Collect finish reason and any text parts for error messages.

    Args:
        response: generate_content response.

    Returns:
        Short debug string.
    """
    bits: list[str] = []
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        candidate = candidates[0]
        bits.append(f"finish={getattr(candidate, 'finish_reason', None)}")
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            text = getattr(part, "text", None)
            if text:
                bits.append(text[:400])
    prompt_feedback = getattr(response, "prompt_feedback", None)
    if prompt_feedback is not None:
        bits.append(f"feedback={prompt_feedback}")
    return " | ".join(bits) if bits else "empty response"


def _image_from_gemini_response(response: Any) -> PilImage.Image:
    """Pull the first inline image out of a generate_content response.

    Args:
        response: google-genai GenerateContent response.

    Returns:
        RGB PIL image from the model.

    Raises:
        RuntimeError: No image part in the response.
    """
    parts = list(getattr(response, "parts", None) or [])
    if not parts and getattr(response, "candidates", None):
        content = response.candidates[0].content
        parts = list(getattr(content, "parts", None) or [])
    for part in parts:
        if hasattr(part, "as_image"):
            image = _pil_from_genai_image(part.as_image())
            if image is not None:
                return image
        inline = getattr(part, "inline_data", None)
        if inline is not None and getattr(inline, "data", None):
            return PilImage.open(BytesIO(inline.data)).convert("RGB")
    raise RuntimeError(
        "Gemini returned no image (blocked or text-only). "
        + _response_debug_text(response)
    )


def _guided_send_image(crop_bgr: np.ndarray) -> np.ndarray:
    """Upscale the crop and draw a magenta box around the logo.

    Args:
        crop_bgr: Native-resolution 1:1 crop.

    Returns:
        BGR image at ``SEND_SIZE`` for the API.
    """
    upscaled = cv2.resize(
        crop_bgr, (SEND_SIZE, SEND_SIZE), interpolation=cv2.INTER_CUBIC
    )
    scale = SEND_SIZE / CROP_W
    x, y, box_w, box_h = _logo_xy_in_crop()
    x0 = int(round(x * scale))
    y0 = int(round(y * scale))
    x1 = int(round((x + box_w) * scale))
    y1 = int(round((y + box_h) * scale))
    cv2.rectangle(upscaled, (x0, y0), (x1, y1), GUIDE_BGR, 2)
    return upscaled


def gemini_fill_crop(
    crop_bgr: np.ndarray, model_name: str | None = None
) -> np.ndarray:
    """Ask Gemini to reconstruct the crop without the CapCut overlay.

    Args:
        crop_bgr: Tight 1:1 BGR crop at native resolution.
        model_name: Override; default is ``config_store.gemini_image_model``.

    Returns:
        Filled crop resized back to the input size.

    Raises:
        RuntimeError: API returned no image after retry.
    """
    from google.genai import types

    config_store = get_module("config_store")
    client = get_module("gemini_client")
    model = model_name or config_store.gemini_image_model
    send = _guided_send_image(crop_bgr)
    last_error: Exception | None = None
    for prompt in (PROMPT, PROMPT_RETRY):
        for attempt in range(4):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[prompt, _pil_from_bgr(send)],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=types.ImageConfig(aspect_ratio="1:1"),
                    ),
                )
                filled = _bgr_from_pil(_image_from_gemini_response(response))
                if filled.shape[1] != CROP_W or filled.shape[0] != CROP_H:
                    filled = cv2.resize(
                        filled, (CROP_W, CROP_H), interpolation=cv2.INTER_AREA
                    )
                return filled
            except RuntimeError as exc:
                last_error = exc
                print(f"  retry after: {exc}", flush=True)
                break
            except Exception as exc:
                last_error = exc
                delay = min(32.0, 2.0 ** attempt)
                print(
                    f"  API error attempt {attempt + 1}: {exc}; sleep {delay:.0f}s",
                    flush=True,
                )
                time.sleep(delay)
    raise RuntimeError(str(last_error))


def align_filled_crop(original_bgr: np.ndarray, filled_bgr: np.ndarray) -> np.ndarray:
    """Register Gemini's crop to the original using pixels outside the logo.

    Image models often nudge framing by a few pixels. ECC on the foliage
    around the logo reduces a paste seam.

    Args:
        original_bgr: Original 1:1 crop.
        filled_bgr: Gemini crop already resized to the same shape.

    Returns:
        Warped filled crop, or the unaligned fill if ECC fails.
    """
    height, width = original_bgr.shape[:2]
    mask = np.ones((height, width), np.uint8) * 255
    x, y, box_w, box_h = _logo_xy_in_crop()
    mask[y : y + box_h, x : x + box_w] = 0
    original_gray = cv2.cvtColor(original_bgr, cv2.COLOR_BGR2GRAY)
    filled_gray = cv2.cvtColor(filled_bgr, cv2.COLOR_BGR2GRAY)
    warp = np.eye(2, 3, dtype=np.float32)
    try:
        criteria = (
            cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
            80,
            1e-5,
        )
        cv2.findTransformECC(
            original_gray,
            filled_gray,
            warp,
            cv2.MOTION_EUCLIDEAN,
            criteria,
            mask,
            1,
        )
        return cv2.warpAffine(
            filled_bgr,
            warp,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
    except cv2.error:
        return filled_bgr


def feathered_logo_mask(height: int, width: int) -> np.ndarray:
    """Soft mask covering only the CapCut logo box in crop space.

    Args:
        height: Crop height.
        width: Crop width.

    Returns:
        Float32 mask in ``[0, 1]`` with a Gaussian falloff at the box edge.
    """
    mask = np.zeros((height, width), np.float32)
    x, y, box_w, box_h = _logo_xy_in_crop()
    mask[y : y + box_h, x : x + box_w] = 1.0
    kernel = FEATHER_PIXELS * 2 + 1
    return cv2.GaussianBlur(mask, (kernel, kernel), FEATHER_PIXELS / 2.0)


def composite_filled_crop(
    frame_bgr: np.ndarray, filled_crop_bgr: np.ndarray
) -> np.ndarray:
    """Paste the filled logo region onto the original frame.

    Args:
        frame_bgr: Full original frame.
        filled_crop_bgr: Gemini crop aligned to the 1:1 patch.

    Returns:
        Full frame with only the logo pixels replaced.
    """
    out = frame_bgr.copy()
    crop = logo_crop(out)
    aligned = align_filled_crop(crop, filled_crop_bgr)
    mask = feathered_logo_mask(crop.shape[0], crop.shape[1])
    alpha = mask[..., None]
    blended = (crop.astype(np.float32) * (1.0 - alpha)) + (
        aligned.astype(np.float32) * alpha
    )
    out[CROP_Y : CROP_Y + CROP_H, CROP_X : CROP_X + CROP_W] = np.clip(
        blended, 0, 255
    ).astype(np.uint8)
    return out


def fill_frame(frame_bgr: np.ndarray, model_name: str | None = None) -> dict[str, np.ndarray]:
    """Gemini-fill one frame's CapCut watermark.

    Args:
        frame_bgr: Full original BGR frame.
        model_name: Optional Gemini image model id.

    Returns:
        Dict with ``filled_crop``, ``aligned_crop``, and ``composited`` frames.
    """
    crop = logo_crop(frame_bgr)
    filled_crop = gemini_fill_crop(crop, model_name=model_name)
    aligned = align_filled_crop(crop, filled_crop)
    composited = composite_filled_crop(frame_bgr, filled_crop)
    return {
        "filled_crop": filled_crop,
        "aligned_crop": aligned,
        "composited": composited,
    }
