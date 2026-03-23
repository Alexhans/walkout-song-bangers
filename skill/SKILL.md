---
name: walkout-songs
description: This skill should be used when the user asks to "get walkout songs", "find walkout songs for UFC", "walkout songs for UFC 229", "process walkout songs", "UFC entrance music", or mentions a UFC event and wants walkout/entrance music information. Discovers UFC walkout songs from web sources and produces a browsable list with clickable Spotify links.
version: 0.1.0
---

# walkout-songs

Discover UFC walkout songs for a given event and produce a JSON data file plus a browsable Markdown table with clickable Spotify track links.

## Input

Accept an event name as the primary argument. Examples:
- `"UFC 229"`
- `"UFC Fight Night: Evloev vs Murphy"`
- `"UFC London March 2026"`
- `"Adesanya vs Pyfer"`

## Workflow

### Operating modes

Use one of these two modes based on user intent:

- **Normal mode**: User wants event data saved to the repo. Write or merge into `data/{slug}.json`, then generate `viz/{slug}.md`.
- **Eval mode**: User wants to test the skill from scratch. Write fresh output to a temp directory such as `/tmp/walkout-eval/{slug}/data/{slug}.json`, do not read or merge committed `data/{slug}.json`, then run the eval commands below.

The user should not need to remember temp paths or `--data-dir`. In eval mode, the skill should handle that automatically.

### Step 1: Normalize the event identifier

Convert the user's input into a slug for filenames (e.g., `"UFC 229"` → `ufc-229`, `"UFC Fight Night: Evloev vs Murphy"` → `ufc-fight-night-evloev-vs-murphy`). Use the user's input as a working name for searches, but the **canonical event name** comes from UFCStats in Step 3.

### Step 2: Search for walkout song data

Search for post-event walkout song articles using these sources in priority order:

1. **Sherdog "The Walkmen"** (best source — complete per-event data, every fighter on card)
   - WebSearch: `site:sherdog.com "The Walkmen" "{event name}" walkout tracks`
   - Coverage: Most UFC events from ~2019 onward
   - Format: Fighter name → Artist → Song title, full card

2. **LowKickMMA** (good post-event coverage)
   - WebSearch: `site:lowkickmma.com "{event name}" walkout songs`

3. **MMA Junkie "Fight Tracks"** (excellent, complete per-event data)
   - WebSearch: `site:mmajunkie.com "fight tracks" "{event name}" walkout songs`
   - WebFetch blocks mmajunkie.com — use `curl` via Bash to fetch the article HTML instead
   - URL pattern: `https://mmajunkie-eu.usatoday.com/story/sports/ufc/{year}/{month}/{day}/fight-tracks-walkout-songs-{event-slug}/...`
   - Parse HTML with python3 to extract text content (fighter names and songs are in plain text)
   - Format: `Fighter Name: "Song Title" by Artist`

4. **MixedMartialArts.com** (good for older events pre-2019)
   - WebSearch: `site:mixedmartialarts.com "walked out" "{event name}"`

If no source-specific results, broaden: `"{event name}" walkout songs full card`

**Important:** Prefer post-event articles (confirmed walkout songs) over pre-event articles (historical guesses). Check whether the article says fighters "walked out to" (confirmed) vs "has used" or "is known for" (historical guess).

### Step 3: Get the full fight card

Get the complete roster of fighters from UFCStats. This is the authoritative source for fighter coverage — every fighter on the card must appear in the output, even if no walkout song was found.

1. **Find the event on UFCStats:** Use `curl` via Bash to fetch `http://www.ufcstats.com/statistics/events/completed` and find the event URL (format: `http://www.ufcstats.com/event-details/{id}`).
2. **Extract the canonical event name:** The event listing page shows the full name (e.g., "UFC 290: Volkanovski vs. Rodriguez"). Use this as the `"event"` field in the output JSON — never use the user's shorthand input (e.g., "UFC 290") as the event name.
3. **Scrape the fight card:** Use `curl` on the event details page and parse with python3 to extract all fighter names. The page lists every bout with both fighter names.
4. **Count bouts and fighters:** Verify the total matches expectations (e.g., 12 bouts = 24 fighters). This count is the ground truth for coverage.

**Caching:** Save fetched HTML pages to `/tmp/walkout-song-bangers-cache/` (e.g., `/tmp/walkout-song-bangers-cache/ufcstats-events.html`, `/tmp/walkout-song-bangers-cache/ufcstats-{event-slug}.html`). Before fetching, check if a cached copy exists and is less than 24 hours old — reuse it instead of re-fetching. This avoids hammering external sites when processing multiple events in a session.

If UFCStats is unavailable, fall back to the Wikipedia event page via `curl` (WebFetch returns 403 on Wikipedia).

### Step 4: Scrape walkout song data

Use WebFetch on the best matching walkout song article. Extract every fighter–song pair:

- **Fighter name** (full name as listed)
- **Song title**
- **Artist(s)**

Sherdog Walkmen format: `Fighter → Artist → Song Title`
LowKickMMA format: varies, look for fighter name + song title + artist in body text
MMA Junkie format: `Fighter Name – "Song Title" by Artist`

Collect ALL fighters on the card (main card + prelims). For fighters not found in the walkout article, include them with `confidence: "missing"` and empty song fields.

### Step 5: Match songs on Spotify

For each fighter–song pair, find the direct Spotify track link:

1. **Read credentials:** Read the file `.env` to get `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`.

2. **Get access token:** Use Bash with `curl` to POST to `https://accounts.spotify.com/api/token`:
   ```bash
   curl -s -X POST "https://accounts.spotify.com/api/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -H "Authorization: Basic {base64(client_id:client_secret)}" \
     -d "grant_type=client_credentials"
   ```
   Base64-encode the credentials with: `echo -n "client_id:client_secret" | base64`
   Extract `access_token` from the JSON response. Do this ONCE per skill invocation.

3. **Search for each song:** Use Bash with `curl` to GET:
   ```bash
   curl -s "https://api.spotify.com/v1/search?q={url_encoded_query}&type=track&limit=3" \
     -H "Authorization: Bearer {access_token}"
   ```
   URL-encode the query with: `python3 -c "import urllib.parse; print(urllib.parse.quote('song artist'))"`
   Note: avoid single quotes in the python command — use triple-quoted strings for names with apostrophes.

4. **Pick the best match:** From the search results, select the top track. Extract:
   - Track ID
   - Construct URL: `https://open.spotify.com/track/{track_id}`

5. **Fallback:** If no results or the match looks wrong (completely different song/artist name), use a search link instead: `https://open.spotify.com/search/{url_encoded_song+artist}` and add a note: `"spotify_match: search_fallback"`.

### Step 6: Assign confidence

Use these rules:
- **gold**: Human verified — confirmed from broadcast video, optionally backed by Shazam audio recognition (see Gold Verification below). Must include a `verified_by` field: `{"user": "github_username", "method": "shazam"|"human", "reason": "..."}`
- **silver**: 2+ independent post-event sources agree on the same song for this fighter at this event (Phase 3)
- **bronze**: 1 post-event source reports this song for this fighter at this event
- **missing**: No post-event source found, or only pre-event/historical associations exist

Pre-event articles ("fighter has used X in the past") do NOT count — mark the fighter as `missing` unless a post-event source confirms the song for this specific event.

### Step 7: Write JSON output

**If the event JSON already exists**, read it first and merge:
- For each fighter, if the existing entry has a **higher confidence** than the new data, keep the existing entry (confidence, song_title, artist, spotify_url, notes). Never downgrade confidence.
- Confidence ranking: **gold > silver > bronze > missing**.
- If the song title changed (different song, not just formatting), use the new data regardless of confidence — flag it in notes so the human can review.
- Add any new fighters not in the existing file (e.g., fighters from UFCStats that were previously missing).
- Update `source_urls` to include any new sources found.

Write to `data/{slug}.json` with this schema:

```json
{
  "event": "UFC 229: Khabib vs McGregor",
  "event_slug": "ufc-229",
  "date": "2018-10-06",
  "location": "T-Mobile Arena, Las Vegas, Nevada",
  "source_urls": [
    "https://www.essentiallysports.com/..."
  ],
  "generated_at": "2026-03-22T14:30:00Z",
  "songs": [
    {
      "fighter": "Khabib Nurmagomedov",
      "song_title": "Dagestan",
      "artist": "Direct Hit & Sabina Saidova",
      "confidence": "silver",
      "spotify_url": "https://open.spotify.com/track/abc123",
      "notes": ""
    }
  ]
}
```

### Step 8: Generate Markdown output

Run the generation script to produce markdown from the JSON source of truth:

```bash
python3 skill/scripts/generate_md.py data/{slug}.json
```

This generates `viz/{slug}.md` with this format:

```markdown
# {Event Name}

**Date:** {date} | **Location:** {location}

| # | Fighter | Song | Artist | Confidence | Listen |
|---|---------|------|--------|------------|--------|
| 1 | Khabib Nurmagomedov | Dagestan | Direct Hit & Sabina Saidova | silver | [Spotify](https://open.spotify.com/track/abc123) |

---
*Sources: [Sherdog]({url}) | [MMA Junkie]({url})*
*Generated: {date}*
```

Use confidence indicators in the table:
- `gold` — human verified
- `silver` — 2+ independent sources agree (Phase 3)
- `bronze` — 1 post-event source
- `missing` — no post-event data found

### Step 9: Report

Summarize:
- Event processed
- Fighter coverage: songs found / total fighters on card
- Songs with direct Spotify links vs search fallbacks
- Confidence breakdown (silver / guess / missing)
- Output file paths
- Source(s) used

## Gold Verification Mode

When the user wants to promote a fighter's song to gold confidence, they provide a YouTube URL with a timestamp pointing to the walkout moment. The pipeline extracts a short audio clip and runs Shazam recognition to confirm the song.

### Requirements

- `yt-dlp` — install via `uv tool install yt-dlp`
- `ffmpeg` — must be available on PATH
- `shazamio` Python library — install in a venv: `uv venv /tmp/shazam-env --python 3.12 && source /tmp/shazam-env/bin/activate && pip install shazamio`

### Workflow

### Operating modes

Use one of these two modes based on user intent:

- **Normal mode**: User wants event data saved to the repo. Write or merge into `data/{slug}.json`, then generate `viz/{slug}.md`.
- **Eval mode**: User wants to test the skill from scratch. Write fresh output to a temp directory such as `/tmp/walkout-eval/{slug}/data/{slug}.json`, do not read or merge committed `data/{slug}.json`, then run the eval commands below.

The user should not need to remember temp paths or `--data-dir`. In eval mode, the skill should handle that automatically.

1. **User provides:** A fighter name and a YouTube URL with timestamp. The user finds a video of the event, right-clicks at the moment the walkout music starts, and selects "Copy video URL at current time" (e.g., `https://youtu.be/L7U5WMkQjR8?t=4510`)
2. **Extract audio clip:** Use `yt-dlp` to download a 30-second MP3 starting at the timestamp:
   ```bash
   yt-dlp -x --audio-format mp3 --download-sections "*{MM:SS}-{MM:SS+30}" \
     -o "/tmp/{fighter}-walkout.%(ext)s" "{youtube_url}"
   ```
3. **Run Shazam recognition:**
   ```python
   import asyncio
   from shazamio import Shazam

   async def recognize():
       shazam = Shazam()
       result = await shazam.recognize("/tmp/{fighter}-walkout.mp3")
       if result.get("track"):
           print(f"Song:   {result['track']['title']}")
           print(f"Artist: {result['track']['subtitle']}")

   asyncio.run(recognize())
   ```
   Run with: `/tmp/shazam-env/bin/python3 script.py`
4. **If Shazam matches:** Update the fighter's entry in the event JSON — set `confidence` to `"gold"` and add a note like `"Shazam verified from broadcast video"`.
5. **If Shazam doesn't match:** The broadcast audio may be too noisy (commentary/crowd). The human can still confirm by ear and promote to gold manually. Note: `"Human verified from broadcast video"`.

### Limitations

- Shazam works best when the walkout music is prominent in the broadcast mix. Commentary-heavy or crowd-heavy sections may fail to match.
- This is an optional upgrade path — gold can always be assigned by human ear alone.

## Handling Edge Cases

- **Mashups/remixes** (e.g., "Foggy Dew / Hypnotize"): List the combined title. Search Spotify for the mashup first. If not found, search for each individual song and list the first one found. Note the others in `notes`.
- **No walkout song data found**: Do not write `data/{slug}.json` or `viz/{slug}.md` if the run recovers zero real songs. Report the event as source-blocked instead. Do not fabricate songs.
- **Fighter walked out to silence or no music**: Include the fighter with `song_title: "No music"` and empty `spotify_url`.
- **Multiple sources disagree** (Phase 3): Will be handled when cross-referencing is added.

## Eval Mode

When the user asks to "eval walkout-songs" or "score walkout-songs against {event}":

1. **Run the pipeline into a temp directory** — produce fresh output in a path like `/tmp/walkout-eval/{slug}/data/{slug}.json`.
   Do not read or merge `data/{slug}.json` in eval mode.
2. **Run the ground-truth eval:**
   ```bash
   python3 skill/scripts/eval.py --data-dir /tmp/walkout-eval/{slug}/data {slug}
   ```
3. **Run the baseline comparison:**
   ```bash
   python3 skill/scripts/compare_runs.py /tmp/walkout-eval/{slug}/data {slug}
   ```
4. Report both answers clearly:
   - **Ground truth**: did the fresh run get the event right?
   - **Baseline match**: did the fresh run match the committed result in `data/`?

`eval.py` compares fresh output against `evals/ground-truth/{slug}.expected.json`:
- Fighter coverage: % of ground-truth fighters found (fuzzy name match, ≥60% similarity)
- Song accuracy: % of matched fighters with correct song (fuzzy, ≥70% similarity)
- Artist accuracy: % of matched fighters with correct artist (fuzzy, ≥60% similarity)
- Spotify link quality: direct track links vs search fallbacks
- Lists all issues: missing fighters, wrong songs, wrong artists

`compare_runs.py` compares fresh output against committed `data/{slug}.json` and reports fighter, song, artist, confidence, and Spotify-link differences.

> **Important:** Never read files under `evals/ground-truth/` during extraction, and never merge committed `data/{slug}.json` into an eval-mode run. Eval mode must measure the fresh output only.

## Backfill Mode

To process multiple past events, the user can provide a list of event names. Process each one sequentially, producing separate JSON and MD files for each event. Report a summary at the end.

Example: `"backfill: UFC 229, UFC Fight Night 140, UFC 324"`
