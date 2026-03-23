#!/usr/bin/env python3
"""Generate `data/ufc-{n}.json` using a LowKickMMA walkout songs page.

Workflow:
- discover LowKick URL via LowKick search (unless URL is provided)
- scrape UFCStats for full fighter roster + canonical event name/date/location
- parse LowKick for `Fighter: “Song” by Artist` lines
- match to roster; fill missing for the rest
- Spotify lookup for found songs
- write JSON only if at least 1 song was found; then generate `viz/*.md`

Usage:
  python3 skill/scripts/run_lowkick.py 323
  python3 skill/scripts/run_lowkick.py 323 https://www.lowkickmma.com/ufc-323-walkout-songs/
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
    s = re.sub(r"</(p|li|h1|h2|h3|h4|tr|td|div|span)>", "\n", s, flags=re.I)
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


def _find_ufcstats_event(event_label: str) -> tuple[str, str]:
    """Return (event_details_url, canonical_event_name) from UFCStats completed events list."""
    index = _http_get("http://www.ufcstats.com/statistics/events/completed?page=all")
    for m in re.finditer(
        r'<a\s+href="(?P<url>http://www\.ufcstats\.com/event-details/[^"]+)"[^>]*>(?P<name>[^<]+)</a>',
        index,
    ):
        name = html.unescape(m.group("name")).strip()
        if name.startswith(event_label):
            return (m.group("url"), name)
    raise RuntimeError(f"Could not find {event_label} on UFCStats completed events page")


def _parse_ufcstats_event_details(event_url: str) -> tuple[str, str, list[str]]:
    page = _http_get(event_url)

    date_m = re.search(r"Date:\s*</i>\s*([^<]+)</li>", page, flags=re.I)
    loc_m = re.search(r"Location:\s*</i>\s*([^<]+)</li>", page, flags=re.I)

    if not date_m or not loc_m:
        joined = "\n".join(_strip_html_to_lines(page))
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

    return (iso, loc_text, fighters)


def _discover_lowkick_url(event_number: int) -> str:
    q = urllib.parse.quote_plus(f"ufc {event_number} walkout songs")
    search_url = f"https://www.lowkickmma.com/?s={q}"
    html_txt = _http_get(search_url)

    candidates = re.findall(r'href="(https://www\.lowkickmma\.com/[^"]+)"', html_txt)

    # De-dupe while preserving order.
    seen = set()
    uniq = []
    for u in candidates:
        u2 = html.unescape(u)
        if u2 in seen:
            continue
        seen.add(u2)
        uniq.append(u2)

    # Filter to plausible article URLs.
    plausible = []
    for u2 in uniq:
        lu = u2.lower()
        if not lu.startswith('https://www.lowkickmma.com/'):
            continue
        if any(x in lu for x in ('/tag/', '/category/', '/author/', '/search/')):
            continue
        if not any(k in lu for k in ('walkout', 'entrance', 'music')):
            continue
        if 'ufc' not in lu:
            continue
        plausible.append(u2)

    # Verify candidates by fetching them and checking they mention the right UFC number.
    # Keep it bounded so a miss doesn't explode runtime.
    want = f"ufc {event_number}"
    for u2 in plausible[:15]:
        try:
            page = _http_get(u2)
        except Exception:
            continue

        head = page[:50000].lower()
        if want in head:
            return u2

    raise RuntimeError(f"LowKick search found no verifiable walkout-songs URL for UFC {event_number}")



def _parse_lowkick_walkouts(url: str) -> dict[str, tuple[str, str]]:
    raw = _http_get(url)
    lines = _strip_html_to_lines(raw)

    out: dict[str, tuple[str, str]] = {}

    # Most LowKick lists use curly quotes.
    for line in lines:
        if ":" not in line or " by " not in line or "“" not in line or "”" not in line:
            continue
        m = re.match(r"^(.*?):\s*“(.*?)”\s*by\s*(.+)$", line)
        if not m:
            continue
        fighter = _collapse_ws(m.group(1))
        song = _collapse_ws(m.group(2))
        artist = _collapse_ws(m.group(3))
        # Avoid false positives where it's obviously not a fighter entry.
        if len(fighter.split()) > 4:
            continue
        if not fighter or not song:
            continue
        out[_norm_name(fighter)] = (song, artist)

    if not out:
        raise RuntimeError("Parsed 0 walkout entries from LowKick page")

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

    n = _parse_event_number(sys.argv[1])
    lowkick_url = sys.argv[2] if len(sys.argv) == 3 else _discover_lowkick_url(n)

    slug = f"ufc-{n}"
    event_label = f"UFC {n}"

    ufcstats_url, event_name = _find_ufcstats_event(event_label)
    event_date, location, roster = _parse_ufcstats_event_details(ufcstats_url)

    walkouts = _parse_lowkick_walkouts(lowkick_url)
    spotify = SpotifyClient.from_env()

    songs: list[dict] = []
    found = 0

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

    if found == 0:
        print(f"{event_name}: 0 walkout songs found from sources; not writing {slug}.json")
        return 3

    out_path = DATA_DIR / f"{slug}.json"
    payload = {
        "event": event_name,
        "event_slug": slug,
        "date": event_date,
        "location": location,
        "source_urls": [lowkick_url],
        "generated_at": date.today().isoformat(),
        "songs": songs,
    }

    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")

    VIZ_DIR.mkdir(exist_ok=True)
    os.system(f"python3 {REPO_ROOT / 'skill/scripts/generate_md.py'} {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
