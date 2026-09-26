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
        self._check_svg_assets(readme_text, readme_path, rep)

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
        # 1. Markdown links [text](url)
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

        # 2. Markdown images ![alt](url)
        img_matches = re.finditer(r'!\[.*?\]\((?!https?://|#)(.*?)\)', readme_text)
        for m in img_matches:
            target_path_str = m.group(1).split("#")[0].strip()
            if target_path_str:
                resolved = (self.repo_dir / target_path_str).resolve()
                if not resolved.exists():
                    report.add_finding(
                        category=FindingCategory.BROKEN_LINK,
                        severity=FindingSeverity.FATAL,
                        message=f"Referenced image does not exist on disk: '{target_path_str}'.",
                        location=f"{readme_path.name}",
                        expected="Existing image file in repo",
                        actual=target_path_str,
                        suggested_fix=f"Provide image asset '{target_path_str}' or adjust link.",
                    )

        # 3. HTML <img> tags
        html_img_matches = re.finditer(r'<img\b[^>]*\bsrc=["\'](?!https?://|#)([^"\'>]+)["\']', readme_text, re.IGNORECASE)
        for m in html_img_matches:
            target_path_str = m.group(1).split("#")[0].strip()
            if target_path_str:
                resolved = (self.repo_dir / target_path_str).resolve()
                if not resolved.exists():
                    report.add_finding(
                        category=FindingCategory.BROKEN_LINK,
                        severity=FindingSeverity.FATAL,
                        message=f"Referenced HTML <img> src does not exist on disk: '{target_path_str}'.",
                        location=f"{readme_path.name}",
                        expected="Existing image file in repo",
                        actual=target_path_str,
                        suggested_fix=f"Provide image asset '{target_path_str}' or adjust src.",
                    )

        # 4. HTML <source> tags
        html_source_matches = re.finditer(r'<source\b[^>]*\bsrcset=["\'](?!https?://|#)([^"\'>]+)["\']', readme_text, re.IGNORECASE)
        for m in html_source_matches:
            target_path_str = m.group(1).split("#")[0].strip()
            if target_path_str:
                resolved = (self.repo_dir / target_path_str).resolve()
                if not resolved.exists():
                    report.add_finding(
                        category=FindingCategory.BROKEN_LINK,
                        severity=FindingSeverity.FATAL,
                        message=f"Referenced HTML <source> srcset does not exist on disk: '{target_path_str}'.",
                        location=f"{readme_path.name}",
                        expected="Existing source asset in repo",
                        actual=target_path_str,
                        suggested_fix=f"Provide asset '{target_path_str}' or adjust srcset.",
                    )

    def _check_svg_assets(
        self,
        readme_text: str,
        readme_path: Path,
        report: VerificationReport,
    ) -> None:
        """Validate SVG assets against GitHub Camo and XML rendering constraints."""
        import xml.etree.ElementTree as ET

        svg_paths: set[Path] = set()

        # 1. Collect SVGs in assets/ directory
        assets_dir = self.repo_dir / "assets"
        if assets_dir.exists():
            for f in assets_dir.rglob("*.svg"):
                if f.is_file():
                    svg_paths.add(f.resolve())

        # 2. Collect SVGs referenced in README (markdown images, <img>, <source>)
        ref_patterns = [
            r'!\[.*?\]\((?!https?://)([^)#\s]+\.svg)[^)]*\)',
            r'<img\b[^>]*\bsrc=["\'](?!https?://)([^"\'>]+\.svg)["\']',
            r'<source\b[^>]*\bsrcset=["\'](?!https?://)([^"\'>]+\.svg)["\']',
        ]
        for pat in ref_patterns:
            for m in re.finditer(pat, readme_text, re.IGNORECASE):
                rel_ref = m.group(1)
                resolved = (self.repo_dir / rel_ref).resolve()
                if not resolved.exists() or not resolved.is_file():
                    report.add_finding(
                        category=FindingCategory.RENDER_ISSUE,
                        severity=FindingSeverity.FATAL,
                        message=f"Referenced SVG asset does not exist on disk: '{rel_ref}'.",
                        location=f"{readme_path.name}",
                        expected="Existing SVG file in repository",
                        actual="Missing asset",
                        suggested_fix=f"Generate or restore '{rel_ref}'.",
                    )
                else:
                    svg_paths.add(resolved)

        # 3. Validate each SVG
        for svg_file in sorted(svg_paths):
            try:
                rel_path = svg_file.relative_to(self.repo_dir)
            except ValueError:
                rel_path = svg_file.name

            # Check well-formedness
            try:
                tree = ET.parse(svg_file)
                root = tree.getroot()
            except ET.ParseError as e:
                report.add_finding(
                    category=FindingCategory.RENDER_ISSUE,
                    severity=FindingSeverity.FATAL,
                    message=(
                        f"GitHub rendering failure: SVG '{rel_path}' is not well-formed XML ({e}). "
                        f"GitHub Camo proxy and browser image decoders reject malformed SVGs, displaying a broken image '?' icon."
                    ),
                    location=str(rel_path),
                    expected="Well-formed XML document with properly escaped characters (&, <, >, quotes)",
                    actual=f"ParseError: {e}",
                    suggested_fix="Escape all dynamic text content with XML entities (&amp;, &lt;, &gt;, &quot;, &apos;).",
                )
                continue
            except Exception as e:
                report.add_finding(
                    category=FindingCategory.RENDER_ISSUE,
                    severity=FindingSeverity.FATAL,
                    message=f"Failed to read SVG '{rel_path}': {e}",
                    location=str(rel_path),
                    expected="Readable SVG file",
                    actual=str(e),
                    suggested_fix="Check file permissions and format.",
                )
                continue

            # Verify root element is <svg>
            tag_name = root.tag.split("}")[-1] if "}" in root.tag else root.tag
            if tag_name.lower() != "svg":
                report.add_finding(
                    category=FindingCategory.RENDER_ISSUE,
                    severity=FindingSeverity.FATAL,
                    message=f"SVG '{rel_path}' root element is '<{tag_name}>', expected '<svg>'.",
                    location=str(rel_path),
                    expected="Root element <svg>",
                    actual=f"<{tag_name}>",
                    suggested_fix="Ensure valid SVG document with <svg> root element.",
                )

            # Verify SVG namespace
            has_ns = root.tag.startswith("{http://www.w3.org/2000/svg}") or root.attrib.get("xmlns") == "http://www.w3.org/2000/svg"
            if not has_ns:
                report.add_finding(
                    category=FindingCategory.RENDER_ISSUE,
                    severity=FindingSeverity.FATAL,
                    message=f"SVG '{rel_path}' is missing standard 'xmlns=\"http://www.w3.org/2000/svg\"' namespace declaration.",
                    location=str(rel_path),
                    expected="xmlns=\"http://www.w3.org/2000/svg\"",
                    actual="Missing or non-standard namespace",
                    suggested_fix="Add xmlns=\"http://www.w3.org/2000/svg\" to <svg> root tag.",
                )

            # Verify dimensions (viewBox or width/height) to prevent 0x0 empty boxes
            has_viewbox = "viewBox" in root.attrib or "viewbox" in root.attrib
            has_dims = ("width" in root.attrib and "height" in root.attrib)
            if not has_viewbox and not has_dims:
                report.add_finding(
                    category=FindingCategory.RENDER_ISSUE,
                    severity=FindingSeverity.FATAL,
                    message=f"SVG '{rel_path}' is missing 'viewBox' or ('width' and 'height') attributes, causing 0x0 empty rendering.",
                    location=str(rel_path),
                    expected="viewBox or explicit width/height dimensions",
                    actual="No viewBox or width/height attributes",
                    suggested_fix="Add viewBox attribute (e.g. viewBox=\"0 0 800 380\") to root <svg> element.",
                )

            # Check for <foreignObject>, <script>, inline event handlers, and external references
            for el in root.iter():
                el_tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
                el_tag_lower = el_tag.lower()

                if el_tag_lower == "foreignobject":
                    report.add_finding(
                        category=FindingCategory.RENDER_ISSUE,
                        severity=FindingSeverity.FATAL,
                        message=(
                            f"GitHub sanitization rejection: SVG '{rel_path}' contains '<foreignObject>', "
                            f"which GitHub's SVG sanitizer strips or blocks for security reasons."
                        ),
                        location=str(rel_path),
                        expected="Native SVG vector elements (<text>, <rect>, <path>, <g>)",
                        actual="<foreignObject> tag detected",
                        suggested_fix="Replace <foreignObject> with native SVG <text> and <tspan> elements.",
                    )
                    break
                elif el_tag_lower == "script":
                    report.add_finding(
                        category=FindingCategory.RENDER_ISSUE,
                        severity=FindingSeverity.FATAL,
                        message=(
                            f"GitHub sanitization rejection: SVG '{rel_path}' contains '<script>', "
                            f"which GitHub's SVG sanitizer strips or blocks."
                        ),
                        location=str(rel_path),
                        expected="Static or CSS-animated SVG without scripts",
                        actual="<script> tag detected",
                        suggested_fix="Remove JavaScript from SVG assets.",
                    )
                    break
                elif el_tag_lower == "style":
                    # Check for external CSS imports which GitHub Camo blocks
                    if el.text and ("@import" in el.text or "url(http" in el.text.lower()):
                        report.add_finding(
                            category=FindingCategory.RENDER_ISSUE,
                            severity=FindingSeverity.FATAL,
                            message=f"SVG '{rel_path}' contains external stylesheet reference in <style>, blocked by GitHub Camo proxy.",
                            location=str(rel_path),
                            expected="Self-contained CSS without external imports",
                            actual="External CSS import detected",
                            suggested_fix="Remove external @import or url() from SVG <style>.",
                        )
                        break

            # Check for inline event handlers and external image/use references
            for el in root.iter():
                for attr, val in el.attrib.items():
                    if attr.lower().startswith("on"):
                        report.add_finding(
                            category=FindingCategory.RENDER_ISSUE,
                            severity=FindingSeverity.FATAL,
                            message=f"SVG '{rel_path}' contains inline event handler '{attr}', blocked by GitHub sanitizer.",
                            location=str(rel_path),
                            expected="No inline JS event handlers",
                            actual=f"Attribute '{attr}' detected",
                            suggested_fix="Remove event handlers from SVG elements.",
                        )
                        break
                    if attr.lower() in ("href", "{http://www.w3.org/1999/xlink}href") and (val.startswith("http://") or val.startswith("https://")):
                        report.add_finding(
                            category=FindingCategory.RENDER_ISSUE,
                            severity=FindingSeverity.WARNING,
                            message=f"SVG '{rel_path}' contains external reference '{val}', which may be blocked or broken by GitHub Camo.",
                            location=str(rel_path),
                            expected="Local or inline assets",
                            actual=f"External reference '{val}'",
                            suggested_fix="Embed resource data inline or use local assets.",
                        )
                        break
