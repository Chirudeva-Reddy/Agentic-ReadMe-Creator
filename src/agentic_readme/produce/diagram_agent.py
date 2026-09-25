"""Diagram Agent for Phase 1.

Derives architectural diagrams strictly from verified code nodes (entry points,
pipeline stages, storage, guardrails) rather than generic vibes.
Produces .excalidraw source + light and dark SVG assets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from agentic_readme.core.models import ArchitectureNode, FactsLedger, StorySpec


class DiagramAgent:
    """Produces code-grounded architecture diagrams."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir) / "assets" / "diagrams"

    def produce(self, story: StorySpec, facts: FactsLedger) -> Dict[str, Path]:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        excalidraw_path = self.output_dir / "architecture.excalidraw"
        light_svg_path = self.output_dir / "architecture.svg"
        dark_svg_path = self.output_dir / "architecture-dark.svg"

        # 1. Generate .excalidraw source
        excalidraw_data = self._generate_excalidraw(story.architecture_nodes, story.repo_name)
        excalidraw_path.write_text(json.dumps(excalidraw_data, indent=2), encoding="utf-8")

        # 2. Generate Light SVG
        light_svg = self._generate_svg(story.architecture_nodes, is_dark=False)
        light_svg_path.write_text(light_svg, encoding="utf-8")

        # 3. Generate Dark SVG
        dark_svg = self._generate_svg(story.architecture_nodes, is_dark=True)
        dark_svg_path.write_text(dark_svg, encoding="utf-8")

        return {
            "excalidraw": excalidraw_path,
            "light_svg": light_svg_path,
            "dark_svg": dark_svg_path,
        }

    def _generate_excalidraw(self, nodes: List[ArchitectureNode], title: str) -> Dict[str, Any]:
        """Create valid Excalidraw schema with code-grounded nodes."""
        elements = []
        x_offset = 100
        y_offset = 100

        for i, node in enumerate(nodes):
            element_id = f"node_{node.id}_{i}"
            elements.append({
                "id": element_id,
                "type": "rectangle",
                "x": x_offset + (i * 220),
                "y": y_offset,
                "width": 180,
                "height": 90,
                "angle": 0,
                "strokeColor": "#1e1e1e",
                "backgroundColor": "#e3fafc" if node.role == "guardrail" else "#e7f5ff",
                "fillStyle": "solid",
                "strokeWidth": 2,
                "strokeStyle": "solid",
                "roughness": 1,
                "opacity": 100,
                "groupIds": [],
                "roundness": {"type": 3},
                "seed": 1000 + i,
                "version": 1,
                "versionNonce": 1,
                "isDeleted": False,
                "boundElements": None,
                "updated": 1,
                "link": node.source_file or None,
                "locked": False,
            })
            # Add text inside rectangle
            elements.append({
                "id": f"text_{element_id}",
                "type": "text",
                "x": x_offset + (i * 220) + 15,
                "y": y_offset + 30,
                "width": 150,
                "height": 30,
                "angle": 0,
                "strokeColor": "#1e1e1e",
                "backgroundColor": "transparent",
                "fillStyle": "solid",
                "strokeWidth": 1,
                "strokeStyle": "solid",
                "roughness": 1,
                "opacity": 100,
                "text": node.label,
                "fontSize": 14,
                "fontFamily": 1,
                "textAlign": "center",
                "verticalAlign": "middle",
                "baseline": 18,
            })

            # Add arrow between nodes
            if i > 0:
                elements.append({
                    "id": f"arrow_{i}",
                    "type": "arrow",
                    "x": x_offset + ((i - 1) * 220) + 180,
                    "y": y_offset + 45,
                    "width": 40,
                    "height": 0,
                    "angle": 0,
                    "strokeColor": "#495057",
                    "points": [[0, 0], [40, 0]],
                    "endArrowhead": "arrow",
                })

        return {
            "type": "excalidraw",
            "version": 2,
            "source": "agentic-readme-creator",
            "elements": elements,
            "appState": {
                "viewBackgroundColor": "#ffffff",
                "gridSize": None,
            },
            "files": {},
        }

    def _generate_svg(self, nodes: List[ArchitectureNode], is_dark: bool = False) -> str:
        """Generate clean, scalable SVG diagram for light and dark modes."""
        bg_color = "#0d1117" if is_dark else "#ffffff"
        text_color = "#e6edf3" if is_dark else "#1f2328"
        box_bg = "#161b22" if is_dark else "#f6f8fa"
        box_border = "#30363d" if is_dark else "#d0d7de"
        guard_bg = "#1c2c3e" if is_dark else "#e8f4fd"
        guard_border = "#388bfd" if is_dark else "#0969da"
        arrow_color = "#8b949e" if is_dark else "#656d76"

        width = max(800, len(nodes) * 220 + 80)
        height = 200

        svg_elements = []
        x_start = 40
        y_pos = 55
        box_w = 170
        box_h = 80

        for i, node in enumerate(nodes):
            x = x_start + (i * 210)
            is_guard = node.role == "guardrail"
            fill = guard_bg if is_guard else box_bg
            border = guard_border if is_guard else box_border

            svg_elements.append(
                f'<rect x="{x}" y="{y_pos}" width="{box_w}" height="{box_h}" rx="8" '
                f'fill="{fill}" stroke="{border}" stroke-width="2"/>'
            )
            role_text = node.role.replace("_", " ").upper()
            svg_elements.append(
                f'<text x="{x + box_w/2}" y="{y_pos + 28}" font-size="10" font-family="system-ui, sans-serif" '
                f'font-weight="600" fill="{arrow_color}" text-anchor="middle">{role_text}</text>'
            )
            # Truncate label for neat rendering if needed
            label_text = node.label[:22] + "..." if len(node.label) > 25 else node.label
            svg_elements.append(
                f'<text x="{x + box_w/2}" y="{y_pos + 52}" font-size="13" font-family="system-ui, sans-serif" '
                f'font-weight="bold" fill="{text_color}" text-anchor="middle">{label_text}</text>'
            )

            # Draw connecting arrow
            if i < len(nodes) - 1:
                arrow_x1 = x + box_w
                arrow_x2 = arrow_x1 + 40
                arrow_y = y_pos + (box_h / 2)
                svg_elements.append(
                    f'<line x1="{arrow_x1}" y1="{arrow_y}" x2="{arrow_x2}" y2="{arrow_y}" '
                    f'stroke="{arrow_color}" stroke-width="2" marker-end="url(#arrowhead)"/>'
                )

        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="{height}" style="background-color: {bg_color};">
  <defs>
    <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
      <polygon points="0 0, 8 3, 0 6" fill="{arrow_color}" />
    </marker>
  </defs>
  {"".join(svg_elements)}
</svg>"""
        return svg
