#!/usr/bin/env python3
"""Evaluate pipeline output against ground truth.

Usage:
    python3 scripts/eval.py                           # eval all events with ground truth
    python3 scripts/eval.py ufc-229                   # eval single event by slug
    python3 scripts/eval.py events/ufc-229.json       # eval single event by path
"""

import json
import sys
from pathlib import Path
from difflib import SequenceMatcher


def fuzzy_match(a: str, b: str) -> float:
    """Case-insensitive fuzzy string similarity (0.0 to 1.0)."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def find_best_match(fighter: str, candidates: list[dict]) -> dict | None:
    """Find the best fuzzy name match for a fighter in the candidates list."""
    best = None
    best_score = 0.0
    for c in candidates:
        score = fuzzy_match(fighter, c["fighter"])
        if score > best_score:
            best_score = score
            best = c
    return best if best_score >= 0.6 else None


def eval_event(output_path: Path, gt_path: Path) -> dict:
    """Compare pipeline output against ground truth and return scores."""
    with open(output_path) as f:
        output = json.load(f)
    with open(gt_path) as f:
        gt = json.load(f)

    gt_songs = gt["songs"]
    # All output songs count for coverage (including missing — the skill listed them)
    out_songs = output["songs"]

    # Split ground truth into coverage-only (empty song) and fully verified
    gt_verified = [s for s in gt_songs if s.get("song_title")]
    gt_coverage_only = [s for s in gt_songs if not s.get("song_title")]

    results = {
        "event": gt["event"],
        "gt_fighters": len(gt_songs),
        "gt_verified": len(gt_verified),
        "out_fighters": len(out_songs),
        "matched": 0,
        "song_correct": 0,
        "song_checked": 0,
        "artist_correct": 0,
        "artist_checked": 0,
        "spotify_direct": 0,
        "spotify_search": 0,
        "spotify_none": 0,
        "details": [],
    }

    for gt_entry in gt_songs:
        match = find_best_match(gt_entry["fighter"], out_songs)
        has_song = bool(gt_entry.get("song_title"))

        detail = {
            "fighter": gt_entry["fighter"],
            "expected_song": gt_entry.get("song_title", ""),
            "expected_artist": gt_entry.get("artist", ""),
        }

        if match is None:
            detail["status"] = "NOT FOUND"
            detail["got_song"] = ""
            detail["got_artist"] = ""
        else:
            results["matched"] += 1
            detail["got_song"] = match["song_title"]
            detail["got_artist"] = match["artist"]

            if has_song:
                # Only score song/artist accuracy for verified entries
                results["song_checked"] += 1
                results["artist_checked"] += 1

                song_score = fuzzy_match(gt_entry["song_title"], match["song_title"])
                artist_score = fuzzy_match(gt_entry["artist"], match["artist"])

                if song_score >= 0.7:
                    results["song_correct"] += 1
                    detail["song_match"] = f"OK ({song_score:.0%})"
                else:
                    detail["song_match"] = f"WRONG ({song_score:.0%})"

                if artist_score >= 0.6:
                    results["artist_correct"] += 1
                    detail["artist_match"] = f"OK ({artist_score:.0%})"
                else:
                    detail["artist_match"] = f"WRONG ({artist_score:.0%})"
            else:
                detail["song_match"] = "UNVERIFIED"
                detail["artist_match"] = "UNVERIFIED"

            url = match.get("spotify_url", "")
            if "/track/" in url:
                results["spotify_direct"] += 1
            elif "/search/" in url:
                results["spotify_search"] += 1
            else:
                results["spotify_none"] += 1

            detail["status"] = "MATCHED"

        results["details"].append(detail)

    return results


def print_report(results: dict):
    """Print a human-readable eval report."""
    r = results
    total = r["gt_fighters"]
    verified = r["gt_verified"]
    checked_s = r["song_checked"]
    checked_a = r["artist_checked"]

    print(f"\n{'='*60}")
    print(f"Eval: {r['event']}")
    print(f"{'='*60}")
    print(f"Coverage:  {r['matched']}/{total} fighters found ({pct(r['matched'], total)})")
    print(f"Verified:  {verified} fighters with human-verified songs")
    print(f"Songs:     {r['song_correct']}/{checked_s} correct ({pct(r['song_correct'], checked_s)})")
    print(f"Artists:   {r['artist_correct']}/{checked_a} correct ({pct(r['artist_correct'], checked_a)})")
    print(f"Spotify:   {r['spotify_direct']} direct | {r['spotify_search']} search | {r['spotify_none']} none")
    print()

    # Show mismatches and missing
    issues = [d for d in r["details"] if d["status"] == "NOT FOUND"
              or d.get("song_match", "").startswith("WRONG")
              or d.get("artist_match", "").startswith("WRONG")]

    if issues:
        print("Issues:")
        for d in issues:
            if d["status"] == "NOT FOUND":
                print(f"  MISSING: {d['fighter']}")
            else:
                if d.get("song_match", "").startswith("WRONG"):
                    print(f"  SONG:    {d['fighter']}: expected \"{d['expected_song']}\" got \"{d['got_song']}\"")
                if d.get("artist_match", "").startswith("WRONG"):
                    print(f"  ARTIST:  {d['fighter']}: expected \"{d['expected_artist']}\" got \"{d['got_artist']}\"")
        print()
    else:
        print("No issues found.\n")


def pct(n: int, total: int) -> str:
    if total == 0:
        return "N/A"
    return f"{100 * n / total:.0f}%"


def main():
    base = Path(__file__).parent.parent
    events_dir = base / "events"
    gt_dir = base / "evals" / "ground-truth"

    if len(sys.argv) > 1:
        # Single event
        arg = sys.argv[1]
        if arg.endswith(".json"):
            slug = Path(arg).stem
        else:
            slug = arg
        output_path = events_dir / f"{slug}.json"
        gt_path = gt_dir / f"{slug}.expected.json"

        if not output_path.exists():
            print(f"Output not found: {output_path}")
            sys.exit(1)
        if not gt_path.exists():
            print(f"Ground truth not found: {gt_path}")
            sys.exit(1)

        results = eval_event(output_path, gt_path)
        print_report(results)
    else:
        # All events with ground truth
        gt_files = sorted(gt_dir.glob("*.expected.json"))
        if not gt_files:
            print("No ground truth files found in evals/ground-truth/")
            sys.exit(1)

        for gt_path in gt_files:
            slug = gt_path.stem.replace(".expected", "")
            output_path = events_dir / f"{slug}.json"
            if not output_path.exists():
                print(f"Skipping {slug}: no pipeline output found")
                continue
            results = eval_event(output_path, gt_path)
            print_report(results)


if __name__ == "__main__":
    main()
