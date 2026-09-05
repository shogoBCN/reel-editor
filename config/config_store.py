"""
Repository-wide configuration: paths, 9:16 canvas, and Instagram/Facebook safe zones.

This is the Locaria config store for reel-editor. Pipelines must read canvas size,
safe-zone ratios, and codec defaults from here instead of declaring script-level
globals. Client look (colours, brush, endcard) is *not* here — that lives in
``brands/<id>/brand.yaml`` so a second talking-head brand does not fork the engine.

PREFERRED ACCESS (singleton, same as adaptria_pulls):

    from modules.modules_initialiser import get_module
    config_store = get_module("config_store")
"""

from __future__ import annotations

import sys
from pathlib import Path


# Insert repo root once so ``from config.config_store`` and ``from modules...``
# work whether the caller is a pipeline two folders down or a script at root.
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


class ConfigStore:
    """Shared paths and Reels-canvas constants for every pipeline in this repo."""

    def __init__(self) -> None:
        """Populate path roots and 2026 Meta Reels chrome numbers.

        Safe-zone ratios exist because Instagram crops the top ~14% in feed and
        organic Reels UI covers the bottom third. Stickers and captions that sit
        in those bands disappear on the phone.
        """
        self.directory_path = REPOSITORY_ROOT
        self.repo_name = "reel-editor"
        self.conda_environment_name = "angelica-website"

        self.brands_directory = self.directory_path / "brands"
        self.examples_directory = self.directory_path / "examples"
        self.projects_directory = self.directory_path / "projects"
        self.templates_directory = self.directory_path / "templates"
        self.auth_directory = self.directory_path / "auth"

        # Instagram / Facebook Reels 9:16. Briefs do not currently override size;
        # if they ever do, keep these as the fallback so output stays publishable.
        self.frame_width = 1080
        self.frame_height = 1920
        self.frames_per_second = 30.0

        # Meta ad spec (~14% top, ~35% bottom, 6% sides) plus organic chrome and
        # 4:5 feed crop. 15% / 68% / 6% is the envelope that survived both.
        self.top_safe_ratio = 0.15
        self.bottom_safe_ratio = 0.68
        self.side_safe_ratio = 0.06
        self.right_rail_pixels = 120
        # Captions need a tighter inset than stickers: karaoke lines clip the
        # Reels right-rail icons if they use the full 6% gutter.
        self.caption_inset_pixels = 92
        self.caption_floor_ratio = 0.88

        self.default_fade_to_white_seconds = 0.70
        self.default_endcard_hold_seconds = 2.00
        # CRF 17 is visually lossless on talking-head; lower = huge files, higher
        # = banding on the sky behind Dra. Angélica.
        self.video_constant_rate_factor = 17
        self.audio_bitrate = "192k"

        # macOS Supplemental faces. Linux/CI needs a brand.yaml override.
        self.mac_font_round = "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf"
        self.mac_font_black = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
        self.mac_font_bold = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

    @property
    def top_safe_pixels(self) -> int:
        """Pixel Y below which hook titles and stickers may sit (below IG crop).

        Returns:
            Integer Y in the 1080×1920 canvas.
        """
        return int(self.frame_height * self.top_safe_ratio)

    @property
    def bottom_safe_pixels(self) -> int:
        """Lowest Y that still clears organic Reels UI.

        Returns:
            Integer Y in the 1080×1920 canvas.
        """
        return int(self.frame_height * self.bottom_safe_ratio)

    @property
    def side_safe_pixels(self) -> int:
        """Left/right gutter so stickers are not under the Reels rail.

        Returns:
            Integer inset from each vertical edge.
        """
        return int(self.frame_width * self.side_safe_ratio)

    @property
    def caption_max_width_pixels(self) -> int:
        """Maximum karaoke line width after both caption insets.

        Returns:
            Width in pixels (typically 896 on a 1080 canvas).
        """
        return self.frame_width - 2 * self.caption_inset_pixels

    @property
    def caption_floor_pixels(self) -> int:
        """Hard floor so a tall caption cannot sink into Reels chrome.

        Returns:
            Integer Y of the lowest allowed caption bottom edge.
        """
        return int(self.frame_height * self.caption_floor_ratio)

    def resolve_brand_directory(self, brand_id: str) -> Path:
        """Return ``brands/<brand_id>`` or fail closed if the pack is missing.

        Args:
            brand_id: Folder name under ``brands/`` (e.g. ``dra_angelica``).

        Returns:
            Absolute path to the brand pack.

        Raises:
            FileNotFoundError: No directory at that path. Copy
                ``brands/dra_angelica/`` rather than inventing a partial pack.
        """
        brand_directory = self.brands_directory / brand_id
        if not brand_directory.is_dir():
            raise FileNotFoundError(
                f"Brand pack not found: {brand_directory}. "
                f"Add brands/{brand_id}/brand.yaml (see brands/dra_angelica/)."
            )
        return brand_directory
