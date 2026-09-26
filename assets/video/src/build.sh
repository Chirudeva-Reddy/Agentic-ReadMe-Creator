#!/usr/bin/env bash
# Rebuilds the launch video from composition.html + score.py.
# Needs: node 22+, ffmpeg, python3 + numpy, and a Chromium for playwright-core
# (set CHROME=/path/to/chrome if it isn't in the default Playwright cache).
set -euo pipefail
cd "$(dirname "$0")"
OUT=${OUT:-..}
POSTER=${POSTER:-0207}   # frame number of the strongest settled frame (30fps)
[ -d node_modules/playwright-core ] || npm i --no-save playwright-core >/dev/null
rm -rf frames gifframes mp4frames
node render.mjs frames      # 1920x1080 @ 30fps for the MP4
node render.mjs gif         # 15fps, static background, for a small GIF
python3 score.py            # score.wav

# Poster = settled frame; baked in as MP4 frame 0 so thumbnails show it
ffmpeg -loglevel error -y -i frames/f$POSTER.png -q:v 2 "$OUT/launch-poster.jpg"
mkdir -p mp4frames && cp frames/*.png mp4frames/ && cp frames/f$POSTER.png mp4frames/f0000.png
ffmpeg -loglevel error -y -framerate 30 -i mp4frames/f%04d.png -i score.wav \
  -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p \
  -af "loudnorm=I=-14:TP=-1.5:LRA=7" -c:a aac -b:a 160k -ar 44100 \
  -movflags +faststart -shortest "$OUT/launch-video.mp4"
ffmpeg -loglevel error -y -framerate 15 -i gifframes/f%04d.png \
  -vf "scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  "$OUT/launch-video.gif"
rm -rf mp4frames
ls -la "$OUT"/launch-*
