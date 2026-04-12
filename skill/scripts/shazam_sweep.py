#!/usr/bin/env python3
"""Run shazamio against clips using several short front-loaded windows.

Usage:
    python3 skill/scripts/shazam_sweep.py /path/to/clips/*.mp3
    python3 skill/scripts/shazam_sweep.py --clips-dir /path/to/clips

The script tries:
1. The full clip
2. A sweep of short windows from the front of the clip (defaults: 5s and 8s)

This is useful for broadcast walkouts where the opening seconds may be clean enough
for recognition, but later commentary/crowd noise drowns out the fingerprint.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path


try:
    from shazamio import Shazam
except ModuleNotFoundError as exc:
    sys.exit(
        "shazamio is not installed in this Python environment. "
        "Create a Python 3.12 venv and install it there, e.g.:\n"
        "  uv venv /path/to/shazam-env --python 3.12\n"
        "  uv pip install --python /path/to/shazam-env shazamio\n"
        f"\nOriginal error: {exc}"
    )


def parse_int_csv(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def build_attempts(offsets: list[int], durations: list[int]) -> list[dict]:
    attempts = [{"kind": "full"}]
    for duration in durations:
        for offset in offsets:
            attempts.append(
                {
                    "kind": "window",
                    "offset_seconds": offset,
                    "duration_seconds": duration,
                }
            )
    return attempts


def cut_window(src: Path, dest: Path, offset_seconds: int, duration_seconds: int) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            str(offset_seconds),
            "-i",
            str(src),
            "-t",
            str(duration_seconds),
            "-acodec",
            "libmp3lame",
            "-q:a",
            "2",
            str(dest),
        ],
        check=True,
    )


async def recognize_clip(shazam: Shazam, clip_path: Path) -> dict:
    result = await shazam.recognize(str(clip_path))
    track = result.get("track") or {}
    return {
        "matched": bool(track),
        "title": track.get("title"),
        "artist": track.get("subtitle"),
        "url": track.get("url"),
        "match_count": len(result.get("matches", [])),
    }


async def sweep_clip(
    shazam: Shazam,
    clip_path: Path,
    attempts: list[dict],
    keep_cuts: bool,
    cuts_dir: Path | None,
) -> dict:
    summary = {
        "clip": str(clip_path),
        "best_match": None,
        "attempts": [],
    }

    with tempfile.TemporaryDirectory(prefix="shazam-sweep-") as tmpdir:
        tmpdir_path = Path(tmpdir)

        for attempt in attempts:
            probe_path = clip_path
            attempt_result = dict(attempt)

            if attempt["kind"] == "window":
                name = f"{clip_path.stem}_{attempt['offset_seconds']:02d}_{attempt['duration_seconds']}s.mp3"
                if keep_cuts:
                    assert cuts_dir is not None
                    cuts_dir.mkdir(parents=True, exist_ok=True)
                    probe_path = cuts_dir / name
                else:
                    probe_path = tmpdir_path / name
                cut_window(
                    clip_path,
                    probe_path,
                    attempt["offset_seconds"],
                    attempt["duration_seconds"],
                )

            attempt_result.update(await recognize_clip(shazam, probe_path))
            summary["attempts"].append(attempt_result)

            if summary["best_match"] is None and attempt_result["matched"]:
                summary["best_match"] = {
                    "kind": attempt_result["kind"],
                    "offset_seconds": attempt_result.get("offset_seconds"),
                    "duration_seconds": attempt_result.get("duration_seconds"),
                    "title": attempt_result["title"],
                    "artist": attempt_result["artist"],
                    "url": attempt_result["url"],
                    "match_count": attempt_result["match_count"],
                }

    return summary


async def main_async(args: argparse.Namespace) -> int:
    clip_paths = [Path(p) for p in args.clips]
    if args.clips_dir:
        clip_paths.extend(sorted(Path(args.clips_dir).glob("*.mp3")))

    clip_paths = sorted({path.resolve() for path in clip_paths if path.exists()})
    if not clip_paths:
        print("No clip files found.", file=sys.stderr)
        return 1

    attempts = build_attempts(
        offsets=parse_int_csv(args.offsets),
        durations=parse_int_csv(args.durations),
    )
    cuts_dir = Path(args.keep_cuts_dir) if args.keep_cuts_dir else None

    shazam = Shazam(segment_duration_seconds=args.segment_duration_seconds)
    results = []
    for clip_path in clip_paths:
        result = await sweep_clip(
            shazam=shazam,
            clip_path=clip_path,
            attempts=attempts,
            keep_cuts=bool(cuts_dir),
            cuts_dir=cuts_dir,
        )
        results.append(result)
        print(
            json.dumps(
                {
                    "clip": result["clip"],
                    "best_match": result["best_match"],
                }
            )
        )

    if args.output:
        Path(args.output).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clips", nargs="*", help="Clip MP3 files to recognize")
    parser.add_argument("--clips-dir", help="Directory containing MP3 clips")
    parser.add_argument(
        "--offsets",
        default="0,2,4,6,8,10,12",
        help="Comma-separated front-loaded offsets to try in seconds",
    )
    parser.add_argument(
        "--durations",
        default="5,8",
        help="Comma-separated short window durations to try in seconds",
    )
    parser.add_argument(
        "--segment-duration-seconds",
        type=int,
        default=10,
        help="shazamio segment duration setting for fingerprint generation",
    )
    parser.add_argument(
        "--keep-cuts-dir",
        help="Directory to keep generated probe cuts. If omitted, cuts are temporary.",
    )
    parser.add_argument("--output", help="Write full JSON results to this path")
    return parser.parse_args()


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
