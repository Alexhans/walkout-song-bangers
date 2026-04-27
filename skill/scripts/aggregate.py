#!/usr/bin/env python3
"""Aggregate walkout song data by year or by fighter.

Usage:
    python3 skill/scripts/aggregate.py                          # all aggregations
    python3 skill/scripts/aggregate.py --year 2026              # single year
    python3 skill/scripts/aggregate.py --fighter "Max Holloway" # single fighter
    python3 skill/scripts/aggregate.py --year 2026 --urls-only  # Spotify URLs only
"""

import datetime
import html as html_mod
import json
import re
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path("data")
AGG_DIR = Path("agg")


def load_all_events():
    """Load all event JSON files from data/."""
    events = []
    for p in sorted(DATA_DIR.glob("*.json")):
        with open(p) as f:
            events.append(json.load(f))
    return events


def slugify(name: str) -> str:
    """Convert a name to a filename-safe slug."""
    s = name.lower().strip()
    s = re.sub(r"[''']", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def is_playable_url(url: str) -> bool:
    """Check if a Spotify URL is a direct track link (not a search fallback)."""
    return url.startswith("https://open.spotify.com/track/")


def aggregate_by_year(events):
    """Group all songs by year from event date."""
    by_year = defaultdict(list)

    for event in events:
        year = event.get("date", "")[:4]
        if not year:
            continue
        for song in event.get("songs", []):
            by_year[year].append({
                "fighter": song["fighter"],
                "song_title": song["song_title"],
                "artist": song["artist"],
                "confidence": song["confidence"],
                "spotify_url": song["spotify_url"],
                "event": event["event"],
                "event_slug": event["event_slug"],
                "date": event["date"],
            })

    results = {}
    for year, tracks in sorted(by_year.items()):
        with_song = [t for t in tracks if t["confidence"] != "missing"]
        playable = [t for t in with_song if is_playable_url(t["spotify_url"])]
        unique_urls = set(t["spotify_url"] for t in playable)

        results[year] = {
            "year": int(year),
            "events": len(set(t["event_slug"] for t in tracks)),
            "tracks": tracks,
            "stats": {
                "total_fighters": len(tracks),
                "with_song": len(with_song),
                "playable_tracks": len(playable),
                "unique_playable_tracks": len(unique_urls),
                "missing": len(tracks) - len(with_song),
            },
        }

    return results


def aggregate_by_fighter(events):
    """Group all songs by fighter across events."""
    by_fighter = defaultdict(list)

    for event in events:
        for song in event.get("songs", []):
            by_fighter[song["fighter"]].append({
                "song_title": song["song_title"],
                "artist": song["artist"],
                "confidence": song["confidence"],
                "spotify_url": song["spotify_url"],
                "event": event["event"],
                "event_slug": event["event_slug"],
                "date": event["date"],
            })

    results = {}
    for fighter, appearances in sorted(by_fighter.items()):
        with_song = [a for a in appearances if a["confidence"] != "missing"]
        unique_songs = set(
            (a["song_title"], a["artist"])
            for a in with_song
            if a["song_title"]
        )

        appearances.sort(key=lambda a: a["date"], reverse=True)
        results[fighter] = {
            "fighter": fighter,
            "slug": slugify(fighter),
            "appearances": len(appearances),
            "walkouts": appearances,
            "stats": {
                "events": len(appearances),
                "with_song": len(with_song),
                "missing": len(appearances) - len(with_song),
                "unique_songs": len(unique_songs),
            },
        }

    return results


def aggregate_by_song(events):
    """Count appearances of each song, keyed by Spotify URL."""
    counts = defaultdict(lambda: {"artist": "", "song_title": "", "spotify_url": "", "count": 0, "fighters": set()})

    for event in events:
        for song in event.get("songs", []):
            url = song["spotify_url"]
            if not url or song["confidence"] == "missing":
                continue
            entry = counts[url]
            entry["spotify_url"] = url
            entry["artist"] = song["artist"]
            entry["song_title"] = song["song_title"]
            entry["count"] += 1
            entry["fighters"].add(song["fighter"])

    # Convert sets to counts for JSON serialization
    for entry in counts.values():
        entry["unique_fighters"] = len(entry["fighters"])
        del entry["fighters"]

    return sorted(counts.values(), key=lambda x: (-x["unique_fighters"], -x["count"], x["artist"], x["song_title"]))


def write_by_song(song_data):
    """Write the by-song aggregation file."""
    AGG_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AGG_DIR / "by-song.json"
    with open(out_path, "w") as f:
        json.dump(song_data, f, indent=2, ensure_ascii=False)
    return out_path


def write_by_year(year_data, year):
    """Write a single year aggregation file."""
    out_dir = AGG_DIR / "by-year"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{year}.json"
    with open(out_path, "w") as f:
        json.dump(year_data, f, indent=2, ensure_ascii=False)
    return out_path


def write_by_fighter(fighter_data, slug):
    """Write a single fighter aggregation file."""
    out_dir = AGG_DIR / "by-fighter"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{slug}.json"
    with open(out_path, "w") as f:
        json.dump(fighter_data, f, indent=2, ensure_ascii=False)
    return out_path


VIZ_AGG_DIR = Path("viz/agg")


def write_viz_top_songs(song_data):
    """Write a markdown table of top walkout songs."""
    VIZ_AGG_DIR.mkdir(parents=True, exist_ok=True)
    out_path = VIZ_AGG_DIR / "top-songs.md"
    lines = [
        "# Top Walkout Songs",
        "",
        "Songs sorted by number of unique fighters who have used them.",
        "",
        "| # | Song | Artist | Unique Fighters | Total Plays | Spotify |",
        "|---|------|--------|-----------------|-------------|---------|",
    ]
    for i, s in enumerate(song_data, 1):
        if s["unique_fighters"] < 2:
            break
        url = s["spotify_url"]
        link = f"[Listen]({url})" if is_playable_url(url) else ""
        lines.append(f"| {i} | {s['song_title']} | {s['artist']} | {s['unique_fighters']} | {s['count']} | {link} |")
    out_path.write_text("\n".join(lines) + "\n")
    return out_path


_UFCSTATS_EVENTS_URL = "http://www.ufcstats.com/statistics/events/completed?page=all"
_MONTH = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}


def _parse_iso_date(date_text: str) -> str:
    dm = re.match(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", date_text.strip())
    if not dm:
        return ""
    mon = _MONTH.get(dm.group(1).lower()[:3])
    return f"{int(dm.group(3)):04d}-{mon:02d}-{int(dm.group(2)):02d}" if mon else ""


def _refresh_ufcstats_events(events_path: Path) -> list[dict]:
    """Re-scrape ufcstats only when the last known event date has passed."""
    existing: list[dict] = []
    if events_path.exists():
        with open(events_path) as f:
            existing = json.load(f)

    today = datetime.date.today().isoformat()
    last_date = max((e["date"] for e in existing), default="")
    if last_date > today:
        return existing

    # Last known event has passed — fetch the full index for new entries
    try:
        with urllib.request.urlopen(_UFCSTATS_EVENTS_URL, timeout=15) as r:
            index_html = r.read().decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"Warning: could not refresh ufcstats events: {exc}", file=sys.stderr)
        return existing

    known_names = {e["name"] for e in existing}
    new_events: list[dict] = []
    for m in re.finditer(
        r'<a\s+href="(?P<url>http://www\.ufcstats\.com/event-details/[^"]+)"[^>]*>(?P<name>[^<]+)</a>',
        index_html,
    ):
        name = " ".join(html_mod.unescape(m.group("name")).split())
        if not name or name in known_names:
            continue
        known_names.add(name)
        try:
            with urllib.request.urlopen(m.group("url"), timeout=15) as r:
                event_html = r.read().decode("utf-8", errors="replace")
            date_m = re.search(r"Date:\s*</i>\s*([^<]+)</li>", event_html, re.I)
            if not date_m:
                text = html_mod.unescape(re.sub(r"<[^>]+>", " ", event_html))
                date_m = re.search(r"\bDate:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})\b", text)
            date = _parse_iso_date(date_m.group(1)) if date_m else ""
            if date:
                new_events.append({"name": name, "date": date})
        except Exception:
            continue

    if new_events:
        new_events.sort(key=lambda e: e["date"])
        updated = existing + new_events
        with open(events_path, "w") as f:
            json.dump(updated, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"ufcstats-events.json: added {len(new_events)} event(s)")
        return updated

    return existing


def _load_ufcstats_event_counts():
    """Count total UFC events per year from agg/ufcstats-events.json, up to today."""
    events_path = AGG_DIR / "ufcstats-events.json"
    if not events_path.exists():
        return {}
    today = datetime.date.today().isoformat()
    counts: dict[str, int] = {}
    for event in _refresh_ufcstats_events(events_path):
        if event.get("date", "") <= today:
            year = event["date"][:4]
            counts[year] = counts.get(year, 0) + 1
    return counts


def write_viz_by_year(year_results):
    """Write a markdown summary table of all years."""
    VIZ_AGG_DIR.mkdir(parents=True, exist_ok=True)
    out_path = VIZ_AGG_DIR / "by-year.md"
    event_counts = _load_ufcstats_event_counts()
    today = datetime.date.today().isoformat()
    lines = [
        "# Walkout Songs by Year",
        "",
        "| Year | Events | Event Coverage | Songs Found | Unique Playable | Missing | Song Coverage (parsed events) |",
        "|------|--------|----------------|-------------|-----------------|---------|-------------------------------|",
    ]
    for year in sorted(year_results.keys()):
        data = year_results[year]
        s = data["stats"]
        total = s["total_fighters"]
        song_cov = f"{s['with_song'] / total * 100:.0f}%" if total else "0%"
        total_events = event_counts.get(str(year))
        past_covered = len(set(t["event_slug"] for t in data["tracks"] if t["date"] <= today))
        if total_events:
            events_cell = f"[{past_covered}/{total_events}](by-year/{year}.md)"
            event_cov = f"{past_covered / total_events * 100:.0f}%"
        else:
            events_cell = str(past_covered)
            event_cov = ""
        lines.append(f"| {year} | {events_cell} | {event_cov} | {s['with_song']} | {s['unique_playable_tracks']} | {s['missing']} | {song_cov} |")
    out_path.write_text("\n".join(lines) + "\n")
    return out_path


def write_viz_year_page(year: int, year_data, events_for_year: list):
    """Write a per-year viz page: stats + flat song table + event sections."""
    out_dir = VIZ_AGG_DIR / "by-year"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{year}.md"

    current_year = datetime.date.today().year
    nav_parts = []
    if year - 1 >= 2016:
        nav_parts.append(f"[← {year - 1}]({year - 1}.md)")
    if year + 1 <= current_year:
        nav_parts.append(f"[{year + 1} →]({year + 1}.md)")
    nav = " | ".join(nav_parts)

    lines = [f"# {year} Walkout Songs", ""]
    if nav:
        lines += [nav, ""]

    if not year_data or not events_for_year:
        lines.append("No events recorded for this year yet.")
        out_path.write_text("\n".join(lines) + "\n")
        return out_path

    s = year_data["stats"]
    event_counts = _load_ufcstats_event_counts()
    total_events = event_counts.get(str(year), "?")
    today = datetime.date.today().isoformat()
    past_covered = len(set(t["event_slug"] for t in year_data["tracks"] if t["date"] <= today))
    song_cov = f"{s['with_song'] / s['total_fighters'] * 100:.0f}%" if s["total_fighters"] else "0%"
    lines += [
        f"{past_covered}/{total_events} events · {s['with_song']} songs found · {song_cov} song coverage (parsed events)",
        "",
    ]

    # Flat song table — aggregate by spotify_url, sort by play count
    song_counts: dict[str, dict] = {}
    for event in events_for_year:
        for song in event.get("songs", []):
            if song["confidence"] == "missing" or not song["spotify_url"]:
                continue
            url = song["spotify_url"]
            if url not in song_counts:
                song_counts[url] = {
                    "song_title": song["song_title"],
                    "artist": song["artist"],
                    "spotify_url": url,
                    "fighter_counts": {},
                }
            fc = song_counts[url]["fighter_counts"]
            fc[song["fighter"]] = fc.get(song["fighter"], 0) + 1

    sorted_songs = sorted(
        song_counts.values(),
        key=lambda x: (-sum(x["fighter_counts"].values()), x["artist"].lower(), x["song_title"].lower()),
    )
    lines += [
        "## Songs",
        "",
        "| Song | Artist | Fighter(s) | Spotify |",
        "|------|--------|------------|---------|",
    ]
    for entry in sorted_songs:
        parts = []
        for f, count in entry["fighter_counts"].items():
            label = f"[{f}](../by-fighter/{slugify(f)}.md)"
            if count > 1:
                label += f" (×{count})"
            parts.append(label)
        fighters_str = ", ".join(parts)
        url = entry["spotify_url"]
        link = f"[Listen]({url})" if is_playable_url(url) else ""
        lines.append(f"| {entry['song_title']} | {entry['artist']} | {fighters_str} | {link} |")

    lines += [""]

    # Event sections — chronological
    lines += ["## Events", ""]
    for event in sorted(events_for_year, key=lambda e: e["date"]):
        songs = event.get("songs", [])
        found = sum(1 for sg in songs if sg["confidence"] != "missing")
        total = len(songs)
        slug = event["event_slug"]
        event_link = f"[{event['event']}](../../../{slug}.md)"
        lines += [
            f"### {event_link} — {found}/{total} songs",
            "",
            "| Fighter | Song | Artist | Spotify |",
            "|---------|------|--------|---------|",
        ]
        for song in songs:
            fighter_link = f"[{song['fighter']}](../by-fighter/{slugify(song['fighter'])}.md)"
            if song["confidence"] == "missing":
                lines.append(f"| {fighter_link} | — | — | |")
            else:
                url = song["spotify_url"]
                link = f"[Listen]({url})" if is_playable_url(url) else ""
                lines.append(f"| {fighter_link} | {song['song_title']} | {song['artist']} | {link} |")
        lines.append("")

    out_path.write_text("\n".join(lines) + "\n")
    return out_path


def write_viz_fighter(fighter_data):
    """Write a single fighter markdown viz."""
    out_dir = VIZ_AGG_DIR / "by-fighter"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{fighter_data['slug']}.md"
    lines = [
        f"# {fighter_data['fighter']}",
        "",
        f"{fighter_data['appearances']} event(s) | {fighter_data['stats']['with_song']} song(s) found | {fighter_data['stats']['unique_songs']} unique",
        "",
        "| Year | Event | Song | Artist | Spotify |",
        "|------|-------|------|--------|---------|",
    ]
    for w in fighter_data["walkouts"]:
        event_link = f"[{w['event']}](../../{w['event_slug']}.md)"
        year = w["date"][:4]
        year_link = f"[{year}](../agg/by-year/{year}.md)"
        if w["confidence"] == "missing":
            lines.append(f"| {year_link} | {event_link} | — | — | |")
        else:
            url = w["spotify_url"]
            link = f"[Listen]({url})" if is_playable_url(url) else ""
            lines.append(f"| {year_link} | {event_link} | {w['song_title']} | {w['artist']} | {link} |")
    out_path.write_text("\n".join(lines) + "\n")
    return out_path


def main():
    args = sys.argv[1:]
    urls_only = "--urls-only" in args
    if urls_only:
        args.remove("--urls-only")

    filter_year = None
    filter_fighter = None

    i = 0
    while i < len(args):
        if args[i] == "--year" and i + 1 < len(args):
            filter_year = args[i + 1]
            i += 2
        elif args[i] == "--fighter" and i + 1 < len(args):
            filter_fighter = args[i + 1]
            i += 2
        else:
            i += 1

    t0 = time.perf_counter()
    events = load_all_events()
    t_load = time.perf_counter()

    # By year
    if not filter_fighter:
        year_results = aggregate_by_year(events)
        t_year = time.perf_counter()

        if filter_year:
            years_to_write = {filter_year: year_results.get(filter_year)}
            if years_to_write[filter_year] is None:
                print(f"No data for year {filter_year}")
                sys.exit(1)
        else:
            years_to_write = year_results

        if urls_only:
            data = years_to_write[filter_year or sorted(years_to_write.keys())[-1]]
            seen = set()
            for t in data["tracks"]:
                url = t["spotify_url"]
                if is_playable_url(url) and url not in seen:
                    seen.add(url)
                    print(url)
            return

        for year, data in sorted(years_to_write.items()):
            path = write_by_year(data, year)
            s = data["stats"]
            print(f"{path} -> {s['with_song']} songs, {s['unique_playable_tracks']} unique playable, {s['missing']} missing")

        print(f"\n  load: {(t_load - t0)*1000:.1f}ms | aggregate: {(t_year - t_load)*1000:.1f}ms | total: {(time.perf_counter() - t0)*1000:.1f}ms")

    # By fighter
    if not filter_year:
        fighter_results = aggregate_by_fighter(events)
        t_fighter = time.perf_counter()

        if filter_fighter:
            matches = {k: v for k, v in fighter_results.items() if filter_fighter.lower() in k.lower()}
            if not matches:
                print(f"No data for fighter matching '{filter_fighter}'")
                sys.exit(1)
            fighters_to_write = matches
        else:
            fighters_to_write = fighter_results

        if urls_only:
            seen = set()
            for data in fighters_to_write.values():
                for w in data["walkouts"]:
                    url = w["spotify_url"]
                    if is_playable_url(url) and url not in seen:
                        seen.add(url)
                        print(url)
            return

        for fighter, data in fighters_to_write.items():
            write_by_fighter(data, data["slug"])
            write_viz_fighter(data)

        count = len(fighters_to_write)
        multi_event = sum(1 for d in fighters_to_write.values() if d["appearances"] > 1)
        print(f"\nagg/by-fighter/ -> {count} fighters ({multi_event} with multiple events)")
        if not filter_fighter:
            print(f"  load: {(t_load - t0)*1000:.1f}ms | aggregate: {(t_fighter - t_load)*1000:.1f}ms | total: {(time.perf_counter() - t0)*1000:.1f}ms")

    # By song (always runs in full mode, skip when filtering)
    if not filter_year and not filter_fighter:
        song_results = aggregate_by_song(events)
        path = write_by_song(song_results)
        multi = sum(1 for s in song_results if s["count"] > 1)
        print(f"\n{path} -> {len(song_results)} unique songs ({multi} used by 2+ fighters)")

        # Viz markdown tables
        write_viz_top_songs(song_results)
        write_viz_by_year(year_results)

        # Per-year viz pages
        current_year = datetime.date.today().year
        events_by_year: dict[str, list] = defaultdict(list)
        for event in events:
            y = event.get("date", "")[:4]
            if y:
                events_by_year[y].append(event)
        year_pages = 0
        for y in range(2016, current_year + 1):
            write_viz_year_page(y, year_results.get(str(y)), events_by_year.get(str(y), []))
            year_pages += 1

        print(f"viz/agg/ -> top-songs.md, by-year.md, by-year/{year_pages} year pages")


if __name__ == "__main__":
    main()
