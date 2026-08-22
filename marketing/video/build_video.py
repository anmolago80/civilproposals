#!/usr/bin/env python3
"""
Deterministic frame-capture build pipeline for the CivilProposals 30s LinkedIn
video.

Pipeline:
  1. Open storyboard.html in Playwright/Chromium at 1080x1080, deviceScaleFactor 1.
  2. Wait for window.__fontsReady === true (fonts loaded, first frame painted).
  3. For n in 0..899: call window.renderFrame(n), screenshot to frames/f%04d.png.
  4. Encode frames -> out/civilproposals_30s_1080[_<lang>].mp4 via ffmpeg
     (system ffmpeg if present, else imageio_ffmpeg's bundled binary -- never
     silently skipped).
  5. Export frame 780 as out/poster.jpg (quality 90).
  6. Generate out/civilproposals_30s[_<lang>].srt from the SAME beats.<lang>.js
     file that drives the burned-in captions, so caption text can never drift
     between the burned-in video and the sidecar.

Usage:
    python3 build_video.py --lang en
    python3 build_video.py --lang es
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_DIR = Path(__file__).resolve().parent
STORYBOARD = VIDEO_DIR / "storyboard.html"
FRAMES_DIR = VIDEO_DIR / "frames"
OUT_DIR = VIDEO_DIR / "out"

WIDTH = 1080
HEIGHT = 1080
FPS = 30
TOTAL_FRAMES = 900
POSTER_FRAME = 780


def find_ffmpeg():
    """Locate an ffmpeg binary. System ffmpeg first, else imageio_ffmpeg's
    bundled binary. Never silently skip the encode -- raise a clear error if
    neither is available."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
    except ImportError:
        print(
            "ERROR: ffmpeg is not installed and imageio_ffmpeg is not "
            "available.\n"
            "  Fix: pip install imageio-ffmpeg --break-system-packages\n"
            "  (or install ffmpeg on this machine via your package manager)",
            file=sys.stderr,
        )
        sys.exit(1)
    return imageio_ffmpeg.get_ffmpeg_exe()


def load_beats(lang):
    """Read beats.<lang>.js as text, strip the 'const BEATS_XX = ' prefix and
    trailing ';', and json.loads() the remainder. This is the exact same
    extraction the storyboard's caption text is authored against, so the SRT
    and the burned-in captions can never drift."""
    path = VIDEO_DIR / f"beats.{lang}.js"
    if not path.exists():
        print(f"ERROR: beat table not found: {path}", file=sys.stderr)
        sys.exit(1)
    text = path.read_text(encoding="utf-8")
    m = re.search(r"const\s+BEATS_\w+\s*=\s*(\{.*\});\s*\Z", text, re.S)
    if not m:
        print(f"ERROR: could not extract beat table from {path}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(m.group(1))

    beats = data["beats"]
    fps = data["fps"]
    total = data["totalFrames"]
    if fps != FPS or total != TOTAL_FRAMES:
        print(
            f"ERROR: {path} declares fps={fps} totalFrames={total}, "
            f"expected fps={FPS} totalFrames={TOTAL_FRAMES}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate frame ranges are contiguous and exhaustive over 0..TOTAL_FRAMES-1.
    expected_start = 0
    for i, beat in enumerate(beats):
        s, e = beat["frames"]
        if s != expected_start:
            print(
                f"ERROR: {path} beat {i} starts at frame {s}, expected {expected_start}",
                file=sys.stderr,
            )
            sys.exit(1)
        if e < s:
            print(f"ERROR: {path} beat {i} has end < start ({e} < {s})", file=sys.stderr)
            sys.exit(1)
        expected_start = e + 1
    if expected_start != TOTAL_FRAMES:
        print(
            f"ERROR: {path} beats cover frames 0..{expected_start - 1}, "
            f"expected exhaustive coverage to {TOTAL_FRAMES - 1}",
            file=sys.stderr,
        )
        sys.exit(1)

    return beats


def frame_to_timecode(frame_num):
    """Convert a frame number (at FPS) to an SRT timecode HH:MM:SS,mmm."""
    total_ms = round(frame_num * 1000 / FPS)
    hours = total_ms // 3_600_000
    total_ms -= hours * 3_600_000
    minutes = total_ms // 60_000
    total_ms -= minutes * 60_000
    seconds = total_ms // 1000
    total_ms -= seconds * 1000
    ms = total_ms
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def write_srt(beats, out_path):
    lines = []
    for i, beat in enumerate(beats, start=1):
        s, e = beat["frames"]
        start_tc = frame_to_timecode(s)
        # SRT end timecode is exclusive-ish by convention; use the frame after
        # the beat's last frame so consecutive captions are back-to-back with
        # no gap and no overlap.
        end_tc = frame_to_timecode(e + 1)
        caption = beat["caption"].replace("\n", "\n")
        lines.append(str(i))
        lines.append(f"{start_tc} --> {end_tc}")
        lines.append(caption)
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_path}")


def capture_frames(lang):
    from playwright.sync_api import sync_playwright

    if FRAMES_DIR.exists():
        shutil.rmtree(FRAMES_DIR)
    FRAMES_DIR.mkdir(parents=True)

    url = STORYBOARD.as_uri() + f"?lang={lang}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=1,
        )
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        page.goto(url)
        page.wait_for_function("window.__fontsReady === true", timeout=30_000)

        if errors:
            browser.close()
            print("ERROR: page/console errors during load:", file=sys.stderr)
            for e in errors:
                print(f"  {e}", file=sys.stderr)
            sys.exit(1)

        for n in range(TOTAL_FRAMES):
            page.evaluate(f"renderFrame({n})")
            dest = FRAMES_DIR / f"f{n:04d}.png"
            page.screenshot(path=str(dest))
            if n % 100 == 0:
                print(f"  captured frame {n}/{TOTAL_FRAMES}")

        if errors:
            browser.close()
            print("ERROR: page/console errors during capture:", file=sys.stderr)
            for e in errors:
                print(f"  {e}", file=sys.stderr)
            sys.exit(1)

        browser.close()

    frame_count = len(list(FRAMES_DIR.glob("f*.png")))
    if frame_count != TOTAL_FRAMES:
        print(
            f"ERROR: expected {TOTAL_FRAMES} frames, found {frame_count} in {FRAMES_DIR}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"Captured {frame_count} frames to {FRAMES_DIR}")


def encode_video(ffmpeg_bin, lang):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "" if lang == "en" else f"_{lang}"
    out_path = OUT_DIR / f"civilproposals_30s_1080{suffix}.mp4"

    cmd = [
        ffmpeg_bin,
        "-y",
        "-framerate", str(FPS),
        "-i", str(FRAMES_DIR / "f%04d.png"),
        "-c:v", "libx264",
        "-profile:v", "high",
        "-pix_fmt", "yuv420p",
        "-crf", "20",
        "-movflags", "+faststart",
        str(out_path),
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ERROR: ffmpeg encode failed:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    if not out_path.exists() or out_path.stat().st_size == 0:
        print(f"ERROR: ffmpeg reported success but {out_path} is missing/empty", file=sys.stderr)
        sys.exit(1)
    print(f"Encoded {out_path} ({out_path.stat().st_size} bytes)")
    return out_path


def export_poster(ffmpeg_bin, lang):
    poster_src = FRAMES_DIR / f"f{POSTER_FRAME:04d}.png"
    if not poster_src.exists():
        print(f"ERROR: poster source frame missing: {poster_src}", file=sys.stderr)
        sys.exit(1)
    # Suffix matches the MP4/SRT convention: bare name for en, _<lang> otherwise,
    # so building one language never clobbers another language's poster on disk.
    suffix = "" if lang == "en" else f"_{lang}"
    poster_out = OUT_DIR / f"poster{suffix}.jpg"
    cmd = [ffmpeg_bin, "-y", "-i", str(poster_src), "-q:v", "3", str(poster_out)]
    # -q:v 3 corresponds to roughly quality 90 on ffmpeg's inverted mjpeg scale.
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ERROR: poster export failed:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    print(f"Wrote {poster_out}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", choices=["en", "es"], default="en")
    args = parser.parse_args()

    print(f"=== Building {args.lang} render ===")

    ffmpeg_bin = find_ffmpeg()
    print(f"Using ffmpeg: {ffmpeg_bin}")

    beats = load_beats(args.lang)
    print(f"Loaded {len(beats)} beats from beats.{args.lang}.js (validated contiguous/exhaustive)")

    capture_frames(args.lang)
    encode_video(ffmpeg_bin, args.lang)
    export_poster(ffmpeg_bin, args.lang)

    srt_suffix = "" if args.lang == "en" else f"_{args.lang}"
    srt_path = OUT_DIR / f"civilproposals_30s{srt_suffix}.srt"
    write_srt(beats, srt_path)

    print(f"=== Done: {args.lang} render complete ===")


if __name__ == "__main__":
    main()
