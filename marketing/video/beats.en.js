// Single source of truth for beat timing + burned-in caption text (English).
//
// Consumed by TWO independent readers that must never drift apart:
//   1. storyboard.html loads this file directly (<script src="beats.en.js">)
//      and uses BEATS_EN.beats[i].frames to decide which beat is active for
//      a given frame number, and .caption for the burned-in text.
//   2. build_video.py reads this SAME file as text, strips the
//      "const BEATS_EN = " prefix and trailing ";", and json.loads() the
//      remainder to generate the .srt sidecar -- so the file must stay
//      valid JSON after that prefix/suffix strip (no comments, no trailing
//      commas, double-quoted strings only) inside the object literal below.
//
// Frame ranges are inclusive on both ends, contiguous, and exhaustive over
// 0..899 (30s at 30fps) -- see marketing/video/README.md for how to edit.
const BEATS_EN = {
  "fps": 30,
  "totalFrames": 900,
  "beats": [
    {"frames": [0, 89],    "caption": "A 40-page tender brief.\nDue Friday."},
    {"frames": [90, 164],  "caption": "That used to be a weekend."},
    {"frames": [165, 269], "caption": "Upload the brief."},
    {"frames": [270, 389], "caption": "Every requirement pulled out\nand matched to a response."},
    {"frames": [390, 509], "caption": "Methodology, org chart, program —\nbuilt from your brief, not a template."},
    {"frames": [510, 614], "caption": "A fee build-up you can defend."},
    {"frames": [615, 734], "caption": "It never invents a fact.\nAnything it doesn't know, it flags in red."},
    {"frames": [735, 839], "caption": "A drafted Word pack, in minutes."},
    {"frames": [840, 899], "caption": "CivilProposals\nYour first bid is free.\ncivilproposals.com"}
  ]
};
