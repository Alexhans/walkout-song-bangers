#!/usr/bin/env python3
"""
generate-yearly-playlists.py
Generates Spotify playlist text files grouped by year

Usage:
    python3 generate-yearly-playlists.py [year]  # Specific year
    python3 generate-yearly-playlists.py --all   # All years
    
Output: agg/spotify/[year]/[event_slug].txt
"""

import json
import os
import argparse
from pathlib import Path


def extract_spotify_links(data):
    """Extract all Spotify URLs from event data."""
    urls = []
    for song in data.get("songs", []):
        url = song.get("spotify_url", "")
        if url and url.strip():
            urls.append(url.strip())
    return urls


def get_events_for_year(data_dir, year):
    """Find all JSON files for a given year."""
    events = []
    for json_file in Path(data_dir).glob("*.json"):
        with open(json_file, "r") as f:
            try:
                data = json.load(f)
                event_date = data.get("date", "")
                if event_date.startswith(f"{year}-"):
                    events.append((json_file, data))
            except json.JSONDecodeError:
                continue
    return events


def write_playlist_txt(output_path, urls):
    """Write URLs to plain text file."""
    with open(output_path, "w") as f:
        f.write("\n".join(urls))
        if urls:
            f.write("\n")


def generate_for_year(data_dir, year, output_dir):
    """Generate all playlists for a specific year."""
    print(f"\nGenerating playlists for {year}...")
    
    events = get_events_for_year(data_dir, year)
    
    if not events:
        print(f"  No events found for {year}")
        return
    
    output_path = Path(output_dir) / year
    output_path.mkdir(parents=True, exist_ok=True)
    
    all_urls = []  # Collect all tracks for combined playlist
    
    for json_file, data in events:
        event_slug = json_file.stem
        urls = extract_spotify_links(data)
        
        output_file = output_path / f"{event_slug}.txt"
        write_playlist_txt(output_file, urls)
        
        print(f"  ✓ {event_slug}: {len(urls)} tracks")
        all_urls.extend(urls)
    
    # Create combined yearly playlist
    combined_file = output_path / "playlists.txt"
    write_playlist_txt(combined_file, all_urls)
    
    print(f"\n  Total: {len(events)} events written to {output_dir}/{year}")
    print(f"  ✓ playlists.txt: {len(all_urls)} total tracks")


def generate_for_all_years(data_dir, output_dir):
    """Generate playlists for all years in the database."""
    years = set()
    for json_file in Path(data_dir).glob("*.json"):
        with open(json_file, "r") as f:
            try:
                data = json.load(f)
                event_date = data.get("date", "")
                if event_date:
                    year = event_date.split("-")[0]
                    years.add(year)
            except json.JSONDecodeError:
                continue
    
    years = sorted(years)
    print(f"Found {len(years)} years: {', '.join(years)}")
    
    for year in years:
        generate_for_year(data_dir, year, output_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Generate Spotify playlist text files"
    )
    parser.add_argument("year", nargs="?", default=None, help="Specific year (e.g., 2026)")
    parser.add_argument("--all", action="store_true", help="Generate for all years")
    
    args = parser.parse_args()
    
    # Paths
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    output_dir = script_dir.parent / "agg" / "spotify"
    
    if args.all or not args.year:
        generate_for_all_years(data_dir, output_dir)
    else:
        generate_for_year(data_dir, args.year, output_dir)
    
    print("\nDone!")


if __name__ == "__main__":
    main()
