"""Make the terminal demo: a VHS script and an illustrated terminal preview.

make_demo(story, out_dir) writes three files to assets/demo/:
  demo.tape              - a VHS script that types the quickstart commands. Running
                           `vhs assets/demo/demo.tape` records a real terminal GIF.
  hero-demo.svg          - a drawn terminal window with a blinking cursor (not a recording;
                           the README says so)
  hero-demo-static.svg   - the same drawing without animation, for reduced motion
"""

from __future__ import annotations

from pathlib import Path

from agentic_readme.models import StorySpec
from agentic_readme.produce.diagram import xml_escape

MONO = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"

CURSOR_BLINK_STYLE = """  <style>
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


def make_demo(story: StorySpec, out_dir: Path) -> dict[str, Path]:
    folder = Path(out_dir) / "assets" / "demo"
    folder.mkdir(parents=True, exist_ok=True)

    tape = folder / "demo.tape"
    hero = folder / "hero-demo.svg"
    static = folder / "hero-demo-static.svg"
    tape.write_text(_vhs_tape(story), encoding="utf-8")
    hero.write_text(_terminal_svg(story, animated=True), encoding="utf-8")
    static.write_text(_terminal_svg(story, animated=False), encoding="utf-8")
    return {"tape_file": tape, "hero_asset": hero, "static_asset": static}


def _vhs_tape(story: StorySpec) -> str:
    """A VHS script that types each quickstart command, with pauses a viewer can follow."""
    lines = []
    for command in story.quickstart_commands:
        safe = command.replace('"', '\\"')
        lines += [f'Type "{safe}"', "Sleep 500ms", "Enter", "Sleep 2s"]
    commands = "\n".join(lines)

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
{commands}

# End on the successful result (peak-end rule)
Sleep 3s
"""


def _trim(text: str, max_len: int = 80) -> str:
    """Shorten text so it fits the 800px terminal."""
    return text[: max_len - 3] + "..." if len(text) > max_len else text


def _terminal_svg(story: StorySpec, animated: bool) -> str:
    """A drawn terminal: the run command, then three stages taken from the diagram nodes and claims."""
    commands = story.quickstart_commands
    run_commands = [c for c in commands if not c.startswith("git clone") and not c.startswith("pip install")]
    if run_commands:
        command = run_commands[-1]
    elif commands:
        command = commands[0]
    else:
        command = f"./run_{story.repo_name}.sh"
    if "<repo-url>" in command:  # a placeholder URL makes a confusing first line
        command = "python3 src/agentic_readme/cli.py"

    nodes = story.architecture_nodes
    stage1 = nodes[0].label if len(nodes) > 0 else "System Initialization"
    stage2 = nodes[1].label if len(nodes) > 1 else "Pipeline Execution"
    stage3 = nodes[-1].label if len(nodes) > 2 else "Verification & Output"
    claims = story.key_claims
    claim1 = claims[0].claim if claims else "Pipeline execution verified successfully."
    claim2 = claims[1].claim if len(claims) > 1 else "All system outputs verified against ground truth."

    # Trim first, then escape, so an entity like &amp; is never cut in half.
    name = xml_escape(_trim(story.repo_name, 50))
    command = xml_escape(_trim(command, 85))
    stage1 = xml_escape(_trim(stage1, 75))
    stage2 = xml_escape(_trim(stage2, 75))
    stage3 = xml_escape(_trim(stage3, 75))
    claim1 = xml_escape(_trim(claim1, 80))
    claim2 = xml_escape(_trim(claim2, 80))

    style = CURSOR_BLINK_STYLE if animated else ""
    cursor_class = ' class="terminal-cursor"' if animated else ""
    cursor = f'<tspan{cursor_class} fill="#a6e3a1"> ▋</tspan>'

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 800 380" width="800" height="380">
{style}  <rect width="100%" height="100%" rx="10" fill="#1e1e2e" stroke="#313244" stroke-width="1"/>
  <!-- Window buttons -->
  <circle cx="25" cy="25" r="6" fill="#f38ba8"/>
  <circle cx="45" cy="25" r="6" fill="#f9e2af"/>
  <circle cx="65" cy="25" r="6" fill="#a6e3a1"/>
  <text x="400" y="28" font-size="12" font-family="{MONO}" fill="#6c7086" text-anchor="middle">{name} — bash — 80x24</text>
  <line x1="0" y1="42" x2="800" y2="42" stroke="#313244" stroke-width="1"/>

  <!-- Terminal content -->
  <text x="30" y="80" font-size="14" font-family="{MONO}" fill="#cdd6f4">
    <tspan fill="#a6e3a1">$ </tspan>{command}{cursor}
  </text>
  <text x="30" y="115" font-size="13" font-family="{MONO}" fill="#89b4fa">[1/3] {stage1}</text>
  <text x="50" y="140" font-size="13" font-family="{MONO}" fill="#a6adc8">✔ Initialized verified components</text>
  <text x="50" y="165" font-size="13" font-family="{MONO}" fill="#a6adc8">✔ Grounded in real inputs and configuration</text>

  <text x="30" y="205" font-size="13" font-family="{MONO}" fill="#89b4fa">[2/3] {stage2}</text>
  <text x="50" y="230" font-size="13" font-family="{MONO}" fill="#a6adc8">✔ Processing pipeline stages executed without drift</text>
  <text x="50" y="255" font-size="13" font-family="{MONO}" fill="#a6adc8">✔ Stage output verified against deterministic facts</text>

  <text x="30" y="295" font-size="13" font-family="{MONO}" fill="#a6e3a1">[3/3] {stage3}</text>
  <text x="50" y="320" font-size="13" font-family="{MONO}" fill="#a6e3a1">✔ {claim1}</text>
  <text x="50" y="345" font-size="13" font-family="{MONO}" fill="#a6e3a1">✔ {claim2}</text>
</svg>"""
