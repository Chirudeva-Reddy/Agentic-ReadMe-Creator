"""Check that the README will actually display correctly on GitHub.

check_rendering(readme_path) catches things that look fine locally but break on GitHub:
  - <video src="assets/..."> with a repo path: GitHub won't play it
  - GIFs over 5 MB and any asset over GitHub's 10 MB limit
  - images with missing or meaningless alt text
  - links and images pointing at files that don't exist
  - SVGs that GitHub's image proxy rejects (malformed XML, <script>, <foreignObject>, ...)
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from agentic_readme.models import FindingCategory, FindingSeverity, VerificationReport
from agentic_readme.rules import MAX_ATTACHMENT_BYTES, MAX_HERO_GIF_BYTES

FATAL = FindingSeverity.FATAL
WARNING = FindingSeverity.WARNING
RENDER = FindingCategory.RENDER_ISSUE


def check_rendering(readme_path: Path, report: VerificationReport | None = None) -> VerificationReport:
    if report is None:
        report = VerificationReport()
    text = readme_path.read_text(encoding="utf-8", errors="ignore")
    project_dir = readme_path.parent
    name = readme_path.name

    _video_tags(text, name, report)
    _asset_sizes(project_dir, report)
    _alt_text(text, name, report)
    _local_links(text, name, project_dir, report)
    _svg_files(text, name, project_dir, report)
    return report


def _is_web_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def _video_tags(text: str, name: str, report: VerificationReport) -> None:
    """GitHub doesn't play <video> tags that point at a file inside the repo."""
    for match in re.finditer(r'<video[^>]*\bsrc=["\']([^"\']+)["\']', text, re.IGNORECASE):
        src = match.group(1)
        if not _is_web_url(src):
            report.add_finding(
                RENDER, FATAL,
                f"GitHub rendering failure: <video src='{src}'> with a repo-relative path "
                f"will not render on GitHub. GitHub disables relative video playback.",
                location=f"{name} (line around index {match.start()})",
                expected="GIF preview linking to external MP4 or release asset",
                actual=f"<video src='{src}'>",
                suggested_fix="Replace <video> tag with a GIF preview linking to MP4 or user-attachments URL.",
            )

    inner_source = r'<video[\s\S]*?<source[^>]*\bsrc=["\']([^"\']+)["\'][\s\S]*?</video>'
    for match in re.finditer(inner_source, text, re.IGNORECASE):
        src = match.group(1)
        if not _is_web_url(src):
            report.add_finding(
                RENDER, FATAL,
                f"GitHub rendering failure: <source src='{src}'> inside <video> with repo path "
                f"will not render on GitHub.",
                location=name,
                expected="GIF preview linking to external MP4",
                actual=f"<source src='{src}'>",
                suggested_fix="Use a GIF preview image wrapped in an anchor link pointing to the MP4 file.",
            )


def _asset_sizes(project_dir: Path, report: VerificationReport) -> None:
    assets = project_dir / "assets"
    if not assets.exists():
        return
    for path in assets.rglob("*"):
        if not path.is_file():
            continue
        size = path.stat().st_size
        megabytes = f"{size / (1024 * 1024):.2f}"
        relative = path.relative_to(project_dir)
        if path.suffix.lower() == ".gif":
            if size > MAX_HERO_GIF_BYTES:
                report.add_finding(
                    FindingCategory.SIZE_LIMIT, WARNING,
                    f"Hero GIF {relative} is {megabytes}MB, exceeding recommended 5MB ceiling.",
                    location=str(relative), expected="<= 5.0 MB", actual=f"{megabytes} MB",
                    suggested_fix="Optimize GIF framerate/dimensions with gifsicle or ffmpeg to stay under 5MB.",
                )
        elif size > MAX_ATTACHMENT_BYTES:
            report.add_finding(
                FindingCategory.SIZE_LIMIT, FATAL,
                f"Asset {relative} ({megabytes}MB) exceeds GitHub 10MB upload limit.",
                location=str(relative), expected="<= 10.0 MB", actual=f"{megabytes} MB",
                suggested_fix="Compress media asset or host externally.",
            )


def _alt_text(text: str, name: str, report: VerificationReport) -> None:
    """Every image needs alt text that says what it shows."""
    for match in re.finditer(r'!\[(.*?)\]\((.*?)\)', text):  # Markdown ![alt](url)
        alt, url = match.group(1).strip(), match.group(2).strip()
        if not alt or alt.lower() in ("image", "img", "demo", "picture"):
            report.add_finding(
                RENDER, WARNING, f"Image ({url}) has missing or vacuous alt text ('{alt}').",
                location=name, expected="Descriptive alt text stating what the image shows",
                actual=f"alt='{alt}'", suggested_fix="Provide descriptive alt text for accessibility and SEO.",
            )

    # HTML <img> tags (the pattern allows quoted attribute values that contain '>')
    for match in re.finditer(r'<img\b(?:"[^"]*"|\'[^\']*\'|[^>"\'])*>', text, re.IGNORECASE):
        tag = match.group(0)
        alt = re.search(r'\balt=["\']([^"\']*)["\']', tag, re.IGNORECASE)
        # shields.io badges are decorative, so they may skip alt text
        if (not alt or not alt.group(1).strip()) and "shields.io" not in tag:
            report.add_finding(
                RENDER, WARNING, f"HTML <img> tag is missing an alt attribute: {tag[:60]}...",
                location=name, expected="alt attribute with descriptive summary",
                actual="Missing alt attribute", suggested_fix="Add descriptive alt attribute to <img>.",
            )


# Ways a README points at a local file:
# (pattern capturing the path, what it is, severity, what was expected, how to fix it)
LOCAL_REFERENCES = [
    (re.compile(r'\[.*?\]\((?!https?://|#)(.*?)\)'), "local path", WARNING,
     "Existing file or directory in repo", "Create '{}' or adjust the link target."),
    (re.compile(r'!\[.*?\]\((?!https?://|#)(.*?)\)'), "image", FATAL,
     "Existing image file in repo", "Provide image asset '{}' or adjust link."),
    (re.compile(r'<img\b[^>]*\bsrc=["\'](?!https?://|#)([^"\'>]+)["\']', re.IGNORECASE), "HTML <img> src", FATAL,
     "Existing image file in repo", "Provide image asset '{}' or adjust src."),
    (re.compile(r'<source\b[^>]*\bsrcset=["\'](?!https?://|#)([^"\'>]+)["\']', re.IGNORECASE), "HTML <source> srcset", FATAL,
     "Existing source asset in repo", "Provide asset '{}' or adjust srcset."),
]


def _local_links(text: str, name: str, project_dir: Path, report: VerificationReport) -> None:
    for pattern, what, severity, expected, fix in LOCAL_REFERENCES:
        for match in pattern.finditer(text):
            target = match.group(1).split("#")[0].strip()
            if target and not (project_dir / target).resolve().exists():
                report.add_finding(
                    FindingCategory.BROKEN_LINK, severity,
                    f"Referenced {what} does not exist on disk: '{target}'.",
                    location=name, expected=expected, actual=target, suggested_fix=fix.format(target),
                )


SVG_REFERENCES = [
    r'!\[.*?\]\((?!https?://)([^)#\s]+\.svg)[^)]*\)',
    r'<img\b[^>]*\bsrc=["\'](?!https?://)([^"\'>]+\.svg)["\']',
    r'<source\b[^>]*\bsrcset=["\'](?!https?://)([^"\'>]+\.svg)["\']',
]


def _svg_files(text: str, name: str, project_dir: Path, report: VerificationReport) -> None:
    """Check every SVG in assets/ and every SVG the README references."""
    svgs: set[Path] = set()
    assets = project_dir / "assets"
    if assets.exists():
        svgs.update(f.resolve() for f in assets.rglob("*.svg") if f.is_file())

    for pattern in SVG_REFERENCES:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            reference = match.group(1)
            path = (project_dir / reference).resolve()
            if path.is_file():
                svgs.add(path)
            else:
                report.add_finding(
                    RENDER, FATAL, f"Referenced SVG asset does not exist on disk: '{reference}'.",
                    location=name, expected="Existing SVG file in repository", actual="Missing asset",
                    suggested_fix=f"Generate or restore '{reference}'.",
                )

    for svg in sorted(svgs):
        _check_svg(svg, project_dir, report)


def _tag(element: ET.Element) -> str:
    """'{http://www.w3.org/2000/svg}rect' -> 'rect'"""
    return element.tag.split("}")[-1] if "}" in element.tag else element.tag


def _check_svg(svg: Path, project_dir: Path, report: VerificationReport) -> None:
    try:
        relative = str(svg.relative_to(project_dir))
    except ValueError:
        relative = svg.name

    def problem(message, expected, actual, fix, severity=FATAL):
        report.add_finding(RENDER, severity, message, location=relative,
                           expected=expected, actual=actual, suggested_fix=fix)

    try:
        root = ET.parse(svg).getroot()
    except ET.ParseError as e:
        problem(f"GitHub rendering failure: SVG '{relative}' is not well-formed XML ({e}). "
                f"GitHub Camo proxy and browser image decoders reject malformed SVGs, displaying a broken image '?' icon.",
                "Well-formed XML document with properly escaped characters (&, <, >, quotes)", f"ParseError: {e}",
                "Escape all dynamic text content with XML entities (&amp;, &lt;, &gt;, &quot;, &apos;).")
        return
    except Exception as e:
        problem(f"Failed to read SVG '{relative}': {e}", "Readable SVG file", str(e),
                "Check file permissions and format.")
        return

    root_tag = _tag(root)
    if root_tag.lower() != "svg":
        problem(f"SVG '{relative}' root element is '<{root_tag}>', expected '<svg>'.",
                "Root element <svg>", f"<{root_tag}>", "Ensure valid SVG document with <svg> root element.")

    if not (root.tag.startswith("{http://www.w3.org/2000/svg}") or root.attrib.get("xmlns") == "http://www.w3.org/2000/svg"):
        problem(f"SVG '{relative}' is missing standard 'xmlns=\"http://www.w3.org/2000/svg\"' namespace declaration.",
                "xmlns=\"http://www.w3.org/2000/svg\"", "Missing or non-standard namespace",
                "Add xmlns=\"http://www.w3.org/2000/svg\" to <svg> root tag.")

    has_viewbox = "viewBox" in root.attrib or "viewbox" in root.attrib
    has_size = "width" in root.attrib and "height" in root.attrib
    if not has_viewbox and not has_size:
        problem(f"SVG '{relative}' is missing 'viewBox' or ('width' and 'height') attributes, causing 0x0 empty rendering.",
                "viewBox or explicit width/height dimensions", "No viewBox or width/height attributes",
                "Add viewBox attribute (e.g. viewBox=\"0 0 800 380\") to root <svg> element.")

    # Elements GitHub's sanitizer strips (report the first one found).
    for element in root.iter():
        tag = _tag(element).lower()
        if tag == "foreignobject":
            problem(f"GitHub sanitization rejection: SVG '{relative}' contains '<foreignObject>', "
                    f"which GitHub's SVG sanitizer strips or blocks for security reasons.",
                    "Native SVG vector elements (<text>, <rect>, <path>, <g>)", "<foreignObject> tag detected",
                    "Replace <foreignObject> with native SVG <text> and <tspan> elements.")
            break
        if tag == "script":
            problem(f"GitHub sanitization rejection: SVG '{relative}' contains '<script>', "
                    f"which GitHub's SVG sanitizer strips or blocks.",
                    "Static or CSS-animated SVG without scripts", "<script> tag detected",
                    "Remove JavaScript from SVG assets.")
            break
        if tag == "style" and element.text and ("@import" in element.text or "url(http" in element.text.lower()):
            problem(f"SVG '{relative}' contains external stylesheet reference in <style>, blocked by GitHub Camo proxy.",
                    "Self-contained CSS without external imports", "External CSS import detected",
                    "Remove external @import or url() from SVG <style>.")
            break

    # Inline event handlers and links to outside resources (first one per element).
    for element in root.iter():
        for attribute, value in element.attrib.items():
            if attribute.lower().startswith("on"):
                problem(f"SVG '{relative}' contains inline event handler '{attribute}', blocked by GitHub sanitizer.",
                        "No inline JS event handlers", f"Attribute '{attribute}' detected",
                        "Remove event handlers from SVG elements.")
                break
            if attribute.lower() in ("href", "{http://www.w3.org/1999/xlink}href") and _is_web_url(value):
                problem(f"SVG '{relative}' contains external reference '{value}', which may be blocked or broken by GitHub Camo.",
                        "Local or inline assets", f"External reference '{value}'",
                        "Embed resource data inline or use local assets.", WARNING)
                break
