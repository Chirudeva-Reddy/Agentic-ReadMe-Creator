# House Style Rubric & Reference Analysis

This house style is distilled from empirical analysis of 5 reference repositories, contrasting gold-standard patterns against common failure modes.

---

## 1. Reference Repositories Analysis

| Repository | What Works (Adopted as House Style) | Anti-Patterns (System Must Block) |
| :--- | :--- | :--- |
| **`duet`** | • Hook naming immediate pain ("You pay for Claude and ChatGPT...")<br>• Hero asset is a real run ("That run is real, and it is the whole pitch")<br>• Honest cost and self-test sections<br>• "Deliberately not included" design notes<br>• Editable `.excalidraw` source committed | — *(Gold standard model)* |
| **`body2health`** | • Centered title + italic one-liner<br>• Flat-square badges that link directly to evidence<br>• Hero GIF with descriptive alt text<br>• `<picture>` architecture diagrams with dark-mode (`prefers-color-scheme: dark`)<br>• Ground truth statement ("Every figure above comes from...")<br>• `/brag` launch video with scene/time table | — *(Gold standard model)* |
| **`odoo-salon-erp`** | • Clean banner, collapsible ToC, quickstart | • Generic template phrasing ("Welcome to ... 👋", "Maintained? yes" badges) |
| **`ClaimLens`** | • Strong problem framing, live demo link | • **Fact drift**: Badge says 52 tests passed, while Quickstart says 44 tests<br>• **Jargon leakage**: Internal design specs leaked into public README ("Option C Architecture", "Blueprint §11/§13")<br>• **GitHub rendering failure**: Uses `<video src="assets/claimlens-demo.mp4">` (GitHub does not render repo-relative video tags)<br>• **Inflated tone**: Emotional marketing adjectives ("agonizing uncertainty") |
| **`NLP-Proj`** | • Metric-first `<samp>` line, clickable demo GIF | • **Badge flood**: 9 for-the-badge badges causing visual clutter<br>• Text disproportionately describes frontend UI rather than core research |

---

## 2. Formatting & Structural Rules

1. **Header Layout**:
   - Centered `<h1 align="center">{repo_name}</h1>`
   - Centered italic pain hook: `<p align="center"><em>{hook}</em></p>`
2. **Badges**:
   - Style: `style=flat-square`
   - Maximum count: **≤ 6 badges**
   - Every badge MUST wrap an anchor link pointing to its underlying evidence (`LICENSE`, `pyproject.toml`, `tests/`).
3. **Hero Asset**:
   - Centered terminal run or demo GIF (`assets/demo/hero-demo.svg` or `.gif`).
   - File size must remain **under 5 MB**.
   - Mandatory descriptive alt text describing the action and outcome.
4. **Architecture Diagram**:
   - Commits `.excalidraw` source alongside SVGs.
   - Embeds via `<picture>` with dark mode variant:
     ```html
     <picture>
       <source media="(prefers-color-scheme: dark)" srcset="assets/diagrams/architecture-dark.svg">
       <img alt="Architecture diagram" src="assets/diagrams/architecture.svg" width="760">
     </picture>
     ```
5. **Video Embed Pattern**:
   - Never use `<video src="relative/path.mp4">`.
   - Use GIF preview linking to MP4 or GitHub Release attachment URL, followed by scene/time breakdown table.
6. **Evidence Table**:
   - "Every figure above is verified against source code and execution logs in `facts.json`."
   - Table detailing claim, metric value, evidence file, and status.
7. **Honest Design Constraints**:
   - Mandatory "Deliberately not included" section explaining explicit non-goals.
