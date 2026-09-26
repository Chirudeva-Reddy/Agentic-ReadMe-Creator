# docs

Two things live here:

- **The website** (`index.html`, `assets/`). Plain HTML and CSS, no build step. This folder is the GitHub Pages deploy root.
- **The written guides**, listed below.

| Doc | What's in it |
| :--- | :--- |
| [INSTALL.md](INSTALL.md) | Beginner, developer, AI-assistant, and Codespaces setup, plus CI and troubleshooting |
| [ARCHITECTURE.md](ARCHITECTURE.md) | The three phases, contracts, and agents |
| [LAUNCH_VIDEO.md](LAUNCH_VIDEO.md) | How the video was made, and the first-20-seconds README method |
| [HOUSE_STYLE.md](HOUSE_STYLE.md) | The README patterns the writer follows |
| [EVALUATION.md](EVALUATION.md) | The benchmark protocol for evaluating output quality |

## Local preview

```bash
python3 -m http.server 8000 --directory docs
```

Then open http://localhost:8000.

## Deploy (GitHub Pages)

In the repo's **Settings → Pages**, set the source to **Deploy from a branch**, branch `main`, folder **`/docs`**.

The site is self-contained: Pages only serves this folder, so the videos it plays are copies kept in `assets/`. After re-rendering a launch video, refresh the copies from the repo root:

```bash
cp assets/video/launch-video.mp4 assets/video/launch-poster.jpg docs/assets/video/
cp examples/csv-dedupe/assets/video/launch-video.mp4 examples/csv-dedupe/assets/video/launch-poster.jpg docs/assets/examples/csv-dedupe/
```
