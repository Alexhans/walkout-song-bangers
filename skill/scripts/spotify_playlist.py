#!/usr/bin/env python3
"""Create or update a Spotify playlist for a given year's UFC walkout songs.

First run will open a browser auth flow and save a refresh token locally.
Subsequent runs are headless.

Usage:
    python3 skill/scripts/spotify_playlist.py 2026
    python3 skill/scripts/spotify_playlist.py 2026 --private
"""

import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "playlist-modify-public playlist-modify-private"
TOKEN_FILE = Path(".spotify-refresh-token")


def load_env():
    env_path = Path(".env")
    if not env_path.exists():
        return {}
    env = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def _token_request(headers, body):
    data = urllib.parse.urlencode(body).encode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", **headers},
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def _basic_auth(client_id, client_secret):
    return base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()


def refresh_access_token(client_id, client_secret, refresh_token):
    resp = _token_request(
        {"Authorization": f"Basic {_basic_auth(client_id, client_secret)}"},
        {"grant_type": "refresh_token", "refresh_token": refresh_token},
    )
    return resp["access_token"]


def exchange_code(client_id, client_secret, code):
    return _token_request(
        {"Authorization": f"Basic {_basic_auth(client_id, client_secret)}"},
        {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI},
    )


def get_access_token(client_id, client_secret):
    if TOKEN_FILE.exists():
        return refresh_access_token(client_id, client_secret, TOKEN_FILE.read_text().strip())

    params = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
    })
    print(f"\nOpen this URL in your browser:\nhttps://accounts.spotify.com/authorize?{params}\n")
    print(f"You'll be redirected to {REDIRECT_URI}?code=... (the page will fail to load — that's fine)")
    redirect = input("Paste the full redirect URL: ").strip()

    code = urllib.parse.parse_qs(urllib.parse.urlparse(redirect).query).get("code", [None])[0]
    if not code:
        raise RuntimeError("No code found in redirect URL")

    tokens = exchange_code(client_id, client_secret, code)
    TOKEN_FILE.write_text(tokens["refresh_token"])
    print(f"Refresh token saved to {TOKEN_FILE}")
    return tokens["access_token"]


def api(method, access_token, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {access_token}",
            **({"Content-Type": "application/json"} if data else {}),
        },
    )
    with urllib.request.urlopen(req) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def get_user_id(access_token):
    return api("GET", access_token, "https://api.spotify.com/v1/me")["id"]


def find_playlist(access_token, user_id, name):
    url = f"https://api.spotify.com/v1/users/{user_id}/playlists?limit=50"
    while url:
        data = api("GET", access_token, url)
        for pl in data["items"]:
            if pl["name"] == name:
                return pl["id"]
        url = data.get("next")
    return None


def create_playlist(access_token, user_id, name, public, description):
    resp = api("POST", access_token, f"https://api.spotify.com/v1/users/{user_id}/playlists", {
        "name": name,
        "public": public,
        "description": description,
    })
    return resp["id"]


def update_playlist_description(access_token, playlist_id, description):
    api("PUT", access_token, f"https://api.spotify.com/v1/playlists/{playlist_id}", {
        "description": description,
    })


def set_playlist_tracks(access_token, playlist_id, uris):
    # PUT replaces everything (first 100), POST appends
    api("PUT", access_token, f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
        {"uris": uris[:100]})
    for i in range(100, len(uris), 100):
        api("POST", access_token, f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
            {"uris": uris[i:i + 100]})


def load_year_tracks(year):
    path = Path("agg") / "by-year" / f"{year}.json"
    if not path.exists():
        raise FileNotFoundError(f"No aggregation data for {year} — run aggregate.py first")
    with open(path) as f:
        data = json.load(f)
    tracks = [t for t in data["tracks"] if t["spotify_url"].startswith("https://open.spotify.com/track/")]
    tracks.sort(key=lambda t: t["date"])
    return tracks


def process_year(year, access_token, user_id, public):
    tracks = load_year_tracks(year)
    print(f"\n{year}: {len(tracks)} playable tracks")

    with open(Path("agg") / "by-year" / f"{year}.json") as f:
        year_data = json.load(f)
    stats = year_data["stats"]
    events = year_data["events"]
    description = (
        f"UFC walkout songs {year} — "
        f"{stats['unique_playable_tracks']} tracks, {events} events | "
        f"github.com/Alexhans/walkout-song-bangers"
    )

    name = f"UFC Walkout Songs {year}"
    playlist_id = find_playlist(access_token, user_id, name)
    if playlist_id:
        print(f"  Updating: {name}")
        update_playlist_description(access_token, playlist_id, description)
    else:
        playlist_id = create_playlist(access_token, user_id, name, public, description)
        print(f"  Created: {name}")

    uris = [f"spotify:track:{t['spotify_url'].split('/track/')[1]}" for t in tracks]
    set_playlist_tracks(access_token, playlist_id, uris)
    print(f"  Done → https://open.spotify.com/playlist/{playlist_id}")
    return playlist_id


def update_readme_spotify(results):
    """Rewrite the <!-- BEGIN SPOTIFY -->...<!-- END SPOTIFY --> block in README.md."""
    import re
    readme = Path("README.md")
    if not readme.exists():
        return
    text = readme.read_text()
    begin, end = "<!-- BEGIN SPOTIFY -->", "<!-- END SPOTIFY -->"
    start = text.find(begin)
    stop = text.find(end)
    if start == -1 or stop == -1:
        return

    # Parse existing entries so a single-year run doesn't wipe other years
    existing = {}
    for m in re.finditer(r"\| (\d{4}) \| \[.*?\]\(https://open\.spotify\.com/playlist/(\w+)\)", text):
        existing[m.group(1)] = m.group(2)
    existing.update(results)

    rows = "\n".join(
        f"| {year} | [UFC Walkout Songs {year}](https://open.spotify.com/playlist/{pid}) |"
        for year, pid in sorted(existing.items(), reverse=True)
    )
    table = f"| Year | Playlist |\n|------|----------|\n{rows}"
    readme.write_text(text[:start] + begin + "\n" + table + "\n" + text[stop:])
    print("\nREADME.md Spotify section updated.")


def main():
    args = sys.argv[1:]
    public = "--private" not in args
    all_years = "--all" in args
    args = [a for a in args if not a.startswith("--")]

    if not args and not all_years:
        print("Usage: python3 skill/scripts/spotify_playlist.py <year> [--private]")
        print("       python3 skill/scripts/spotify_playlist.py --all [--private]")
        sys.exit(1)

    env = {**load_env(), **os.environ}
    client_id = env.get("SPOTIFY_CLIENT_ID")
    client_secret = env.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("Missing SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET in .env")
        sys.exit(1)

    access_token = get_access_token(client_id, client_secret)
    user_id = get_user_id(access_token)

    results = {}
    if all_years:
        years = sorted(p.stem for p in (Path("agg") / "by-year").glob("*.json"))
        print(f"Processing {len(years)} years: {', '.join(years)}")
        for year in years:
            results[year] = process_year(year, access_token, user_id, public)
    else:
        year = args[0]
        results[year] = process_year(year, access_token, user_id, public)

    if results:
        update_readme_spotify(results)


if __name__ == "__main__":
    main()
