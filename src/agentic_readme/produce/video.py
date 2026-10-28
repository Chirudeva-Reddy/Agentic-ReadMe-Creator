"""Plan a 20-second launch video: a storyboard, not a rendered video.

make_storyboard(story, facts, out_dir) writes two files to assets/video/:
  brag_spec.json  - five timed scenes plus the rules a renderer must follow
  scenes.md       - the same scenes as a Markdown table

Rendering is a separate agent step: an AI agent renders the storyboard with /brag-slim
(see SKILL.md, Phase 3), and write_readme then embeds the GIF linking to the MP4.
"""

from __future__ import annotations

import json
from pathlib import Path

from agentic_readme.models import FactsLedger, StorySpec

RENDER_RULES = [
    "Open on the problem a stranger recognises; name the project only in the reveal.",
    "Every number and claim must come from facts.json or story.yaml.",
    "Terminal text must be copied from a real run of the commands shown, never typed up.",
    "Any line meant to be read stays on screen for at least 0.3s per word.",
]


def make_storyboard(story: StorySpec, facts: FactsLedger, out_dir: Path) -> dict:
    folder = Path(out_dir) / "assets" / "video"
    folder.mkdir(parents=True, exist_ok=True)
    spec_file = folder / "brag_spec.json"
    table_file = folder / "scenes.md"

    scenes = _scenes(story, facts)
    spec = {
        "title": f"{story.repo_name} Launch Video",
        "duration_seconds": 20,
        "target_resolution": "1920x1080",
        "framerate": 30,
        "status": "storyboard_only",
        "render_with": "/brag-slim (https://github.com/latent-spaces/brag), run by an AI agent; see SKILL.md Phase 3",
        "scenes": scenes,
        "rules": RENDER_RULES,
        "deliverables": {
            "mp4": "assets/video/launch-video.mp4",
            "gif": "assets/video/launch-video.gif",
            "poster": "assets/video/launch-poster.jpg",
        },
        "github_safe_embed": {
            "pattern": "gif_preview_linking_to_mp4",
            "preview_gif": "assets/video/launch-video.gif",
            "reduced_motion_poster": "assets/video/launch-poster.jpg",
            "target_mp4": "assets/video/launch-video.mp4",
            "github_discussions_or_release_note": (
                "Upload MP4 to GitHub Release or issue/PR comment to obtain "
                "a https://github.com/user-attachments/assets/... URL."
            ),
        },
    }
    spec_file.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    table_file.write_text(_scene_table(scenes), encoding="utf-8")
    return {"spec_file": spec_file, "scene_table": table_file, "scenes": scenes}


def _scenes(story: StorySpec, facts: FactsLedger) -> list[dict]:
    """Problem-first: hook -> reveal -> real run -> proof -> how to get it."""
    name = story.repo_name
    description = facts.get_fact("project_description")
    what = str(description.value).rstrip(".") + "." if description else story.solution

    commands = story.quickstart_commands or []
    run_command = None
    for command in reversed(commands):  # the last command that isn't a setup step
        if not command.startswith(("git clone", "pip install", "pipx install")):
            run_command = command
            break
    install_command = name
    if commands:
        install_command = commands[0]
        for command in commands:  # the first command that installs something
            if "install" in command:
                install_command = command
                break

    if run_command:
        run_narration = f"One command: {run_command}."
        run_visual = f"Terminal types `{run_command}` and shows its real output"
    else:
        run_narration = f"{name} doing its job."
        run_visual = "The product in use, from a real run"
    help_line = facts.get_fact("cli_help_output")
    if help_line:
        run_visual += f" (captured in facts.json: `{str(help_line.value).strip()}`)"

    proof = [c.claim.rstrip(".") for c in story.key_claims[:2]]
    proof_narration = ". ".join(proof) + "." if proof else "Every claim links to its evidence."

    outro_visual = f"Install command `{install_command}`"
    remote = facts.get_fact("git_remote_url")
    if remote:
        outro_visual += f" and {str(remote.value).removesuffix('.git').split('://')[-1]}"

    beats = [
        # (title, seconds, narration, what's on screen)
        ("Hook: the problem", 3.0, story.hook,
         f"Show the pain a stranger recognises, before {name} is named. No logo, no architecture."),
        ("Reveal", 3.5, f"{name}. {what}", f"{name} wordmark with the one-line description."),
        ("The real run", 5.0, run_narration, run_visual),
        ("Proof", 5.0, proof_narration, "Claims appear one by one, each with the file that proves it."),
        ("How to get it", 3.5, install_command, outro_visual + "."),
    ]
    scenes = []
    start = 0.0
    for title, seconds, narration, visual in beats:
        scenes.append({
            "timecode": f"00:{start:04.1f} - 00:{start + seconds:04.1f}",
            "duration_seconds": seconds,
            "title": title,
            "narration": narration,
            "visual": visual,
        })
        start += seconds
    return scenes


def _scene_table(scenes: list[dict]) -> str:
    lines = [
        "| Time | Scene | Narration / Key Message | Visual |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for s in scenes:
        lines.append(f"| `{s['timecode']}` | **{s['title']}** | {s['narration']} | {s['visual']} |")
    return "\n".join(lines)
