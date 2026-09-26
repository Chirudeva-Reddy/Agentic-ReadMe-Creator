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
