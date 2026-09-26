# The launch video, and the first-20-seconds method

The GIF at the top of the README is a 20-second launch video made with [/brag](https://github.com/latent-spaces/brag), specifically its `/brag-slim` variant, which renders with local tools only: a headless browser, ffmpeg, and Python.

| File | What it is |
| :--- | :--- |
| [`assets/video/launch-video.mp4`](../assets/video/launch-video.mp4) | 1920×1080, 30fps, 20.0s, with soundtrack. Frame 0 is the poster, so thumbnails look right. |
| [`assets/video/launch-video.gif`](../assets/video/launch-video.gif) | 960px, 15fps, silent. This is what the README embeds. |
| [`assets/video/launch-poster.jpg`](../assets/video/launch-poster.jpg) | The settled "reveal" frame. Shown instead of the GIF to readers who set reduced motion. |
| [`assets/video/brag-plan.md`](../assets/video/brag-plan.md) | Angle, hook, storyboard, and sound plan. |
| [`assets/video/share-copy.txt`](../assets/video/share-copy.txt) | One-line caption for LinkedIn or X. |
| [`assets/video/src/`](../assets/video/src/) | The source: `composition.html` (every frame is a pure function of time), `score.py` (synthesized music and SFX), and `build.sh`. |

Rebuild it (needs Node 22+, ffmpeg, Python with numpy, and a Playwright Chromium):

```bash
assets/video/src/build.sh
```

Set `POSTER=0180` (a frame number at 30fps) to choose a different poster frame, and `OUT=dir` to write somewhere else.

## The storyline

Nobody who opens a repo cares how it's built until they know what it does for them. So the video opens with the problem, not the architecture:

| Time | Beat | Why it's there |
| :--- | :--- | :--- |
| 0–4s | **Hook.** "Your README says 40 tests pass. Your code has 3." The badges flip red. | Everyone has seen a stale badge. The problem lands in two seconds without jargon. |
| 4–7.6s | **Reveal.** Name, plus "Writes your README from your code. Then proves every claim." | What it is and why it's different, in 10 words. |
| 7.6–11.6s | **One command.** Real `agentic-readme run .` output. | Shows it's real and that it's easy. |
| 11.6–15.6s | **Fudge a badge, the build fails.** Real `audit` output, 2 fatal, `exit 1`. | The thing no plain README generator does. |
| 15.6–18s | **Proof.** The same README card as the hook, now with ✅ evidence rows. | Closes the loop: the object that lied is now verified. |
| 18–20s | **Outro.** Repo URL and where it plugs in (CLI, Claude Code, MCP, GPT). | Tells the viewer how to get it. |

Every line of terminal text in the video is copied from a real run on [`examples/tip-splitter`](../examples/tip-splitter/). You can reproduce the audit scene with the steps in [examples/README.md](../examples/README.md#watch-it-catch-a-lie).

## The first-20-seconds method

A recruiter spends under a minute on a repo, and a student decides in about the same time whether to clone it. The README is laid out for that window:

1. **Motion first (0–20s).** A GIF that tells the whole story with no sound, above everything else. GitHub doesn't play `<video>` tags that point at files in the repo, so embed a GIF and link it to the MP4.
2. **One sentence of what + who.** Plain words. If a non-programmer can't repeat it back, rewrite it.
3. **A "pick your path" table.** Recruiter, student, and developer each get one row with the single link they need. Nobody has to scroll to find their part.
4. **Proof before detail.** A try-it-in-60-seconds block (or a Codespaces link) comes before the architecture section.
5. **Everything else goes below the fold,** with links to `docs/`.

### Making one for your own repo

With the [agentic-readme skill](../skills/agentic-readme/SKILL.md) installed in Claude Code, ask for it directly:

```text
Use agentic-readme to write my README, with a launch video.
```

The skill runs Ground → Produce → Verify, then Phase 3. In Phase 3 the agent renders the storyboard from `assets/video/brag_spec.json` with `/brag-slim` (it asks before installing it) and saves `launch-video.mp4`, `launch-video.gif`, and `launch-poster.jpg`. Running `produce` again then embeds the GIF automatically. Without an agent, Node 22+, and ffmpeg, you get the storyboard and an illustrated SVG, but no video.

If you'd rather embed it by hand:

```html
<a href="assets/video/launch-video.mp4">
  <picture>
    <source media="(prefers-reduced-motion: reduce)" srcset="assets/video/launch-poster.jpg">
    <img alt="20-second launch video: what it does, one command, and the proof" src="assets/video/launch-video.gif" width="760">
  </picture>
</a>
```

To get an inline player with sound on GitHub, drag the MP4 into any issue or PR comment box. GitHub uploads it and gives you a `https://github.com/user-attachments/assets/...` URL. Put that URL on its own line in the README.
