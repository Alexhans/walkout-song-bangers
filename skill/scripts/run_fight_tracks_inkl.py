#!/usr/bin/env python3
"""Generate `data/{slug}.json` using an inkl (MMA Junkie Fight Tracks reprint) page.

Usage:
  python3 skill/scripts/run_fight_tracks_inkl.py 290 \
    'https://www.inkl.com/news/...'
  python3 skill/scripts/run_fight_tracks_inkl.py \
    'UFC Fight Night: Ankalaev vs. Walker 2' \
    'https://sports.yahoo.com/...'
  python3 skill/scripts/run_fight_tracks_inkl.py 'UFC 307'
"""

from __future__ import annotations

import base64
import difflib
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from discover_fight_tracks import discover as discover_fight_tracks
from run_logging import RunLogger


REPO_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = REPO_ROOT / "data"
VIZ_DIR = REPO_ROOT / "viz"


def _http_get(url: str, headers: dict[str, str] | None = None, timeout_s: int = 30) -> str:
    hdrs = dict(headers or {})
    hdrs.setdefault("User-Agent", "Mozilla/5.0")
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _http_post_form(
    url: str, form: dict[str, str], headers: dict[str, str] | None = None, timeout_s: int = 30
) -> str:
    hdrs = dict(headers or {})
    hdrs.setdefault("User-Agent", "Mozilla/5.0")
    data = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _strip_html_to_lines(raw_html: str) -> list[str]:
    s = raw_html
    s = re.sub(r"<script.*?</script>", "", s, flags=re.I | re.S)
    s = re.sub(r"<style.*?</style>", "", s, flags=re.I | re.S)
    s = re.sub(r"</(p|div|li|h1|h2|h3|h4|tr|td|span)>", "\n", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    lines = [_collapse_ws(x) for x in s.splitlines()]
    return [x for x in lines if x]


def _norm_name(name: str) -> str:
    name = html.unescape(name)
    name = name.lower()
    name = re.sub(r"['’`]", "", name)
    name = re.sub(r"[^a-z0-9]+", " ", name)
    return _collapse_ws(name)


def _parse_event_number(arg: str) -> int:
    s = arg.strip().lower().replace("ufc", "").replace("-", " ")
    m = re.search(r"\b(\d{1,4})\b", s)
    if not m:
        raise ValueError(f"Could not parse UFC event number from: {arg!r}")
    return int(m.group(1))


def _looks_like_numbered_event_arg(arg: str) -> bool:
    s = arg.strip()
    return bool(re.fullmatch(r"(?i)(?:ufc[\s-]*)?\d{1,4}", s))


def _slugify_event_name(name: str) -> str:
    slug = html.unescape(name).lower()
    slug = re.sub(r"['’`]", "", slug)
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _parse_ufcstats_event_details(event_url: str) -> tuple[str, str, list[str]]:
    page = _http_get(event_url)

    date_m = re.search(r"Date:\s*</i>\s*([^<]+)</li>", page, flags=re.I)
    loc_m = re.search(r"Location:\s*</i>\s*([^<]+)</li>", page, flags=re.I)

    if not date_m or not loc_m:
        lines = _strip_html_to_lines(page)
        joined = "\n".join(lines)
        date_m = date_m or re.search(r"\bDate:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})\b", joined)
        loc_m = loc_m or re.search(r"\bLocation:\s*(.+)", joined)

    if not date_m or not loc_m:
        raise RuntimeError("Could not parse date/location from UFCStats event details page")

    date_text = _collapse_ws(date_m.group(1))
    loc_text = _collapse_ws(loc_m.group(1))

    month = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    dm = re.match(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", date_text)
    if not dm:
        raise RuntimeError(f"Unrecognized UFCStats date format: {date_text!r}")
    mon = month.get(dm.group(1).lower()[:3])
    if not mon:
        raise RuntimeError(f"Unrecognized UFCStats month: {dm.group(1)!r}")
    iso = date(int(dm.group(3)), mon, int(dm.group(2))).isoformat()

    fighters_raw = re.findall(
        r'<a[^>]+href="http://www\.ufcstats\.com/fighter-details/[^"]+"[^>]*>\s*([^<]+)\s*</a>',
        page,
    )

    fighters: list[str] = []
    seen: set[str] = set()
    for f in fighters_raw:
        f = _collapse_ws(html.unescape(f))
        if not f:
            continue
        k = _norm_name(f)
        if k in seen:
            continue
        fighters.append(f)
        seen.add(k)

    if len(fighters) < 10:
        raise RuntimeError(f"Unexpectedly small fighter roster from UFCStats ({len(fighters)} fighters)")

    return iso, loc_text, fighters


def _parse_inkl_fight_tracks(inkl_url: str) -> dict[str, tuple[str, str]]:
    raw = _http_get(inkl_url)
    lines = _strip_html_to_lines(raw)

    # Expected line format (curly quotes):
    # Fighter Name: “Song” by Artist
    out: dict[str, tuple[str, str]] = {}

    def parse_song_line(line: str) -> tuple[str, str] | None:
        m = re.match(r'^[“"](.+?)[”"]\s*by\s*(.+)$', line)
        if m:
            return (_collapse_ws(m.group(1)), _collapse_ws(m.group(2)))
        m = re.match(r'^[“"](.+?)[”"](?:\s*\((.+)\))?$', line)
        if m:
            return (_collapse_ws(m.group(1)), _collapse_ws(m.group(2) or ""))
        return None

    for line in lines:
        if ":" not in line or " by " not in line:
            continue
        m = re.match(r'^(.*?):\s*[“"](.+?)[”"]\s*by\s*(.+)$', line)
        if not m:
            continue
        fighter = re.sub(r"\[/?autotag\]", "", m.group(1), flags=re.I)
        fighter = _collapse_ws(fighter)
        song = _collapse_ws(m.group(2))
        artist = _collapse_ws(m.group(3))
        if not fighter or not song:
            continue
        out[_norm_name(fighter)] = (song, artist)

    # Newer Yahoo Sports / MMA Junkie mirrors often use:
    # Fighter Name
    # Fighter Name def. Opponent ... / Fighter Name vs. Opponent ...
    # “Song Title” by Artist
    for idx in range(len(lines) - 2):
        fighter = re.sub(r"\[/?autotag\]", "", lines[idx], flags=re.I)
        fighter = _collapse_ws(fighter)
        result_line = lines[idx + 1]
        song_line = lines[idx + 2]

        if not fighter or len(fighter.split()) > 5:
            continue
        if fighter not in result_line:
            continue
        if " def. " not in result_line and " vs. " not in result_line:
            continue

        parsed_song = parse_song_line(song_line)
        if not parsed_song:
            continue

        song, artist = parsed_song
        if not song:
            continue
        out.setdefault(_norm_name(fighter), (song, artist))

    if not out:
        raise RuntimeError("Parsed 0 walkout entries from inkl page")
    return out


@dataclass(frozen=True)
class SpotifyClient:
    token: str

    @staticmethod
    def _read_env() -> dict[str, str]:
        env_path = REPO_ROOT / ".env"
        if not env_path.exists():
            return {}
        out: dict[str, str] = {}
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip("'").strip('"')
        return out

    @staticmethod
    def from_env() -> "SpotifyClient | None":
        env = dict(os.environ)
        env.update(SpotifyClient._read_env())
        cid = env.get("SPOTIFY_CLIENT_ID")
        secret = env.get("SPOTIFY_CLIENT_SECRET")
        if not cid or not secret:
            return None

        basic = base64.b64encode(f"{cid}:{secret}".encode("utf-8")).decode("ascii")
        raw = _http_post_form(
            "https://accounts.spotify.com/api/token",
            {"grant_type": "client_credentials"},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {basic}",
            },
        )
        data = json.loads(raw)
        token = data.get("access_token", "")
        if not token:
            raise RuntimeError("Spotify token request succeeded but no access_token was returned")
        return SpotifyClient(token=token)

    def search_track_url(self, song_title: str, artist: str) -> tuple[str, str]:
        q = _collapse_ws(f"{song_title} {artist}".strip())
        if not q:
            return ("", "")
        if " / " in song_title or " & " in song_title:
            return (f"https://open.spotify.com/search/{urllib.parse.quote(q)}", "spotify_match: search_fallback")

        url = "https://api.spotify.com/v1/search?" + urllib.parse.urlencode(
            {"q": q, "type": "track", "limit": "3"}
        )
        raw = _http_get(url, headers={"Authorization": f"Bearer {self.token}"})
        data = json.loads(raw)
        items = ((data.get("tracks") or {}).get("items") or [])[:3]
        if not items:
            return (f"https://open.spotify.com/search/{urllib.parse.quote(q)}", "spotify_match: search_fallback")
        tid = items[0].get("id", "")
        if not tid:
            return (f"https://open.spotify.com/search/{urllib.parse.quote(q)}", "spotify_match: search_fallback")
        return (f"https://open.spotify.com/track/{tid}", "")


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__.strip())
        return 2

    event_arg = sys.argv[1].strip()
    logger = RunLogger(script="run_fight_tracks_inkl", subject=event_arg)
    use_cache = True
    inkl_url = ""

    if len(sys.argv) == 3:
        if sys.argv[2] == "--refresh":
            use_cache = False
        else:
            inkl_url = sys.argv[2]
    logger.set_field("use_cache", use_cache)
    logger.set_field("explicit_url", bool(inkl_url))
    discovery: dict[str, object] | None = None

    try:
        if not inkl_url:
            with logger.stage("discover_source"):
                discovery = discover_fight_tracks(event_arg, use_cache=use_cache, logger=logger)
            inkl_url = str(discovery.get("best_url") or "").strip()
            if not inkl_url:
                print(f"{event_arg}: no Fight Tracks source discovered")
                log_path = logger.finalize()
                print(f"Log: {log_path}")
                return 4
            print(f"Discovered source: {inkl_url}")
            logger.set_field("discovered_source", inkl_url)
            logger.set_field("discovery_candidates", len(discovery.get("candidates") or []))
        else:
            logger.set_field("source_url", inkl_url)

        n: int | None = None
        with logger.stage("resolve_roster"):
            if discovery:
                event_name = str(discovery.get("event") or event_arg).strip()
                ufcstats_url = str(discovery.get("event_url") or "").strip()
                if not ufcstats_url:
                    raise RuntimeError(f"{event_arg}: discovery payload missing UFCStats event URL")
            else:
                event_name = event_arg
                if _looks_like_numbered_event_arg(event_arg):
                    n = _parse_event_number(event_arg)
                    event_name = f"UFC {n}"
                ufcstats_url = ""
                index = _http_get("http://www.ufcstats.com/statistics/events/completed?page=all")
                for m in re.finditer(
                    r'<a\s+href="(?P<url>http://www\.ufcstats\.com/event-details/[^"]+)"[^>]*>(?P<name>[^<]+)</a>',
                    index,
                ):
                    name = html.unescape(m.group("name")).strip()
                    if name.startswith(event_name):
                        ufcstats_url, event_name = m.group("url"), name
                        break
                if not ufcstats_url:
                    raise RuntimeError(f"Could not find {event_name} on UFCStats completed events page")
            event_date, location, roster = _parse_ufcstats_event_details(ufcstats_url)
        if discovery:
            slug = str(discovery.get("event_slug") or "").strip() or _slugify_event_name(event_name)
            if re.fullmatch(r"ufc-(\d{1,4})", slug):
                n = int(slug.split("-", 1)[1])
        else:
            slug = f"ufc-{n}" if n is not None else _slugify_event_name(event_name)
        logger.set_field("event", event_name)
        logger.set_field("event_slug", slug)
        logger.set_field("date", event_date)
        logger.set_field("location", location)
        logger.set_field("roster_size", len(roster))
        logger.set_field("source_url", inkl_url)

        with logger.stage("parse_walkouts"):
            walkouts = _parse_inkl_fight_tracks(inkl_url)
        logger.set_field("walkout_entries", len(walkouts))
        with logger.stage("spotify_auth"):
            spotify = SpotifyClient.from_env()
        logger.set_field("spotify_enabled", bool(spotify))

        songs: list[dict] = []
        found = 0
        spotify_found = 0

        with logger.stage("match_and_enrich"):
            for fighter in roster:
                song_title = ""
                artist = ""

                key = _norm_name(fighter)
                if key in walkouts:
                    song_title, artist = walkouts[key]
                else:
                    best_k = None
                    best = 0.0
                    for k in walkouts.keys():
                        score = difflib.SequenceMatcher(None, key, k).ratio()
                        if score > best:
                            best = score
                            best_k = k
                    if best_k and best >= 0.88:
                        song_title, artist = walkouts[best_k]

                confidence = "bronze" if song_title else "missing"
                spotify_url = ""
                notes = ""

                if song_title:
                    found += 1
                    if spotify:
                        spotify_url, note = spotify.search_track_url(song_title, artist)
                        notes = note
                        if spotify_url:
                            spotify_found += 1

                songs.append(
                    {
                        "fighter": fighter,
                        "song_title": song_title,
                        "artist": artist,
                        "confidence": confidence,
                        "spotify_url": spotify_url,
                        "notes": notes,
                    }
                )
        logger.set_field("songs_found", found)
        logger.set_field("spotify_urls_found", spotify_found)

        if found == 0:
            print(f"{event_name}: 0 walkout songs found from sources; not writing {slug}.json")
            log_path = logger.finalize()
            print(f"Log: {log_path}")
            return 3

        out_path = DATA_DIR / f"{slug}.json"
        payload = {
            "event": event_name,
            "event_slug": slug,
            "date": event_date,
            "location": location,
            "source_urls": [inkl_url],
            "generated_at": date.today().isoformat(),
            "songs": songs,
        }

        with logger.stage("write_output"):
            out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {out_path}")
        logger.set_field("output_path", str(out_path))

        VIZ_DIR.mkdir(exist_ok=True)
        with logger.stage("generate_md"):
            os.system(f"python3 {REPO_ROOT / 'skill/scripts/generate_md.py'} {out_path}")
        log_path = logger.finalize()
        print(f"Log: {log_path}")

        return 0
    except Exception as exc:
        logger.append("exception", error_type=type(exc).__name__, error=str(exc))
        log_path = logger.finalize({"type": type(exc).__name__, "message": str(exc)})
        print(f"Log: {log_path}")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
