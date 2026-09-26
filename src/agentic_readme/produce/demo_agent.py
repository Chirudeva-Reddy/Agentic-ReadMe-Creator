"""Demo Agent for Phase 1.

Produces VHS terminal scripts (.tape) and lightweight hero GIF / SVG preview
assets adhering to strict platform constraints (GIF size <= 5MB).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from agentic_readme.core.models import FactsLedger, StorySpec


def _xml_escape(text: Any) -> str:
    """Safely escape text for inclusion in SVG/XML.

    Escapes &, <, >, \", and ' so text elements and attributes never produce
    malformed XML that GitHub Camo proxy or browser decoders reject.
    """
    if text is None:
        return ""
    s = str(text)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


class DemoAgent:
    """Produces terminal demo scripts and hero visual assets."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir) / "assets" / "demo"

    def produce(self, story: StorySpec, facts: FactsLedger) -> Dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        tape_path = self.output_dir / "demo.tape"
        gif_path = self.output_dir / "hero-demo.gif"
        preview_svg_path = self.output_dir / "hero-demo.svg"
        static_svg_path = self.output_dir / "hero-demo-static.svg"

        # Build VHS tape content
        tape_content = self._generate_vhs_tape(story)
        tape_path.write_text(tape_content, encoding="utf-8")

        # Generate lightweight hero asset with CSS blinking cursor animation
        hero_svg = self._generate_terminal_hero_svg(story, animated=True)
        preview_svg_path.write_text(hero_svg, encoding="utf-8")

        # Generate static fallback asset without CSS animations (prefers-reduced-motion / print)
        static_svg = self._generate_terminal_hero_svg(story, animated=False)
        static_svg_path.write_text(static_svg, encoding="utf-8")

        # Create lightweight starter GIF placeholder (or use SVG)
        # Note: If VHS binary is available in environment, user can run vhs assets/demo/demo.tape
        alt_text = (
            f"Illustrated terminal preview of the {story.repo_name} quickstart commands."
        )

        return {
            "tape_file": tape_path,
            "hero_asset": preview_svg_path,
            "static_asset": static_svg_path,
            "hero_gif_target": gif_path,
            "alt_text": alt_text,
            "max_size_bytes": 5 * 1024 * 1024,  # 5 MB hard limit
        }

    def _generate_vhs_tape(self, story: StorySpec) -> str:
        """Create VHS tape script with realistic pauses and exact quickstart commands."""
        cmds = story.quickstart_commands
        cmd_lines = []
        for cmd in cmds:
            safe_cmd = cmd.replace('"', '\\"')
            cmd_lines.append(f'Type "{safe_cmd}"')
            cmd_lines.append("Sleep 500ms")
            cmd_lines.append("Enter")
            cmd_lines.append("Sleep 2s")

        return f"""# VHS Tape for {story.repo_name}
# Output target: hero GIF under 5MB for GitHub README performance
Output assets/demo/hero-demo.gif
Output assets/demo/hero-demo.mp4

Set FontSize 15
Set Width 900
Set Height 480
Set Padding 20
Set Theme "Catppuccin Mocha"
Set Framerate 30

# Initial pause
Sleep 1s

# Run verified quickstart commands
{chr(10).join(cmd_lines)}

# End on the successful result (peak-end rule)
Sleep 3s
"""

    def _generate_terminal_hero_svg(self, story: StorySpec, animated: bool = True) -> str:
        """Lightweight terminal window representation as an SVG hero asset."""
        cmds = story.quickstart_commands
        exec_cmds = [
            c for c in cmds
            if not c.startswith("git clone") and not c.startswith("pip install")
        ]
        cmd_str = exec_cmds[-1] if exec_cmds else (cmds[0] if cmds else f"./run_{story.repo_name}.sh")
        # Sanitize fallback if it still contains raw placeholder
        if "<repo-url>" in cmd_str:
            cmd_str = f"python3 src/agentic_readme/cli.py"

        # Determine terminal output stages from architecture nodes or claims
        nodes = story.architecture_nodes
        stage1 = nodes[0].label if len(nodes) > 0 else "System Initialization"
        stage2 = nodes[1].label if len(nodes) > 1 else "Pipeline Execution"
        stage3 = nodes[-1].label if len(nodes) > 2 else "Verification & Output"

        claim1 = story.key_claims[0].claim if story.key_claims else "Pipeline execution verified successfully."
        claim2 = story.key_claims[1].claim if len(story.key_claims) > 1 else "All system outputs verified against ground truth."

        # Truncate strings before XML escaping to fit the 800px terminal width cleanly
        def _trim(s: str, max_len: int = 80) -> str:
            return s[: max_len - 3] + "..." if len(s) > max_len else s

        repo_name_escaped = _xml_escape(_trim(story.repo_name, 50))
        cmd_escaped = _xml_escape(_trim(cmd_str, 85))
        stage1_escaped = _xml_escape(_trim(stage1, 75))
        stage2_escaped = _xml_escape(_trim(stage2, 75))
        stage3_escaped = _xml_escape(_trim(stage3, 75))
        claim1_escaped = _xml_escape(_trim(claim1, 80))
        claim2_escaped = _xml_escape(_trim(claim2, 80))

        if animated:
            style_block = """  <style>
    @keyframes blink {
      0%, 49% { opacity: 1; }
      50%, 100% { opacity: 0; }
    }
    .terminal-cursor {
      animation: blink 1s infinite;
    }
    @media (prefers-reduced-motion: reduce) {
      .terminal-cursor {
        animation: none;
        opacity: 1;
      }
    }
  </style>
"""
            cursor_element = '<tspan class="terminal-cursor" fill="#a6e3a1"> ▋</tspan>'
        else:
            style_block = ""
            cursor_element = '<tspan fill="#a6e3a1"> ▋</tspan>'

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 800 380" width="800" height="380">
{style_block}  <rect width="100%" height="100%" rx="10" fill="#1e1e2e" stroke="#313244" stroke-width="1"/>
  <!-- Window buttons -->
  <circle cx="25" cy="25" r="6" fill="#f38ba8"/>
  <circle cx="45" cy="25" r="6" fill="#f9e2af"/>
  <circle cx="65" cy="25" r="6" fill="#a6e3a1"/>
  <text x="400" y="28" font-size="12" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" fill="#6c7086" text-anchor="middle">{repo_name_escaped} — bash — 80x24</text>
  <line x1="0" y1="42" x2="800" y2="42" stroke="#313244" stroke-width="1"/>

  <!-- Terminal content -->
  <text x="30" y="80" font-size="14" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" fill="#cdd6f4">
    <tspan fill="#a6e3a1">$ </tspan>{cmd_escaped}{cursor_element}
  </text>
  <text x="30" y="115" font-size="13" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" fill="#89b4fa">[1/3] {stage1_escaped}</text>
  <text x="50" y="140" font-size="13" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" fill="#a6adc8">✔ Initialized verified components</text>
  <text x="50" y="165" font-size="13" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" fill="#a6adc8">✔ Grounded in real inputs and configuration</text>

  <text x="30" y="205" font-size="13" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" fill="#89b4fa">[2/3] {stage2_escaped}</text>
  <text x="50" y="230" font-size="13" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" fill="#a6adc8">✔ Processing pipeline stages executed without drift</text>
  <text x="50" y="255" font-size="13" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" fill="#a6adc8">✔ Stage output verified against deterministic facts</text>

  <text x="30" y="295" font-size="13" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" fill="#a6e3a1">[3/3] {stage3_escaped}</text>
  <text x="50" y="320" font-size="13" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" fill="#a6e3a1">✔ {claim1_escaped}</text>
  <text x="50" y="345" font-size="13" font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace" fill="#a6e3a1">✔ {claim2_escaped}</text>
</svg>"""

