#!/usr/bin/env python3
"""Generate markdown files from walkout song JSON data files.

Usage:
    python3 skill/scripts/generate_md.py                    # all events
    python3 skill/scripts/generate_md.py data/ufc-229.json  # single event
"""

import json
import re
import sys
from pathlib import Path


def slugify(name: str) -> str:
    """Convert a name to a filename-safe slug."""
    s = name.lower().strip()
    s = re.sub(r"[''']", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def generate_md(json_path: Path) -> str:
    with open(json_path) as f:
        data = json.load(f)

    lines = []
    lines.append(f"# {data['event']}")
    lines.append("")
    lines.append(f"**Date:** {data['date']} | **Location:** {data['location']}")
    lines.append("")

    lines.append("| # | Fighter | Song | Artist | Confidence | Listen |")
    lines.append("|---|---------|------|--------|------------|--------|")

    for i, song in enumerate(data["songs"], 1):
        fighter_name = song["fighter"]
        fighter = f"[{fighter_name}](agg/by-fighter/{slugify(fighter_name)}.md)"
        title = song.get("song_title") or "—"
        artist = song.get("artist") or "—"
        confidence = song.get("confidence", "missing")
        url = song.get("spotify_url", "")
        notes = song.get("notes", "")

        if not url or confidence == "missing":
            listen = "—"
        elif "/search/" in url:
            listen = f"[Search]({url})"
        elif "/track/" in url:
            listen = f"[Spotify]({url})"
        else:
            listen = f"[Link]({url})"

        # For mashups with multiple spotify links in notes, add extra links
        if notes and "https://open.spotify.com/track/" in notes:
            extra_links = re.findall(
                r"(\w[\w\s/]+?):\s*(https://open\.spotify\.com/track/\S+)", notes
            )
            if extra_links:
                parts = [f"[{name.strip()}]({link})" for name, link in extra_links]
                listen = " / ".join(parts)

        lines.append(
            f"| {i} | {fighter} | {title} | {artist} | {confidence} | {listen} |"
        )

    # Coverage stats
    total = len(data["songs"])
    found = sum(1 for s in data["songs"] if s.get("confidence") != "missing")
    direct = sum(
        1
        for s in data["songs"]
        if s.get("spotify_url") and "/track/" in s.get("spotify_url", "")
    )
    fallback = sum(
        1
        for s in data["songs"]
        if s.get("spotify_url") and "/search/" in s.get("spotify_url", "")
    )

    lines.append("")
    coverage_parts = [f"**Coverage:** {found}/{total} fighters ({100*found//total}%)"]
    if direct:
        coverage_parts.append(f"{direct} direct Spotify links")
    if fallback:
        coverage_parts.append(f"{fallback} search fallbacks")
    lines.append(" | ".join(coverage_parts))

    lines.append("")
    lines.append("---")

    sources = data.get("source_urls", [])
    if sources:
        source_links = [f"[{i+1}]({url})" for i, url in enumerate(sources)]
        lines.append(f"*Sources: {', '.join(source_links)}*")

    lines.append(f"*Generated: {data.get('generated_at', 'unknown')}*")
    lines.append("")

    return "\n".join(lines)


def main():
    repo_root = Path(__file__).parent.parent.parent
    data_dir = repo_root / "data"
    viz_dir = repo_root / "viz"
    viz_dir.mkdir(exist_ok=True)

    # Process specific files if given as args, otherwise all JSON files in data/
    if len(sys.argv) > 1:
        json_files = [Path(p) for p in sys.argv[1:]]
    else:
        json_files = sorted(data_dir.glob("*.json"))

    if not json_files:
        print("No JSON files found in data/")
        sys.exit(1)

    for json_path in json_files:
        md_path = viz_dir / json_path.with_suffix(".md").name
        md_content = generate_md(json_path)
        md_path.write_text(md_content)
        print(f"{json_path.name} -> viz/{md_path.name}")


if __name__ == "__main__":
    main()
