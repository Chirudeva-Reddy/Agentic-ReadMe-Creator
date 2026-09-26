"""Tests for Phase 2 Render Checker: GitHub constraints and media validation."""

from pathlib import Path
from agentic_readme.core.models import FindingCategory, FindingSeverity, VerificationReport
from agentic_readme.verify.render_checker import RenderChecker


def test_render_checker_catches_relative_video_tag(tmp_path: Path):
    """Catches ClaimLens rendering failure:

    <video src="assets/claimlens-demo.mp4"> will not render in GitHub markdown.
    """
    readme = tmp_path / "README.md"
    readme.write_text("""# ClaimLens Showcase
<details>
<summary>Watch Demo</summary>
<video src="assets/claimlens-demo.mp4" controls width="100%">
</video>
</details>
""", encoding="utf-8")

    checker = RenderChecker(tmp_path)
    report = checker.check(readme)

    video_findings = [f for f in report.findings if f.category == FindingCategory.RENDER_ISSUE and "<video" in f.actual]
    assert len(video_findings) >= 1
    assert video_findings[0].severity == FindingSeverity.FATAL
    assert "will not render on GitHub" in video_findings[0].message


def test_render_checker_accepts_gif_preview_linking_to_mp4(tmp_path: Path):
    """Verifies that the body2health pattern (GIF preview -> link to MP4) passes."""
    readme = tmp_path / "README.md"
    readme.write_text("""# Showcase
<p align="center">
  <a href="https://github.com/org/repo/releases/download/v1.0/demo.mp4">
    <img alt="Terminal run showing 3-second instant photo triage" src="https://example.com/hero.gif" width="760">
  </a>
</p>
""", encoding="utf-8")

    checker = RenderChecker(tmp_path)
    report = checker.check(readme)

    video_findings = [f for f in report.findings if f.category == FindingCategory.RENDER_ISSUE]
    assert len(video_findings) == 0


def test_render_checker_flags_vacuous_alt_text(tmp_path: Path):
    readme = tmp_path / "README.md"
    readme.write_text("""# Project
![demo](assets/demo.gif)
<img src="assets/arch.svg">
""", encoding="utf-8")

    checker = RenderChecker(tmp_path)
    report = checker.check(readme)

    alt_findings = [f for f in report.findings if "alt" in f.message.lower()]
    assert len(alt_findings) >= 2


def test_render_checker_flags_oversized_gif(tmp_path: Path):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    big_gif = assets_dir / "big.gif"
    # Create file slightly larger than 5MB
    big_gif.write_bytes(b"\x00" * (5 * 1024 * 1024 + 1024))

    readme = tmp_path / "README.md"
    readme.write_text("# Project\n", encoding="utf-8")

    checker = RenderChecker(tmp_path)
    report = checker.check(readme)

    size_findings = [f for f in report.findings if f.category == FindingCategory.SIZE_LIMIT]
    assert len(size_findings) == 1
    assert "exceeding recommended 5MB ceiling" in size_findings[0].message


def test_render_checker_catches_malformed_svg(tmp_path: Path):
    """Verifies that malformed XML in SVGs is detected as a fatal render issue."""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    bad_svg = assets_dir / "bad.svg"
    # Write invalid XML (unclosed tag / unescaped ampersand)
    bad_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>$ git clone <repo> && cd foo</text></svg>', encoding="utf-8")

    readme = tmp_path / "README.md"
    readme.write_text('# Project\n<img alt="Hero demo" src="assets/bad.svg" width="760">\n', encoding="utf-8")

    checker = RenderChecker(tmp_path)
    report = checker.check(readme)

    svg_findings = [f for f in report.findings if f.category == FindingCategory.RENDER_ISSUE and "not well-formed XML" in f.message]
    assert len(svg_findings) == 1
    assert svg_findings[0].severity == FindingSeverity.FATAL


def test_render_checker_catches_foreign_object_in_svg(tmp_path: Path):
    """Verifies that foreignObject in SVGs is detected as a fatal render issue."""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    fo_svg = assets_dir / "fo.svg"
    fo_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><foreignObject width="100" height="100"><div>hello</div></foreignObject></svg>', encoding="utf-8")

    readme = tmp_path / "README.md"
    readme.write_text('# Project\n<img alt="Hero demo" src="assets/fo.svg" width="760">\n', encoding="utf-8")

    checker = RenderChecker(tmp_path)
    report = checker.check(readme)

    fo_findings = [f for f in report.findings if f.category == FindingCategory.RENDER_ISSUE and "<foreignObject>" in f.message]
    assert len(fo_findings) == 1
    assert fo_findings[0].severity == FindingSeverity.FATAL


def test_render_checker_accepts_valid_svg(tmp_path: Path):
    """Verifies that well-formed SVGs pass verification."""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    good_svg = assets_dir / "good.svg"
    good_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 380" width="800" height="380"><rect width="100%" height="100%" fill="#1e1e2e"/><text x="30" y="80">Clean SVG</text></svg>', encoding="utf-8")

    readme = tmp_path / "README.md"
    readme.write_text('# Project\n<img alt="Hero demo" src="assets/good.svg" width="760">\n', encoding="utf-8")

    checker = RenderChecker(tmp_path)
    report = checker.check(readme)

    render_findings = [f for f in report.findings if f.category == FindingCategory.RENDER_ISSUE]
    assert len(render_findings) == 0


def test_render_checker_catches_missing_referenced_svg(tmp_path: Path):
    """Verifies that missing SVG referenced in <img> or <source> is flagged."""
    readme = tmp_path / "README.md"
    readme.write_text('# Project\n<picture><source srcset="assets/missing-static.svg"><img alt="Hero demo" src="assets/missing.svg" width="760"></picture>\n', encoding="utf-8")

    checker = RenderChecker(tmp_path)
    report = checker.check(readme)

    missing_findings = [f for f in report.findings if "does not exist on disk" in f.message]
    assert len(missing_findings) >= 2


def test_render_checker_catches_svg_missing_namespace(tmp_path: Path):
    """Verifies that an SVG missing xmlns is detected."""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    no_ns_svg = assets_dir / "no_ns.svg"
    no_ns_svg.write_text('<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="40"/></svg>', encoding="utf-8")

    readme = tmp_path / "README.md"
    readme.write_text('# Project\n<img alt="Hero" src="assets/no_ns.svg">\n', encoding="utf-8")

    checker = RenderChecker(tmp_path)
    report = checker.check(readme)

    ns_findings = [f for f in report.findings if "missing standard 'xmlns" in f.message]
    assert len(ns_findings) == 1


def test_render_checker_catches_svg_missing_dimensions(tmp_path: Path):
    """Verifies that an SVG without viewBox or dimensions is detected."""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    no_dim_svg = assets_dir / "no_dim.svg"
    no_dim_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40"/></svg>', encoding="utf-8")

    readme = tmp_path / "README.md"
    readme.write_text('# Project\n<img alt="Hero" src="assets/no_dim.svg">\n', encoding="utf-8")

    checker = RenderChecker(tmp_path)
    report = checker.check(readme)

    dim_findings = [f for f in report.findings if "missing 'viewBox' or ('width' and 'height')" in f.message]
    assert len(dim_findings) == 1


def test_render_checker_catches_external_css_import(tmp_path: Path):
    """Verifies that @import in SVG style tags is detected and rejected."""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    ext_css_svg = assets_dir / "ext_css.svg"
    ext_css_svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><style>@import url("https://fonts.googleapis.com/css?family=Roboto");</style><text x="10" y="20">Hi</text></svg>', encoding="utf-8")

    readme = tmp_path / "README.md"
    readme.write_text('# Project\n<img alt="Hero" src="assets/ext_css.svg">\n', encoding="utf-8")

    checker = RenderChecker(tmp_path)
    report = checker.check(readme)

    ext_findings = [f for f in report.findings if "external stylesheet reference" in f.message]
    assert len(ext_findings) == 1


def test_render_checker_accepts_picture_with_static_and_animated_svg(tmp_path: Path):
    """Verifies that a <picture> element referencing valid static and animated SVGs passes."""
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    anim_svg = assets_dir / "hero.svg"
    static_svg = assets_dir / "hero-static.svg"

    anim_svg.write_text('<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 800 380" width="800" height="380"><style>@keyframes blink { 0% { opacity: 1; } }</style><rect width="100%" height="100%" fill="#1e1e2e"/><text x="30" y="80">Animated</text></svg>', encoding="utf-8")
    static_svg.write_text('<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 800 380" width="800" height="380"><rect width="100%" height="100%" fill="#1e1e2e"/><text x="30" y="80">Static</text></svg>', encoding="utf-8")

    readme = tmp_path / "README.md"
    readme.write_text('# Project\n<picture><source media="(prefers-reduced-motion: reduce)" srcset="assets/hero-static.svg"><img alt="Hero demo" src="assets/hero.svg" width="760"></picture>\n', encoding="utf-8")

    checker = RenderChecker(tmp_path)
    report = checker.check(readme)

    assert report.fatal_count == 0
    assert len([f for f in report.findings if f.category == FindingCategory.RENDER_ISSUE]) == 0
