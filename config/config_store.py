"""
Video-editor config store: repository paths, Reels canvas, and safe-zone constants.

All pipelines should read canvas and path defaults from here rather than declaring
script-level globals. Brand colours, fonts, and sticker assets live in
``brands/<id>/brand.yaml`` — this store only holds values that are true for every
brand (9:16 Reels frame, Meta 2026 chrome, conda env name).

PREFERRED ACCESS:
    from modules.modules_initialiser import get_module
    config_store = get_module("config_store")
"""

from __future__ import annotations

import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


class ConfigStore:
    """Repository-wide configuration for the reel compose toolkit."""

    def __init__(self) -> None:
        self.directory_path = _REPO_ROOT
        self.repo_name = "video-editor"
        self.conda_env_name = "angelica-website"

        self.brands_dir = self.directory_path / "brands"
        self.examples_dir = self.directory_path / "examples"
        self.projects_dir = self.directory_path / "projects"
        self.templates_dir = self.directory_path / "templates"
        self.auth_dir = self.directory_path / "auth"

        ## 9:16 Instagram / Facebook Reels (2026). Briefs may override per project.
        self.frame_width = 1080
        self.frame_height = 1920
        self.fps = 30.0

        ## Meta ad spec: keep clear top ~14%, bottom ~35%, sides 6%.
        ## Organic Reels UI + 4:5 feed crop sit in the same bands.
        self.top_safe_ratio = 0.15
        self.bottom_safe_ratio = 0.68
        self.side_safe_ratio = 0.06
        self.right_rail_px = 120
        self.caption_inset_px = 92
        self.caption_floor_ratio = 0.88

        self.default_fade_white_s = 0.70
        self.default_endcard_hold_s = 2.00
        self.video_crf = 17
        self.audio_bitrate = "192k"

        self.mac_font_round = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
        self.mac_font_black = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
        self.mac_font_bold = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

    @property
    def top_safe_px(self) -> int:
        return int(self.frame_height * self.top_safe_ratio)

    @property
    def bottom_safe_px(self) -> int:
        return int(self.frame_height * self.bottom_safe_ratio)

    @property
    def side_safe_px(self) -> int:
        return int(self.frame_width * self.side_safe_ratio)

    @property
    def caption_max_width_px(self) -> int:
        return self.frame_width - 2 * self.caption_inset_px

    @property
    def caption_floor_px(self) -> int:
        return int(self.frame_height * self.caption_floor_ratio)

    def resolve_brand_dir(self, brand_id: str) -> Path:
        """Return ``brands/<brand_id>`` or raise if the pack is missing."""
        brand_dir = self.brands_dir / brand_id
        if not brand_dir.is_dir():
            raise FileNotFoundError(
                f"Brand pack not found: {brand_dir}. "
                f"Add brands/{brand_id}/brand.yaml (see brands/dra_angelica/)."
            )
        return brand_dir
