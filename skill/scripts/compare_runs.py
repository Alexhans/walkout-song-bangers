#!/usr/bin/env python3
"""Compare a fresh skill run against committed baseline data.

Usage:
    python3 skill/scripts/compare_runs.py /tmp/fresh-run ufc-229
    python3 skill/scripts/compare_runs.py /tmp/fresh-run
"""

import argparse
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path


def fuzzy_match(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def normalize(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def find_best_match(fighter: str, candidates: list[dict]) -> dict | None:
    best = None
    best_score = 0.0
    for candidate in candidates:
        score = fuzzy_match(fighter, candidate["fighter"])
        if score > best_score:
            best_score = score
            best = candidate
    return best if best_score >= 0.6 else None


def spotify_kind(url: str) -> str:
    if "/track/" in (url or ""):
        return "track"
    if "/search/" in (url or ""):
        return "search"
    return "none"


def compare_event(fresh_path: Path, baseline_path: Path) -> dict:
    with open(fresh_path) as f:
        fresh = json.load(f)
    with open(baseline_path) as f:
        baseline = json.load(f)

    fresh_songs = fresh["songs"]
    baseline_songs = baseline["songs"]

    results = {
        "event": baseline["event"],
        "fresh_fighters": len(fresh_songs),
        "baseline_fighters": len(baseline_songs),
        "matched": 0,
        "song_diff": 0,
        "artist_diff": 0,
        "confidence_diff": 0,
        "spotify_diff": 0,
        "missing_from_fresh": [],
        "extra_in_fresh": [],
        "details": [],
    }

    matched_fresh_names = set()

    for baseline_entry in baseline_songs:
        match = find_best_match(baseline_entry["fighter"], fresh_songs)
        if match is None:
            results["missing_from_fresh"].append(baseline_entry["fighter"])
            continue

        matched_fresh_names.add(match["fighter"])
        results["matched"] += 1

        detail = {"fighter": baseline_entry["fighter"], "differences": []}

        if normalize(baseline_entry.get("song_title", "")) != normalize(match.get("song_title", "")):
            results["song_diff"] += 1
            detail["differences"].append(
                f'song: baseline="{baseline_entry.get("song_title", "")}" fresh="{match.get("song_title", "")}"'
            )

        if normalize(baseline_entry.get("artist", "")) != normalize(match.get("artist", "")):
            results["artist_diff"] += 1
            detail["differences"].append(
                f'artist: baseline="{baseline_entry.get("artist", "")}" fresh="{match.get("artist", "")}"'
            )

        if normalize(baseline_entry.get("confidence", "")) != normalize(match.get("confidence", "")):
            results["confidence_diff"] += 1
            detail["differences"].append(
                f'confidence: baseline="{baseline_entry.get("confidence", "")}" fresh="{match.get("confidence", "")}"'
            )

        baseline_spotify = spotify_kind(baseline_entry.get("spotify_url", ""))
        fresh_spotify = spotify_kind(match.get("spotify_url", ""))
        if baseline_spotify != fresh_spotify:
            results["spotify_diff"] += 1
            detail["differences"].append(
                f"spotify: baseline={baseline_spotify} fresh={fresh_spotify}"
            )

        if detail["differences"]:
            results["details"].append(detail)

    for fresh_entry in fresh_songs:
        if fresh_entry["fighter"] not in matched_fresh_names:
            results["extra_in_fresh"].append(fresh_entry["fighter"])

    return results


def print_report(results: dict):
    print(f"\n{'=' * 60}")
    print(f"Compare: {results['event']}")
    print(f"{'=' * 60}")
    print(f"Matched fighters: {results['matched']}/{results['baseline_fighters']}")
    print(f"Song diffs:       {results['song_diff']}")
    print(f"Artist diffs:     {results['artist_diff']}")
    print(f"Confidence diffs: {results['confidence_diff']}")
    print(f"Spotify diffs:    {results['spotify_diff']}")
    print()

    if results["missing_from_fresh"]:
        print("Missing from fresh run:")
        for fighter in results["missing_from_fresh"]:
            print(f"  {fighter}")
        print()

    if results["extra_in_fresh"]:
        print("Extra in fresh run:")
        for fighter in results["extra_in_fresh"]:
            print(f"  {fighter}")
        print()

    if results["details"]:
        print("Field differences:")
        for detail in results["details"]:
            print(f"  {detail['fighter']}")
            for diff in detail["differences"]:
                print(f"    {diff}")
        print()
    elif not results["missing_from_fresh"] and not results["extra_in_fresh"]:
        print("Fresh run matches committed baseline.\n")


def main():
    parser = argparse.ArgumentParser(description="Compare a fresh skill run against committed baseline data")
    parser.add_argument("data_dir", type=Path, help="Directory containing fresh output JSON files")
    parser.add_argument("slug", nargs="?", help="Event slug (e.g., ufc-229)")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent.parent
    baseline_dir = repo_root / "data"

    if args.slug:
        slugs = [args.slug]
    else:
        slugs = sorted(path.stem for path in args.data_dir.glob("*.json"))

    if not slugs:
        print(f"No JSON files found in {args.data_dir}")
        sys.exit(1)

    for slug in slugs:
        fresh_path = args.data_dir / f"{slug}.json"
        baseline_path = baseline_dir / f"{slug}.json"
        if not fresh_path.exists():
            print(f"Fresh output not found: {fresh_path}")
            continue
        if not baseline_path.exists():
            print(f"Baseline not found: {baseline_path}")
            continue
        print_report(compare_event(fresh_path, baseline_path))


if __name__ == "__main__":
    main()
