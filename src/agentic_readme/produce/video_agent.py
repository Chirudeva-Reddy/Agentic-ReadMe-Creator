"""Video Agent for Phase 1.

Produces a 20-second launch video storyboard (brag_spec.json + scenes.md).
It does not render video: an AI agent renders it with /brag-slim (SKILL.md, Phase 3),
and WriterAgent embeds the result as a GIF linking to the MP4.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from agentic_readme.core.models import FactsLedger, StorySpec


class VideoAgent:
    """Produces launch video configs and GitHub-safe embed snippets."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir) / "assets" / "video"

    def produce(self, story: StorySpec, facts: FactsLedger) -> Dict[str, Any]:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        config_path = self.output_dir / "brag_spec.json"
        table_path = self.output_dir / "scenes.md"

        scenes = self._build_20s_storyboard(story, facts)

        spec = {
            "title": f"{story.repo_name} Launch Video",
            "duration_seconds": 20,
            "target_resolution": "1920x1080",
            "framerate": 30,
            "status": "storyboard_only",
            "render_with": "/brag-slim (https://github.com/latent-spaces/brag), run by an AI agent; see SKILL.md Phase 3",
            "scenes": scenes,
            "rules": [
                "Open on the problem a stranger recognises; name the project only in the reveal.",
                "Every number and claim must come from facts.json or story.yaml.",
                "Terminal text must be copied from a real run of the commands shown, never typed up.",
                "Any line meant to be read stays on screen for at least 0.3s per word.",
            ],
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

        config_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

        # Generate scene markdown table (like body2health)
        scene_table = self._generate_scene_table(scenes)
        table_path.write_text(scene_table, encoding="utf-8")

        return {
            "spec_file": config_path,
            "scene_table": table_path,
            "scenes": scenes,
        }

    def _build_20s_storyboard(self, story: StorySpec, facts: FactsLedger) -> List[Dict[str, Any]]:
        """Problem-first storyboard: hook -> reveal -> real run -> proof -> how to get it."""
        name = story.repo_name
        desc_fact = facts.get_fact("project_description")
        what = str(desc_fact.value).rstrip(".") + "." if desc_fact else story.solution

        cmds = story.quickstart_commands or []
        run_cmd = next((c for c in reversed(cmds) if not c.startswith(("git clone", "pip install", "pipx install"))), None)
        install_cmd = next((c for c in cmds if "install" in c), cmds[0] if cmds else name)
        help_fact = facts.get_fact("cli_help_output")
        run_visual = f"Terminal types `{run_cmd}` and shows its real output" if run_cmd else "The product in use, from a real run"
        if help_fact:
            run_visual += f" (captured in facts.json: `{str(help_fact.value).strip()}`)"

        proof = [c.claim.rstrip(".") for c in story.key_claims[:2]]
        remote = facts.get_fact("git_remote_url")
        outro_visual = f"Install command `{install_cmd}`"
        if remote:
            outro_visual += f" and {str(remote.value).removesuffix('.git').split('://')[-1]}"

        beats = [
            ("Hook: the problem", 3.0, story.hook,
             f"Show the pain a stranger recognises, before {name} is named. No logo, no architecture."),
            ("Reveal", 3.5, f"{name}. {what}", f"{name} wordmark with the one-line description."),
            ("The real run", 5.0, f"One command: {run_cmd}." if run_cmd else f"{name} doing its job.", run_visual),
            ("Proof", 5.0, ". ".join(proof) + "." if proof else "Every claim links to its evidence.",
             "Claims appear one by one, each with the file that proves it."),
            ("How to get it", 3.5, install_cmd, outro_visual + "."),
        ]
        scenes, start = [], 0.0
        for title, dur, narration, visual in beats:
            scenes.append({
                "timecode": f"00:{start:04.1f} - 00:{start + dur:04.1f}",
                "duration_seconds": dur,
                "title": title,
                "narration": narration,
                "visual": visual,
            })
            start += dur
        return scenes

    def _generate_scene_table(self, scenes: List[Dict[str, Any]]) -> str:
        lines = [
            "| Time | Scene | Narration / Key Message | Visual |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for s in scenes:
            lines.append(f"| `{s['timecode']}` | **{s['title']}** | {s['narration']} | {s['visual']} |")
        return "\n".join(lines)
