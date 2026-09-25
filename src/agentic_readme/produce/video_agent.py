"""Video Agent for Phase 1.

Produces /brag 20-second launch video specification, scene-by-scene script,
and GitHub-safe video embed snippets (GIF preview linking to MP4).
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

        scenes = self._build_20s_storyboard(story)

        spec = {
            "title": f"{story.repo_name} Launch Video",
            "duration_seconds": 20,
            "target_resolution": "1920x1080",
            "framerate": 60,
            "scenes": scenes,
            "github_safe_embed": {
                "pattern": "gif_preview_linking_to_mp4",
                "preview_gif": "assets/demo/hero-demo.svg",
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

    def _build_20s_storyboard(self, story: StorySpec) -> List[Dict[str, Any]]:
        return [
            {
                "timecode": "00:00 - 00:04",
                "duration_seconds": 4,
                "title": "The Hook & Pain Point",
                "narration": story.hook,
                "visual": f"Title card: {story.repo_name} with pain callout",
            },
            {
                "timecode": "00:04 - 00:10",
                "duration_seconds": 6,
                "title": "The Real Run",
                "narration": f"Watch {story.repo_name} execute live in the sandbox.",
                "visual": "Terminal recording executing quickstart and verifying claims",
            },
            {
                "timecode": "00:10 - 00:16",
                "duration_seconds": 6,
                "title": "Ground Truth Architecture",
                "narration": "Every figure and claim is checked against an immutable facts ledger.",
                "visual": "Architecture diagram transitioning into claim audit validation",
            },
            {
                "timecode": "00:16 - 00:20",
                "duration_seconds": 4,
                "title": "Quickstart & Verified PR",
                "narration": f"Install {story.repo_name} and generate zero-drift docs today.",
                "visual": "PR diff showing verified assets and passing checks",
            },
        ]

    def _generate_scene_table(self, scenes: List[Dict[str, Any]]) -> str:
        lines = [
            "| Time | Scene | Narration / Key Message | Visual |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for s in scenes:
            lines.append(f"| `{s['timecode']}` | **{s['title']}** | {s['narration']} | {s['visual']} |")
        return "\n".join(lines)
