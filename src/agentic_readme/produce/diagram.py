"""Draw the architecture diagram from the nodes in story.yaml.

draw_diagrams(story, out_dir) writes four files to assets/diagrams/:
  architecture.excalidraw  - editable source (open it at excalidraw.com)
  architecture.svg         - light theme
  architecture-dark.svg    - dark theme (used when the reader's GitHub is in dark mode)
  architecture-static.svg  - high-contrast version for reduced motion and print

Each node becomes a box, left to right, joined by arrows. Guardrail nodes get a
highlighted colour.
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

from agentic_readme.models import ArchitectureNode, StorySpec

# Colours for each SVG version.
THEMES = {
    "light": {
        "background": "#ffffff", "text": "#1f2328", "box": "#f6f8fa", "border": "#d0d7de",
        "guard_box": "#e8f4fd", "guard_border": "#0969da", "arrow": "#656d76",
    },
    "dark": {
        "background": "#0d1117", "text": "#e6edf3", "box": "#161b22", "border": "#30363d",
        "guard_box": "#1c2c3e", "guard_border": "#388bfd", "arrow": "#8b949e",
    },
    "static": {
        "background": "#ffffff", "text": "#24292f", "box": "#f6f8fa", "border": "#57606a",
        "guard_box": "#eaeef2", "guard_border": "#24292f", "arrow": "#57606a",
    },
}

SVG_FILES = {"light": "architecture.svg", "dark": "architecture-dark.svg", "static": "architecture-static.svg"}


def xml_escape(text: object) -> str:
    """Escape text for SVG/XML, including both kinds of quote."""
    return escape(str(text), {'"': "&quot;", "'": "&apos;"})


def draw_diagrams(story: StorySpec, out_dir: Path) -> dict[str, Path]:
    folder = Path(out_dir) / "assets" / "diagrams"
    folder.mkdir(parents=True, exist_ok=True)
    nodes = story.architecture_nodes

    excalidraw = folder / "architecture.excalidraw"
    excalidraw.write_text(json.dumps(_excalidraw(nodes), indent=2), encoding="utf-8")
    paths = {"excalidraw": excalidraw}

    for theme, filename in SVG_FILES.items():
        path = folder / filename
        path.write_text(_svg(nodes, THEMES[theme]), encoding="utf-8")
        paths[f"{theme}_svg"] = path
    return paths


def _excalidraw(nodes: list[ArchitectureNode]) -> dict:
    """Excalidraw's JSON format: a rectangle and a text label per node, an arrow between them."""
    elements = []
    left, top = 100, 100
    for i, node in enumerate(nodes):
        element_id = f"node_{node.id}_{i}"
        elements.append({
            "id": element_id,
            "type": "rectangle",
            "x": left + (i * 220),
            "y": top,
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
        elements.append({
            "id": f"text_{element_id}",
            "type": "text",
            "x": left + (i * 220) + 15,
            "y": top + 30,
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
        if i > 0:
            elements.append({
                "id": f"arrow_{i}",
                "type": "arrow",
                "x": left + ((i - 1) * 220) + 180,
                "y": top + 45,
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
        "appState": {"viewBackgroundColor": "#ffffff", "gridSize": None},
        "files": {},
    }


def _svg(nodes: list[ArchitectureNode], colors: dict[str, str]) -> str:
    width = max(800, len(nodes) * 220 + 80)
    height = 200
    left, top = 40, 55
    box_w, box_h = 170, 80
    font = 'font-family="system-ui, sans-serif"'

    parts = []
    for i, node in enumerate(nodes):
        x = left + (i * 210)
        is_guard = node.role == "guardrail"
        fill = colors["guard_box"] if is_guard else colors["box"]
        border = colors["guard_border"] if is_guard else colors["border"]
        role = xml_escape(node.role.replace("_", " ").upper())
        label = node.label[:22] + "..." if len(node.label) > 25 else node.label  # keep it inside the box

        parts.append(f'<rect x="{x}" y="{top}" width="{box_w}" height="{box_h}" rx="8" '
                     f'fill="{fill}" stroke="{border}" stroke-width="2"/>')
        parts.append(f'<text x="{x + box_w/2}" y="{top + 28}" font-size="10" {font} '
                     f'font-weight="600" fill="{colors["arrow"]}" text-anchor="middle">{role}</text>')
        parts.append(f'<text x="{x + box_w/2}" y="{top + 52}" font-size="13" {font} '
                     f'font-weight="bold" fill="{colors["text"]}" text-anchor="middle">{xml_escape(label)}</text>')

        if i < len(nodes) - 1:  # arrow to the next box
            x1 = x + box_w
            y = top + (box_h / 2)
            parts.append(f'<line x1="{x1}" y1="{y}" x2="{x1 + 40}" y2="{y}" '
                         f'stroke="{colors["arrow"]}" stroke-width="2" marker-end="url(#arrowhead)"/>')

    background, arrow = colors["background"], colors["arrow"]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="{height}" style="background-color: {background};">
  <defs>
    <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
      <polygon points="0 0, 8 3, 0 6" fill="{arrow}" />
    </marker>
  </defs>
  {"".join(parts)}
</svg>"""
