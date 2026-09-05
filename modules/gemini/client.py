"""Gemini API client from ``auth/auth-config.json`` + config_store endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.genai.client import Client

    from config.config_store import ConfigStore


def build_gemini_client(config_store: "ConfigStore") -> "Client":
    """Construct a Gemini SDK client (speech now; image/music later).

    The API key is read from ``auth/auth-config.json``. Model IDs and the
    AI Studio endpoint live on ``config_store`` so image pipelines can reuse
    this helper without copying secrets.

    Args:
        config_store: Shared store with auth path, base URL, and timeout.

    Returns:
        A ``google.genai.Client``.

    Raises:
        FileNotFoundError: Auth file missing.
        ImportError: ``google-genai`` is not installed.
        KeyError: ``gemini.api_key`` missing from auth config.
        ValueError: Placeholder or empty API key.
    """
    try:
        from google import genai
    except ImportError as exc:
        raise ImportError(
            "google-genai is not installed in this environment. "
            "pip install google-genai  (conda env: angelica-website)"
        ) from exc

    return genai.Client(
        api_key=config_store.gemini_api_key(),
        http_options={
            "base_url": config_store.gemini_api_base_url,
            "api_version": config_store.gemini_api_version,
            "timeout": config_store.gemini_http_timeout_milliseconds,
        },
    )
