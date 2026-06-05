#!/usr/bin/env python3
"""Evaluate whether a source fixture is correctly accepted or rejected by source gating.

Usage:
    python3 skill/scripts/eval_source_gating.py
    python3 skill/scripts/eval_source_gating.py lowkick-pre-fight-328
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent.parent
FIXTURE_DIR = REPO_ROOT / "evals" / "source-gating"

# If any of these appear, the source is invalid for bronze/silver coverage.
BANNED_PHRASES = [
    "tonight",
    "potential walkout songs",
    "previous octagon appearances",
    "have walked out to",
    "used before",
    "usually walks out to",
    "has used",
    "have used",
    "known for",
    "typically marches",
    "what walkout songs do",
]

VALID_PHRASES = [
    "walked out to",
    "confirmed",
    "walkout songs",
    "entrance music used by",
]


def classify_source(text: str) -> tuple[str, list[str]]:
    lowered = text.lower()
    hits = [phrase for phrase in BANNED_PHRASES if phrase in lowered]
    if hits:
        return ("invalid_guesswork", hits)
    positive_hits = [phrase for phrase in VALID_PHRASES if phrase in lowered]
    if positive_hits:
        return ("valid_post_event", positive_hits)
    return ("invalid_guesswork", [])


def extract_pairs(text: str) -> list[dict]:
    pairs: list[dict] = []
    for line in text.splitlines():
        m = re.match(r'\s*[*-]\s*(.+?):\s*"(.*?)"\s+by\s+(.+?)\s*$', line)
        if m:
            pairs.append(
                {
                    "fighter": m.group(1).strip(),
                    "song_title": m.group(2).strip(),
                    "artist": m.group(3).strip(),
                }
            )
    return pairs


def extract_fighters(text: str) -> list[str]:
    return [pair["fighter"] for pair in extract_pairs(text)]


def eval_fixture(label: str) -> dict:
    txt_path = FIXTURE_DIR / f"{label}.txt"
    expected_path = FIXTURE_DIR / f"{label}.expected.json"
    if not txt_path.exists():
        raise FileNotFoundError(f"Fixture not found: {txt_path}")
    if not expected_path.exists():
        raise FileNotFoundError(f"Expected file not found: {expected_path}")

    text = txt_path.read_text(encoding="utf-8")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))

    classification, hits = classify_source(text)
    pairs = extract_pairs(text)
    fighters = [pair["fighter"] for pair in pairs]
    hit_set = {h.lower() for h in hits}

    missing_hits: list[str] = []
    missing_fighters: list[str] = []
    missing_pairs: list[dict] = []

    if expected["expected_classification"] == "invalid_guesswork":
        missing_hits = [
            p for p in expected["must_trigger_phrases"] if p.lower() not in hit_set
        ]
        missing_fighters = [
            f for f in expected["must_reject_fighters"] if f not in fighters
        ]
        ok = (
            classification == expected["expected_classification"]
            and not missing_hits
            and not missing_fighters
        )
    else:
        missing_hits = [
            p for p in expected["must_include_phrases"] if p.lower() not in hit_set
        ]
        missing_fighters = [
            f for f in expected["must_extract_fighters"] if f not in fighters
        ]
        for expected_pair in expected["must_extract_pairs"]:
            if expected_pair not in pairs:
                missing_pairs.append(expected_pair)
        ok = (
            classification == expected["expected_classification"]
            and not missing_hits
            and not missing_fighters
            and not missing_pairs
        )

    return {
        "label": label,
        "ok": ok,
        "classification": classification,
        "expected_classification": expected["expected_classification"],
        "hits": hits,
        "missing_hits": missing_hits,
        "fighters_found": fighters,
        "missing_fighters": missing_fighters,
        "pairs_found": pairs,
        "missing_pairs": missing_pairs,
    }


def print_result(result: dict) -> None:
    status = "PASS" if result["ok"] else "FAIL"
    print(f"{status}: {result['label']}")
    print(f"  classification: {result['classification']}")
    print(f"  expected:       {result['expected_classification']}")
    print(f"  signal hits:    {', '.join(result['hits']) if result['hits'] else '(none)'}")
    if result["missing_hits"]:
        print(f"  missing hits:   {', '.join(result['missing_hits'])}")
    if result["missing_fighters"]:
        print(f"  missing names:  {', '.join(result['missing_fighters'])}")
    if result["missing_pairs"]:
        print("  missing pairs:")
        for pair in result["missing_pairs"]:
            print(f"    - {pair['fighter']}: \"{pair['song_title']}\" by {pair['artist']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run source-gating eval fixtures")
    parser.add_argument("label", nargs="?", help="Fixture label, e.g. lowkick-pre-fight-328")
    args = parser.parse_args()

    labels = [args.label] if args.label else sorted(p.stem for p in FIXTURE_DIR.glob("*.txt"))
    if not labels:
        print(f"No source-gating fixtures found in {FIXTURE_DIR}")
        return 1

    any_fail = False
    for label in labels:
        result = eval_fixture(label)
        print_result(result)
        any_fail = any_fail or not result["ok"]

    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
