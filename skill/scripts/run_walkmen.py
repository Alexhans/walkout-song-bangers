#!/usr/bin/env python3
"""Generate `data/{slug}.json` for a numbered UFC event using Sherdog's "The Walkmen"
post-event article + UFCStats fight-card roster, then generate `viz/{slug}.md`.

This is the "normal mode" runner described in `skill/SKILL.md`.

Usage:
  python3 skill/scripts/run_walkmen.py 291
  python3 skill/scripts/run_walkmen.py "UFC 291"
  python3 skill/scripts/run_walkmen.py ufc-291
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
YAHOO_SEARCH_ROOT = "https://search.yahoo.com/search?p="
BING_SEARCH_ROOT = "https://www.bing.com/search?q="


CONF_RANK = {"missing": 0, "bronze": 1, "silver": 2, "gold": 3}


def _http_get(url: str, headers: dict[str, str] | None = None, timeout_s: int = 30) -> str:
    hdrs = dict(headers or {})
    hdrs.setdefault("User-Agent", "Mozilla/5.0")
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _http_post_form(
    url: str, form: dict[str, str], headers: dict[str, str] | None = None, timeout_s: int = 30
) -> str:
    data = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _strip_tags(s: str) -> str:
    s = re.sub(r"<script.*?</script>", "", s, flags=re.I | re.S)
    s = re.sub(r"<style.*?</style>", "", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s)


def _norm_name(name: str) -> str:
    name = html.unescape(name)
    name = name.lower()
    name = re.sub(r"['’`]", "", name)
    name = re.sub(r"[^a-z0-9]+", " ", name)
    name = _collapse_ws(name)
    return name


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


@dataclass(frozen=True)
class SpotifyClient:
    token: str

    @staticmethod
    def from_env() -> "SpotifyClient | None":
        env = dict(os.environ)
        env.update(_read_env())
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
        """Returns (spotify_url, note). May return a search fallback URL."""
        q = _collapse_ws(f"{song_title} {artist}".strip())
        if not q:
            return ("", "")

        # Mashups / multiple tracks: don't guess a single track id.
        if " / " in song_title or " & " in song_title:
            return (
                f"https://open.spotify.com/search/{urllib.parse.quote(q)}",
                "spotify_match: search_fallback",
            )

        url = "https://api.spotify.com/v1/search?" + urllib.parse.urlencode(
            {"q": q, "type": "track", "limit": "3"}
        )
        raw = _http_get(url, headers={"Authorization": f"Bearer {self.token}"})
        data = json.loads(raw)
        items = ((data.get("tracks") or {}).get("items") or [])[:3]
        if not items:
            return (
                f"https://open.spotify.com/search/{urllib.parse.quote(q)}",
                "spotify_match: search_fallback",
            )
        track_id = items[0].get("id", "")
        if not track_id:
            return (
                f"https://open.spotify.com/search/{urllib.parse.quote(q)}",
                "spotify_match: search_fallback",
            )
        return (f"https://open.spotify.com/track/{track_id}", "")


def _parse_event_number(arg: str) -> int:
    s = arg.strip().lower()
    s = s.replace("ufc", "").strip()
    s = s.replace("-", " ")
    m = re.search(r"\b(\d{1,4})\b", s)
    if not m:
        raise ValueError(f"Could not parse UFC event number from: {arg!r}")
    return int(m.group(1))


def _extract_result_urls_yahoo(search_html: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for encoded in re.findall(r"/RU=([^/]+)/RK=", search_html):
        url = urllib.parse.unquote(encoded)
        if url.startswith("http") and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _extract_result_urls_bing(search_html: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(r'href="([^"]+)"', search_html):
        href = html.unescape(raw)
        if not href.startswith("http"):
            continue
        if "sherdog.com" not in href:
            continue
        if href not in seen:
            seen.add(href)
            urls.append(href)
    return urls


def _find_ufcstats_event_url(event_label: str) -> tuple[str, str]:
    """Return (event_url, canonical_event_name) from UFCStats."""
    index = _http_get("http://www.ufcstats.com/statistics/events/completed?page=all")
    for m in re.finditer(
        r'<a\s+href="(?P<url>http://www\.ufcstats\.com/event-details/[^"]+)"[^>]*>(?P<name>[^<]+)</a>',
        index,
    ):
        name = html.unescape(m.group("name")).strip()
        if name.startswith(event_label):
            return m.group("url"), name
    raise RuntimeError(f"Could not find {event_label} on UFCStats completed events page")


def _parse_ufcstats_event_details(event_url: str) -> tuple[str, str, list[str]]:
    page = _http_get(event_url)

    date_m = re.search(r"Date:\s*</i>\s*([^<]+)</li>", page, flags=re.I)
    loc_m = re.search(r"Location:\s*</i>\s*([^<]+)</li>", page, flags=re.I)

    if not date_m or not loc_m:
        stripped = _strip_tags(page)
        date_m = date_m or re.search(r"\bDate:\s*([A-Za-z]{3}\s+\d{1,2},\s+\d{4})\b", stripped)
        loc_m = loc_m or re.search(r"\bLocation:\s*(.+)", stripped)

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
        key = _norm_name(f)
        if key in seen:
            continue
        fighters.append(f)
        seen.add(key)

    if len(fighters) < 10:
        raise RuntimeError(f"Unexpectedly small fighter roster from UFCStats ({len(fighters)} fighters)")

    return (iso, loc_text, fighters)


def _find_walkmen_url(event_number: int) -> str:
    """Find the Sherdog Walkmen walkout-tracks article URL for a numbered UFC event.

    Sherdog's sitemap appears to omit some newer Walkmen pages, so we use:
    1) sitemap-articles.xml (fast, when present)
    2) fallback: scrape Sherdog's paginated articles list pages for a matching URL
    """
    sitemap = _http_get("https://www.sherdog.com/sitemap-articles.xml")
    pat = rf"https://www\.sherdog\.com/news/articles/The-Walkmen-(?:All-)?UFC-{event_number}-[^<]+"
    m = re.search(pat, sitemap)
    if m:
        return m.group(0)

    queries = [
        f'site:sherdog.com "The Walkmen" "UFC {event_number}"',
        f'site:sherdog.com "All UFC {event_number} Walkout Tracks"',
        f'site:sherdog.com "UFC {event_number}" "Walkout Tracks"',
    ]
    for query in queries:
        for provider, root in (("yahoo", YAHOO_SEARCH_ROOT), ("bing", BING_SEARCH_ROOT)):
            try:
                html_txt = _http_get(root + urllib.parse.quote_plus(query))
            except Exception:
                continue
            hrefs = (
                _extract_result_urls_yahoo(html_txt)
                if provider == "yahoo"
                else _extract_result_urls_bing(html_txt)
            )
            for href in hrefs:
                if "sherdog.com/news/articles/The-Walkmen-" not in href:
                    continue
                if f"UFC-{event_number}-" in href:
                    return href

    # Fallback: walk recent article list pages until we find a matching Walkmen URL.
    # This is intentionally bounded to keep runtime predictable.
    for page in range(1, 301):
        if page == 1:
            url = "https://www.sherdog.com/news/articles/list"
        else:
            url = f"https://www.sherdog.com/news/articles/list/{page}"

        html_txt = _http_get(url)

        # Look for Walkmen article hrefs that include the UFC number in the slug.
        hrefs = re.findall(r'href="(?P<href>/news/articles/The-Walkmen-[^"]+)"', html_txt)
        for href in hrefs:
            if f"UFC-{event_number}-" in href:
                return "https://www.sherdog.com" + href

        # Stop early if we've paged back before 2021-ish to avoid huge scans.
        # (Older events are generally present in the sitemap anyway.)
        if "2020" in html_txt or "2019" in html_txt:
            break

    raise RuntimeError(f"Could not find Walkmen article for UFC {event_number}")



def _parse_walkmen_article(url: str, event_number: int) -> dict[str, tuple[str, str]]:
    page = _http_get(url, headers={"User-Agent": "Mozilla/5.0"})

    header_pat = rf"<h2>\s*(?:All\s+)?UFC {event_number}\s+Walkout Tracks:\s*</h2>"
    m = re.search(header_pat, page, flags=re.I)
    if not m:
        raise RuntimeError("Could not find walkout-tracks header in Walkmen article")

    chunk = page[m.end() : m.end() + 200_000]
    lines = re.split(r"<br\s*/?>", chunk, flags=re.I)

    out: dict[str, tuple[str, str]] = {}
    for raw in lines:
        if "/fighter/" not in raw or ":" not in raw:
            continue

        line = _collapse_ws(raw.replace("\n", " "))

        fm = re.search(
            r'<a[^>]+href="/fighter/[^"]+"[^>]*>\s*([^<]+)\s*</a>',
            line,
            flags=re.I,
        )
        if not fm:
            continue

        fighter = _collapse_ws(_strip_tags(fm.group(0)))

        rest = line[fm.end() :]
        colon = rest.find(":")
        if colon == -1:
            continue
        rest = rest[colon + 1 :].strip()

        song_title = ""
        artist = ""

        if "|" in rest:
            # Newer Walkmen format: Fighter: Artist | “Song”
            artist_part, _, songs_part = rest.partition("|")
            artist = _collapse_ws(_strip_tags(artist_part))

            song_titles = re.findall(r"“\s*<a[^>]*>\s*([^<]+)\s*</a>\s*”", songs_part)
            if not song_titles:
                song_titles = re.findall(r"“([^”]+)”", _strip_tags(songs_part))

            song_titles = [_collapse_ws(html.unescape(t)) for t in song_titles if _collapse_ws(t)]
            song_title = " / ".join(song_titles)
        else:
            # Older Walkmen format: Fighter: “Song” by Artist (may include multiple song/artist pairs)
            # Work on a tag-stripped version so we can regex on plain text.
            plain = _collapse_ws(_strip_tags(rest))
            pairs = re.findall(r"“([^”]+)”\s*by\s*([^&]+?)(?=(?:\s*&\s*“|$))", plain)
            if pairs:
                titles = [_collapse_ws(t) for t, _a in pairs]
                artists = [_collapse_ws(a) for _t, a in pairs]
                song_title = " / ".join([t for t in titles if t])
                uniq_artists = []
                for a in artists:
                    if a and a not in uniq_artists:
                        uniq_artists.append(a)
                artist = " / ".join(uniq_artists)
            else:
                # Fallback: at least try to capture quoted titles.
                titles = re.findall(r"“([^”]+)”", plain)
                song_title = " / ".join([_collapse_ws(t) for t in titles if _collapse_ws(t)])

        if not fighter:
            continue

        out[_norm_name(fighter)] = (song_title, artist)

    if not out:
        raise RuntimeError("Parsed 0 walkout entries from Walkmen article")

    return out


def _merge_existing(existing: dict, new_songs: list[dict]) -> list[dict]:
    ex_map: dict[str, dict] = {_norm_name(s["fighter"]): s for s in existing.get("songs", [])}
    out: list[dict] = []

    for s in new_songs:
        key = _norm_name(s["fighter"])
        prev = ex_map.get(key)
        if not prev:
            out.append(s)
            continue

        prev_title = (prev.get("song_title") or "").strip()
        new_title = (s.get("song_title") or "").strip()

        if prev_title and new_title and _norm_name(prev_title) != _norm_name(new_title):
            s = dict(s)
            note = (s.get("notes") or "").strip()
            s["notes"] = (note + " | " if note else "") + "changed_from_existing"
            out.append(s)
            continue

        if CONF_RANK.get(prev.get("confidence", "missing"), 0) >= CONF_RANK.get(
            s.get("confidence", "missing"), 0
        ):
            out.append(prev)
        else:
            out.append(s)

    return out


def run(event_arg: str) -> Path | None:
    n = _parse_event_number(event_arg)
    slug = f"ufc-{n}"
    event_label = f"UFC {n}"

    ufcstats_url, event_name = _find_ufcstats_event_url(event_label)
    event_date, location, roster = _parse_ufcstats_event_details(ufcstats_url)

    walkmen_url = _find_walkmen_url(n)
    walkouts = _parse_walkmen_article(walkmen_url, n)

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

    # Avoid writing empty coverage shells.
    if found == 0:
        print(f"{event_name}: 0 walkout songs found from sources; not writing {slug}.json")
        return None

    out_path = DATA_DIR / f"{slug}.json"
    payload = {
        "event": event_name,
        "event_slug": slug,
        "date": event_date,
        "location": location,
        "source_urls": [walkmen_url],
        "generated_at": date.today().isoformat(),
        "songs": songs,
    }

    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8", errors="replace"))
        payload["songs"] = _merge_existing(existing, payload["songs"])
        payload["source_urls"] = sorted(set(existing.get("source_urls", []) + payload["source_urls"]))

    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")

    VIZ_DIR.mkdir(exist_ok=True)
    os.system(f"python3 {REPO_ROOT / 'skill/scripts/generate_md.py'} {out_path}")

    return out_path


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip())
        return 2
    out = run(sys.argv[1])
    return 0 if out else 3


if __name__ == "__main__":
    raise SystemExit(main())
