#!/usr/bin/env python3
"""Regenerate the event table in README.md from data/*.json files.

Replaces everything between <!-- BEGIN EVENTS --> and <!-- END EVENTS -->
with an auto-generated table sorted by event date.
"""

import json
from pathlib import Path

DATA_DIR = Path("data")
AGG_DIR = Path("agg")
README = Path("README.md")
BEGIN = "<!-- BEGIN EVENTS -->"
END = "<!-- END EVENTS -->"
BEGIN_SPOTIFY = "<!-- BEGIN SPOTIFY -->"
END_SPOTIFY = "<!-- END SPOTIFY -->"


def event_sort_key(event):
    """Sort by date, then by event name."""
    return (event.get("date", ""), event.get("event", ""))


def generate_table(events):
    """Generate the markdown table from event data."""
    lines = [
        "| Year | Event | Fighters | Gold | Silver | Bronze | Missing |",
        "|------|-------|----------|------|--------|--------|---------|",
    ]

    for event in sorted(events, key=event_sort_key, reverse=True):
        songs = event.get("songs", [])
        slug = event["event_slug"]
        name = event["event"]
        year = event.get("date", "")[:4]
        year_link = f"[{year}](viz/agg/by-year/{year}.md)" if year else ""
        total = len(songs)
        gold = sum(1 for s in songs if s["confidence"] == "gold")
        silver = sum(1 for s in songs if s["confidence"] == "silver")
        bronze = sum(1 for s in songs if s["confidence"] == "bronze")
        missing = sum(1 for s in songs if s["confidence"] == "missing")
        lines.append(f"| {year_link} | [{name}](viz/{slug}.md) | {total} | {gold} | {silver} | {bronze} | {missing} |")

    return "\n".join(lines)


def generate_spotify_table(playlists: dict) -> str:
    lines = ["| Year | Playlist |", "|------|----------|"]
    for year, pid in sorted(playlists.items(), reverse=True):
        lines.append(f"| {year} | [UFC Walkout Songs {year}](https://open.spotify.com/playlist/{pid}) |")
    return "\n".join(lines)


def main():
    readme_text = README.read_text()

    begin_idx = readme_text.index(BEGIN)
    end_idx = readme_text.index(END) + len(END)

    events = []
    for p in sorted(DATA_DIR.glob("*.json")):
        with open(p) as f:
            events.append(json.load(f))

    table = generate_table(events)
    new_section = f"{BEGIN}\n{table}\n{END}"

    new_readme = readme_text[:begin_idx] + new_section + readme_text[end_idx:]

    if new_readme != readme_text:
        README.write_text(new_readme)
        print(f"README.md updated ({len(events)} events)")
    else:
        print(f"README.md already up to date ({len(events)} events)")

    # Update Spotify section if the playlists file exists
    spotify_path = AGG_DIR / "spotify-playlists.json"
    if not spotify_path.exists():
        return
    playlists = json.loads(spotify_path.read_text())
    readme_text = README.read_text()
    start = readme_text.find(BEGIN_SPOTIFY)
    stop = readme_text.find(END_SPOTIFY)
    if start == -1 or stop == -1:
        return
    new_section = BEGIN_SPOTIFY + "\n" + generate_spotify_table(playlists) + "\n" + END_SPOTIFY
    new_readme = readme_text[:start] + new_section + readme_text[stop + len(END_SPOTIFY):]
    if new_readme != readme_text:
        README.write_text(new_readme)
        print("README.md Spotify section updated")


if __name__ == "__main__":
    main()
