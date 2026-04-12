#!/usr/bin/env python3
"""
detect_walkouts.py — find walkout timestamps for each fighter in a Whisper transcript.

Usage:
    python3 scripts/detect_walkouts.py <transcript.json> <event_slug> [options]

    transcript.json : output of faster-whisper transcription (list of {start, end, text})
    event_slug      : e.g. "ufc-327" — reads fighter list from data/{slug}.json

Options:
    --mode fixed-window       Use fixed time windows relative to fight announcer anchors (default)
    --mode silence-detection  Use silence gaps to detect walkout windows (not implemented)
    --pre-buffer-minutes N    How many minutes before Buffer to look for fighter 1 walkout (default: 8)
    --mid-buffer-minutes N    How many minutes before Buffer to look for fighter 2 walkout (default: 4)
    --clip-lead-seconds N     Seconds to subtract from detected timestamp when cutting clip (default: 10)
    --output PATH             Where to write walkouts JSON (default: ~/walkout-gold/{slug}/walkouts.json)
    --fuzzy-threshold N       Minimum fuzzy match score 0-100 for fighter name matching (default: 70)
"""

import argparse
import json
import re
import sys
from pathlib import Path

from rapidfuzz import fuzz, process


BUFFER_PHRASE = "ladies and gentlemen"
BUFFER_LOOKAHEAD_SECONDS = 90  # seconds after Buffer phrase to search for fighter names
# Buffer's full intro runs ~60-75s; 90s gives headroom for slow announcers
BUFFER_MIN_INTRO_WORDS = 30  # filter out short "Ladies and gentlemen, [winner]" post-fight announcements


def load_transcript(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def load_fighters(event_slug: str) -> list[str]:
    data_path = Path(__file__).parent.parent / "data" / f"{event_slug}.json"
    if not data_path.exists():
        sys.exit(f"Event data not found: {data_path}")
    with open(data_path) as f:
        data = json.load(f)
    return [entry["fighter"] for entry in data.get("songs", [])]


def fuzzy_find_fighter(text: str, fighters: list[str], threshold: int) -> str | None:
    """Return the best-matching fighter name in text, or None if below threshold."""
    result = process.extractOne(
        text,
        fighters,
        scorer=fuzz.partial_ratio,
        score_cutoff=threshold,
    )
    return result[0] if result else None


def find_fighter_in_segments(
    segments: list[dict], fighters: list[str], threshold: int
) -> str | None:
    """Scan a list of segments and return the first fighter name found."""
    full_text = " ".join(s["text"] for s in segments)
    for fighter in fighters:
        # Use token_set_ratio for multi-word names that may be partially transcribed
        score = fuzz.token_set_ratio(fighter.lower(), full_text.lower())
        if score >= threshold:
            return fighter
    return None


def find_buffer_anchors(segments: list[dict]) -> list[int]:
    """Return indices of segments containing the fight announcer's intro announcement.

    Uses "introducing first" as the definitive filter — this phrase only appears in
    real walkout intros, never in post-fight winner announcements or referee calls.
    No time-based deduplication needed: each real intro contains exactly one
    "introducing first" phrase.
    """
    anchors = []
    for i, seg in enumerate(segments):
        if BUFFER_PHRASE not in seg["text"].lower():
            continue
        anchor_time = seg["start"]
        lookahead_segs = [s for s in segments if anchor_time <= s["start"] <= anchor_time + BUFFER_LOOKAHEAD_SECONDS]
        block_text = " ".join(s["text"] for s in lookahead_segs).lower()
        if "introducing first" not in block_text:
            continue  # Post-fight or sponsor announcement — not a walkout intro
        anchors.append(i)
    return anchors


def segments_in_window(
    segments: list[dict], start_sec: float, end_sec: float
) -> list[dict]:
    return [s for s in segments if start_sec <= s["start"] < end_sec]


def first_mention_timestamp(
    segments: list[dict], fighter: str, threshold: int
) -> float | None:
    """Return timestamp (seconds) of first segment mentioning this fighter."""
    for seg in segments:
        score = fuzz.token_set_ratio(fighter.lower(), seg["text"].lower())
        if score >= threshold:
            return seg["start"]
    return None


def detect_fixed_window(
    segments: list[dict],
    fighters: list[str],
    pre_buffer_minutes: float,
    mid_buffer_minutes: float,
    clip_lead_seconds: int,
    fuzzy_threshold: int,
) -> list[dict]:
    """
    Fixed-window mode: for each fight announcer anchor, look backwards N minutes
    to find walkout commentary for each fighter in the bout.

    Fighter 1 (walks out first): look in [buffer - pre_buffer_min, buffer - mid_buffer_min]
    Fighter 2 (walks out second): look in [buffer - mid_buffer_min, buffer]
    """
    anchors = find_buffer_anchors(segments)
    if not anchors:
        print("WARNING: No fight announcer intro found in transcript.", file=sys.stderr)
        return []

    print(f"Found {len(anchors)} Buffer anchor(s).", file=sys.stderr)

    # Extract fighter names from Buffer announcement blocks
    bouts = []
    for anchor_idx in anchors:
        buffer_time = segments[anchor_idx]["start"]
        lookahead = [s for s in segments if buffer_time <= s["start"] <= buffer_time + BUFFER_LOOKAHEAD_SECONDS]
        full_text = " ".join(s["text"] for s in lookahead)

        # Find which two fighters are in this Buffer block
        bout_fighters = []
        for fighter in fighters:
            score = fuzz.token_set_ratio(fighter.lower(), full_text.lower())
            if score >= fuzzy_threshold:
                bout_fighters.append((fighter, score))

        bout_fighters.sort(key=lambda x: -x[1])
        bout_fighters = [f for f, _ in bout_fighters[:2]]

        if len(bout_fighters) < 2:
            print(
                f"WARNING: Could not identify 2 fighters for Buffer at {buffer_time:.0f}s "
                f"(found: {bout_fighters})",
                file=sys.stderr,
            )

        bouts.append({"buffer_time": buffer_time, "fighters": bout_fighters, "block_text": full_text})

    walkouts = []
    for bout in bouts:
        buffer_time = bout["buffer_time"]
        bout_fighters = bout["fighters"]

        # Window for fighter 1 (walks out first, further from Buffer)
        window1_start = buffer_time - pre_buffer_minutes * 60
        window1_end = buffer_time - mid_buffer_minutes * 60

        # Window for fighter 2 (walks out second, closer to Buffer)
        window2_start = buffer_time - mid_buffer_minutes * 60
        window2_end = buffer_time

        windows = [
            (window1_start, window1_end),
            (window2_start, window2_end),
        ]

        for i, fighter in enumerate(bout_fighters):
            if i >= len(windows):
                break
            win_start, win_end = windows[i]
            window_segs = segments_in_window(segments, win_start, win_end)
            ts = first_mention_timestamp(window_segs, fighter, fuzzy_threshold)

            if ts is None:
                print(
                    f"WARNING: Could not find walkout timestamp for {fighter} "
                    f"in window [{win_start:.0f}s, {win_end:.0f}s]",
                    file=sys.stderr,
                )
                continue

            clip_start = max(0, ts - clip_lead_seconds)
            h, m, s = int(clip_start // 3600), int((clip_start % 3600) // 60), int(clip_start % 60)

            walkouts.append({
                "fighter": fighter,
                "walkout_timestamp_seconds": round(ts, 1),
                "clip_start_seconds": round(clip_start, 1),
                "clip_start_hhmmss": f"{h:02d}:{m:02d}:{s:02d}",
                "buffer_timestamp_seconds": round(buffer_time, 1),
                "buffer_block_text": bout.get("block_text", ""),
                "mode": "fixed-window",
            })

    return walkouts


def detect_silence(segments: list[dict], fighters: list[str], **kwargs) -> list[dict]:
    """
    Silence-detection mode: find walkout windows by detecting gaps in speech
    (music playing = commentators talk less / stop). More robust than fixed windows
    for events where walkout length varies significantly.

    Implementation notes for when this gets built:
    - Compute inter-segment gaps: gap = segments[i+1]["start"] - segments[i]["end"]
    - Gaps > ~5s during a walkout window = music is prominent / commentary paused
    - Cluster gaps into silence regions, associate each with nearby fighter name mentions
    - The start of a silence region ≈ walkout music onset
    - Need to distinguish walkout silences from commercial breaks (longer, no crowd noise)
      — could use segment density before/after as a heuristic
    """
    raise NotImplementedError(
        "Silence-detection mode is not yet implemented. Use --mode fixed-window."
    )


def main():
    parser = argparse.ArgumentParser(description="Detect walkout timestamps from Whisper transcript.")
    parser.add_argument("transcript", help="Path to transcript JSON (faster-whisper output)")
    parser.add_argument("event_slug", help="Event slug, e.g. ufc-327")
    parser.add_argument(
        "--mode",
        choices=["fixed-window", "silence-detection"],
        default="fixed-window",
        help="Detection mode (default: fixed-window)",
    )
    parser.add_argument("--pre-buffer-minutes", type=float, default=8.0)
    parser.add_argument("--mid-buffer-minutes", type=float, default=4.0)
    parser.add_argument("--clip-lead-seconds", type=int, default=10)
    parser.add_argument("--fuzzy-threshold", type=int, default=55)
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for walkouts JSON. Defaults to ~/walkout-gold/{slug}/walkouts-{transcript_stem}.json",
    )
    args = parser.parse_args()

    if args.output is None:
        transcript_stem = Path(args.transcript).stem
        # Strip common suffixes we add ourselves so the name stays clean
        for suffix in ("-simple", "-vad", "-full"):
            transcript_stem = transcript_stem.removesuffix(suffix)
        output_dir = Path.home() / "walkout-gold" / args.event_slug
        output_dir.mkdir(parents=True, exist_ok=True)
        args.output = str(output_dir / f"walkouts-{transcript_stem}.json")
        print(f"Output → {args.output}", file=sys.stderr)

    segments = load_transcript(args.transcript)
    fighters = load_fighters(args.event_slug)
    print(f"Loaded {len(segments)} segments, {len(fighters)} fighters.", file=sys.stderr)

    if args.mode == "fixed-window":
        walkouts = detect_fixed_window(
            segments,
            fighters,
            pre_buffer_minutes=args.pre_buffer_minutes,
            mid_buffer_minutes=args.mid_buffer_minutes,
            clip_lead_seconds=args.clip_lead_seconds,
            fuzzy_threshold=args.fuzzy_threshold,
        )
    elif args.mode == "silence-detection":
        walkouts = detect_silence(segments, fighters)

    output = {
        "walkouts": walkouts,
        # All Buffer anchors with their raw block text — for Claude to review
        # even when fuzzy fighter matching failed. Fighter identification from
        # these blocks should be done by reading context, not just name matching.
        "anchors": [
            {
                "buffer_timestamp_seconds": round(segments[idx]["start"], 1),
                "buffer_block_text": " ".join(
                    s["text"] for s in segments
                    if segments[idx]["start"] <= s["start"] <= segments[idx]["start"] + BUFFER_LOOKAHEAD_SECONDS
                ),
            }
            for idx in find_buffer_anchors(segments)
        ],
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nDetected {len(walkouts)} walkout(s), {len(output['anchors'])} anchor(s) → {args.output}", file=sys.stderr)
    for w in walkouts:
        print(f"  {w['fighter']:<25} {w['clip_start_hhmmss']}  (Buffer at {w['buffer_timestamp_seconds']:.0f}s)", file=sys.stderr)


if __name__ == "__main__":
    main()
