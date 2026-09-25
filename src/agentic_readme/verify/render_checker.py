"""Render Checker for Phase 2 Verification.

Enforces GitHub platform rendering constraints:
1. Rejects <video src="..."> tags with repo-relative paths (GitHub does NOT render these!).
2. Enforces hero GIF size limits (<= 5MB) and attachment limits (<= 10MB).
3. Ensures meaningful descriptive alt-text on all visuals.
4. Validates local file link integrity.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from agentic_readme.core.models import (
    FindingCategory,
    FindingSeverity,
    VerificationReport,
)

MAX_HERO_GIF_BYTES = 5 * 1024 * 1024       # 5 MB target
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024    # 10 MB GitHub limit


class RenderChecker:
    """Validates markdown and assets against GitHub rendering rules."""

    def __init__(self, repo_dir: Path):
        self.repo_dir = Path(repo_dir)

    def check(
        self,
        readme_path: Path,
        report: Optional[VerificationReport] = None,
    ) -> VerificationReport:
        rep = report or VerificationReport()
        readme_text = readme_path.read_text(encoding="utf-8", errors="ignore")

        self._check_relative_video_tags(readme_text, readme_path, rep)
        self._check_asset_sizes(rep)
        self._check_alt_text(readme_text, readme_path, rep)
        self._check_local_links(readme_text, readme_path, rep)

        return rep

    def _check_relative_video_tags(
        self,
        readme_text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        """GitHub fails to render HTML5 <video> tags pointing to relative repository paths."""
        # Find <video ... src="assets/..."> or <video ...><source src="assets/...">
        video_src_matches = re.finditer(r'<video[^>]*\bsrc=["\']([^"\']+)["\']', readme_text, re.IGNORECASE)
        for m in video_src_matches:
            src = m.group(1)
            if not src.startswith("http://") and not src.startswith("https://"):
                report.add_finding(
                    category=FindingCategory.RENDER_ISSUE,
                    severity=FindingSeverity.FATAL,
                    message=(
                        f"GitHub rendering failure: <video src='{src}'> with a repo-relative path "
                        f"will not render on GitHub. GitHub disables relative video playback."
                    ),
                    location=f"{readme_path.name} (line around index {m.start()})",
                    expected="GIF preview linking to external MP4 or release asset",
                    actual=f"<video src='{src}'>",
                    suggested_fix="Replace <video> tag with a GIF preview linking to MP4 or user-attachments URL.",
                )

        # Also check <source src="..."> inside <video>
        source_matches = re.finditer(r'<video[\s\S]*?<source[^>]*\bsrc=["\']([^"\']+)["\'][\s\S]*?</video>', readme_text, re.IGNORECASE)
        for m in source_matches:
            src = m.group(1)
            if not src.startswith("http://") and not src.startswith("https://"):
                report.add_finding(
                    category=FindingCategory.RENDER_ISSUE,
                    severity=FindingSeverity.FATAL,
                    message=(
                        f"GitHub rendering failure: <source src='{src}'> inside <video> with repo path "
                        f"will not render on GitHub."
                    ),
                    location=f"{readme_path.name}",
                    expected="GIF preview linking to external MP4",
                    actual=f"<source src='{src}'>",
                    suggested_fix="Use a GIF preview image wrapped in an anchor link pointing to the MP4 file.",
                )

    def _check_asset_sizes(self, report: VerificationReport) -> None:
        """Ensure media assets obey platform size ceilings."""
        assets_dir = self.repo_dir / "assets"
        if not assets_dir.exists():
            return

        for asset_file in assets_dir.rglob("*"):
            if not asset_file.is_file():
                continue

            size = asset_file.stat().st_size
            rel_path = asset_file.relative_to(self.repo_dir)

            if asset_file.suffix.lower() == ".gif":
                if size > MAX_HERO_GIF_BYTES:
                    report.add_finding(
                        category=FindingCategory.SIZE_LIMIT,
                        severity=FindingSeverity.WARNING,
                        message=f"Hero GIF {rel_path} is {size / (1024*1024):.2f}MB, exceeding recommended 5MB ceiling.",
                        location=str(rel_path),
                        expected="<= 5.0 MB",
                        actual=f"{size / (1024*1024):.2f} MB",
                        suggested_fix="Optimize GIF framerate/dimensions with gifsicle or ffmpeg to stay under 5MB.",
                    )
            elif size > MAX_ATTACHMENT_BYTES:
                report.add_finding(
                    category=FindingCategory.SIZE_LIMIT,
                    severity=FindingSeverity.FATAL,
                    message=f"Asset {rel_path} ({size / (1024*1024):.2f}MB) exceeds GitHub 10MB upload limit.",
                    location=str(rel_path),
                    expected="<= 10.0 MB",
                    actual=f"{size / (1024*1024):.2f} MB",
                    suggested_fix="Compress media asset or host externally.",
                )

    def _check_alt_text(
        self,
        readme_text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        """Check for missing or empty alt-text on images."""
        # Check markdown images: ![alt](url)
        md_images = re.finditer(r'!\[(.*?)\]\((.*?)\)', readme_text)
        for m in md_images:
            alt = m.group(1).strip()
            url = m.group(2).strip()
            if not alt or alt.lower() in ("image", "img", "demo", "picture"):
                report.add_finding(
                    category=FindingCategory.RENDER_ISSUE,
                    severity=FindingSeverity.WARNING,
                    message=f"Image ({url}) has missing or vacuous alt text ('{alt}').",
                    location=f"{readme_path.name}",
                    expected="Descriptive alt text stating what the image shows",
                    actual=f"alt='{alt}'",
                    suggested_fix="Provide descriptive alt text for accessibility and SEO.",
                )

        # Check HTML <img> tags, allowing quotes that contain '>'
        img_tags = re.finditer(r'<img\b(?:"[^"]*"|\'[^\']*\'|[^>"\'])*>', readme_text, re.IGNORECASE)
        for m in img_tags:
            tag = m.group(0)
            alt_m = re.search(r'\balt=["\']([^"\']*)["\']', tag, re.IGNORECASE)
            if not alt_m or not alt_m.group(1).strip():
                # Badges with shields.io are often decorative, but hero images must have alt
                if "shields.io" not in tag:
                    report.add_finding(
                        category=FindingCategory.RENDER_ISSUE,
                        severity=FindingSeverity.WARNING,
                        message=f"HTML <img> tag is missing an alt attribute: {tag[:60]}...",
                        location=f"{readme_path.name}",
                        expected="alt attribute with descriptive summary",
                        actual="Missing alt attribute",
                        suggested_fix="Add descriptive alt attribute to <img>.",
                    )

    def _check_local_links(
        self,
        readme_text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        """Check that referenced local files and assets exist on disk."""
        link_matches = re.finditer(r'\[.*?\]\((?!https?://|#)(.*?)\)', readme_text)
        for m in link_matches:
            target_path_str = m.group(1).split("#")[0].strip()
            if target_path_str:
                resolved = (self.repo_dir / target_path_str).resolve()
                if not resolved.exists():
                    report.add_finding(
                        category=FindingCategory.BROKEN_LINK,
                        severity=FindingSeverity.WARNING,
                        message=f"Referenced local path does not exist on disk: '{target_path_str}'.",
                        location=f"{readme_path.name}",
                        expected="Existing file or directory in repo",
                        actual=target_path_str,
                        suggested_fix=f"Create '{target_path_str}' or adjust the link target.",
                    )
