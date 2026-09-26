# /brag plan: Agentic-ReadMe-Creator

**What it is:** a CLI that writes a README from your code, then checks every badge and number in it against what the code actually does.
**Who it's for:** developers shipping a repo, and the recruiters and students who land on it and need to understand it in 20 seconds.
**What sets it apart:** it doesn't just generate text. It fails the build when the README lies.
**Most impressive true claim:** change the badges to `40 passed` and `Apache` and `agentic-readme audit` exits 1 with two fatal findings (real output from `examples/tip-splitter`).
**Visual hook:** a README badge that says "40 passed" gets scanned and flips red: "your code has 3."
**Real UI shown:** the real terminal output of `agentic-readme run` and `agentic-readme audit`, and the real generated README for `examples/tip-splitter`.
**Tone:** default. Punchy and clean, in GitHub dark with Catppuccin terminal colors, which are the colors the repo's own diagrams and demo SVG use.
**Share caption:** "Your README says 40 tests pass. Your code has 3. Agentic-ReadMe-Creator writes the README from the code, then fails the build if they ever disagree."

## Angle

Lie → proof. The first and fifth scenes use the same README card: first it's lying, then it's verified. The viewer sees the problem and the fix on the same object.

## Storyboard (20.0s, 1920×1080, 30fps)

| Time | Scene | On screen | Words to read |
| :--- | :--- | :--- | :--- |
| 0.0–4.0 | **Hook** | README card with `tests 40 passed` and `license Apache`. A scan line passes and both badges flip red. | "Your README says 40 tests pass." / "Your code has 3." |
| 4.0–7.6 | **Reveal** | Wordmark rises in. | "Agentic-ReadMe-Creator" / "Writes your README from your code." / "Then proves every claim." |
| 7.6–11.6 | **Highlight 1: one command** | Terminal types `agentic-readme run .`. The real Ground → Produce → Verify output streams in and ends on a green PASSED. | "One command." / "Code in. Verified README out." |
| 11.6–15.6 | **Highlight 2: it catches lies** | Diff: tests `3 → 40` and license `MIT → Apache` (the hook's two lies), then `agentic-readme audit` prints two red FATAL rows and `exit 1`. | "Fudge a badge." / "The build fails." |
| 15.6–18.0 | **Highlight 3: the proof** | The same README card, now truthful. The evidence table fills in with ✅. | "Every badge links to its proof." |
| 18.0–20.0 | **Outro** | Wordmark, repo URL, and chips for CLI, Claude Code skill, MCP server, GPT actions. | repo URL |

## Sound

A minor at 120 BPM with a soft pad over Am–F–C–G. The kick comes in at the reveal. Typing ticks sit low in the mix. Scene cuts get a pluck in the chord tone. The FATAL rows get a low muted A. The last second fades out.
