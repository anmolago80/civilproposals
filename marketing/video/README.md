# CivilProposals — 30s LinkedIn video

A deterministic, frame-captured 30-second promo video. No screen recording,
no wall-clock timing — every frame is rendered from an explicit integer frame
number, so the output is reproducible byte-for-byte given the same inputs.

## What's here

```
marketing/video/
  storyboard.html      the entire visual — a single page exposing window.renderFrame(n)
  beats.en.js           English beat timing + caption copy (the source of truth)
  beats.es.js           Spanish beat timing + caption copy
  build_video.py        capture + encode pipeline
  fonts/                Plus Jakarta Sans woff2 files (500/600/700/800), local — no network fetch at render time
  assets/                unmodified copies of the screenshots/logo used, sourced from landing/assets/
  out/                   build output: MP4s, SRTs, posters (committed)
  frames/                per-frame PNGs written during a build (gitignored, not committed)
  post.md                 the LinkedIn post copy
```

## Re-running the build

```bash
cd marketing/video
python3 build_video.py --lang en    # -> out/civilproposals_30s_1080.mp4, out/civilproposals_30s.srt
python3 build_video.py --lang es    # -> out/civilproposals_30s_1080_es.mp4, out/civilproposals_30s_es.srt
```

Requirements: Python 3 with Playwright installed (`pip install playwright && playwright install chromium`,
or use a preinstalled Chromium via `PLAYWRIGHT_BROWSERS_PATH`), and ffmpeg. If ffmpeg
isn't on the machine, `pip install imageio-ffmpeg` — the script falls back to its
bundled binary automatically rather than skipping the encode.

Each run:
1. Opens `storyboard.html?lang=<en|es>` in headless Chromium at 1080×1080, deviceScaleFactor 1.
2. Waits for `window.__fontsReady === true` (fonts loaded, frame 0 painted).
3. Calls `renderFrame(n)` for `n = 0..899` and screenshots each to `frames/f%04d.png`.
4. Encodes the frames to H.264/yuv420p MP4 via ffmpeg.
5. Exports frame 780 as `out/poster.jpg` (`out/poster_es.jpg` for the Spanish run).
6. Regenerates the matching `.srt` from the same beat table used for the burned-in captions.

The poster, MP4, and SRT filenames all follow the same convention: no suffix for
English, `_es` for Spanish — so building one language never overwrites the other's
output. Each run overwrites only its own language's files in place; `frames/` is
wiped and rebuilt every time (it's gitignored — never committed).

## Editing the copy

**There is exactly one place to edit each language's copy: `beats.en.js` / `beats.es.js`.**
Do not edit caption text anywhere else — `storyboard.html` reads these files directly for
the burned-in captions, and `build_video.py` reads the same files to generate the `.srt`,
so the two can never drift apart.

Each file is a JS object literal (loaded by the browser via `<script src>`) that is
*also* valid JSON once the `const BEATS_XX = ` prefix and trailing `;` are stripped —
`build_video.py` does exactly that strip-and-parse. So when editing:

- Keep it valid JSON inside the braces: double-quoted strings only, no comments, no
  trailing commas.
- `"frames": [start, end]` ranges must stay contiguous and exhaustive across all 9
  beats, covering `0..899` with no gaps or overlaps — `build_video.py` validates this
  and fails loudly if it isn't true.
- `\n` inside a `"caption"` string is a manual line break (used to control exactly
  where the burned-in caption wraps).
- Spanish is intentionally longer per beat than English; the storyboard will shrink the
  caption's font size (down to a floor) before wrapping into an extra physical line
  (capped at 3 lines) — see `fitLinesAllowWrap` in `storyboard.html` — so long ES
  copy degrades gracefully rather than clipping. If you add even longer ES copy, verify
  it visually (see below) — the algorithm avoids clipping, but very long lines can still
  look cramped.

The two red placeholder chip strings in beat 7 (`[CONFIRM REGISTRATION NUMBER]` /
`[INSERT KEY PERSONNEL NAME]` and their ES equivalents) are hardcoded in
`storyboard.html`'s JS (search for `s6chip1` / `s6chip2`), not in the beat-table files,
since they're a visual prop rather than a caption line.

## Changing timing, motion, or layout

Everything else — scene layout, crossfade windows, slow-push amounts, fade-up timing —
lives in `storyboard.html`. Each beat has a `paintBeatN(local, dur, caption)` function;
`local` is the frame number relative to that beat's start (0-indexed). All motion is
computed as a pure function of `local` — no `requestAnimationFrame`, no CSS
transitions/animations, no `Date.now()` — so re-rendering frame N always produces the
same pixels.

## Verifying a build

```bash
ffprobe -v error -show_entries stream=width,height,r_frame_rate,codec_name,pix_fmt \
  -show_entries format=duration -of default=noprint_wrappers=0 out/civilproposals_30s_1080.mp4
```

Expect: `width=1080 height=1080 r_frame_rate=30/1 codec_name=h264 pix_fmt=yuv420p`
and a duration of ~30.0s.

To spot-check individual frames without a full re-encode, pull them straight out of
`frames/` after a build (e.g. `frames/f0045.png`), or re-run just the capture portion
in a Python shell:

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    page = p.chromium.launch().new_page(viewport={"width": 1080, "height": 1080})
    page.goto("file://" + "/absolute/path/to/storyboard.html" + "?lang=en")
    page.wait_for_function("window.__fontsReady === true")
    page.evaluate("renderFrame(300)")
    page.screenshot(path="check.png")
```

## Assets

All screenshots and the logo mark are unmodified copies of files from `landing/assets/`
(read from there, not moved — `landing/` itself is never touched by this build). Every
one was opened and read before use to confirm it contains only example/placeholder data
(e.g. `demo@civilproposals.com`, generic discipline names, fictional placeholder names)
and no real client or person's name.
