# Walkout Song Bangers

Automated pipeline that finds combat sports walkout songs per event and gives you clickable Spotify links.

Run it after any event → get a JSON data file + browsable markdown table → click and listen.

Currently focused on UFC events, but the pattern works for any combat sports promotion (Bellator, ONE, boxing, etc.).

## How it works

This is a [Claude Code Agent Skill](https://docs.anthropic.com/en/docs/claude-code). No Python dependencies for the pipeline — Claude does the scraping, parsing, Spotify matching, and file writing.

```
/walkout-songs "UFC 229"
```

The skill:
1. Searches multiple post-event sources for walkout song data
2. Cross-references sources and assigns confidence tiers
3. Gets the full fight card from UFCStats for coverage
4. Matches every song on Spotify for direct track links
5. Writes JSON (source of truth) + markdown (browsable table)

## Output

Each event produces two files in `events/`:

**JSON** (source of truth):
```json
{
  "event": "UFC 229: Khabib vs McGregor",
  "event_slug": "ufc-229",
  "songs": [
    {
      "fighter": "Khabib Nurmagomedov",
      "song_title": "Dagestan (Remix)",
      "artist": "SABINA, Timaro",
      "confidence": "gold",
      "spotify_url": "https://open.spotify.com/track/1x9wF3XMUGzqYfmmicjY8f",
      "verified_by": {"user": "your_github_username", "method": "human", "reason": "Human verified from broadcast video"}
    }
  ]
}
```

**Markdown** (generated from JSON, clickable Spotify links):

| # | Fighter | Song | Artist | Confidence | Listen |
|---|---------|------|--------|------------|--------|
| 1 | Khabib Nurmagomedov | Dagestan (Remix) | SABINA, Timaro | gold | [Spotify](https://open.spotify.com/track/1x9wF3XMUGzqYfmmicjY8f) |

Regenerate markdown from JSON:
```bash
python3 scripts/generate_md.py                          # all events
python3 scripts/generate_md.py events/ufc-229.json      # single event
```

## Confidence tiers

How much should you trust that this song is what actually played at the event?

| Tier | What it means | How it's obtained |
|------|--------------|-------------------|
| **gold** | Human verified from broadcast video, optionally confirmed by Shazam | See [Gold verification](#gold-verification) below |
| **silver** | 2+ independent post-event sources agree on the same song | Automatic cross-referencing |
| **bronze** | 1 post-event source reports it, no corroboration | Single source |
| **missing** | No walkout song data found for this fighter at this event | — |

Pre-event or historical associations ("fighter has used X in the past") are **not** included. If no post-event source confirms it for this specific event, the fighter is marked as `missing`.

## Gold verification

To promote a song to gold confidence, find a video of the event on YouTube, right-click at the moment the fighter's walkout music starts, and select "Copy video URL at current time". Then tell the skill to verify it:

```
"verify gold: Rose Namajunas https://youtu.be/L7U5WMkQjR8?t=4510"
```

The pipeline extracts a 30-second audio clip and runs Shazam recognition. If Shazam confirms the song, it's promoted to gold. If the broadcast audio is too noisy (commentary/crowd), the human can still confirm by ear.

## Sources (priority order)

1. **Sherdog "The Walkmen"** — complete per-event, every fighter, ~2019+
2. **LowKickMMA** — post-event coverage
3. **MMA Junkie "Fight Tracks"** — excellent, complete per-event
4. **MixedMartialArts.com** — good for older events

## Events processed

| Event | Fighters | Gold | Silver | Bronze | Missing |
|-------|----------|------|--------|--------|---------|
| UFC 229: Khabib vs McGregor | 24 | 1 | 13 | 10 | 0 |
| UFC 217: Bisping vs St-Pierre | 22 | 3 | 0 | 19 | 0 |
| UFC Fight Night 140: Magny vs Ponzinibbio | 24 | 0 | 0 | 24 | 0 |

## Setup

1. Install [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
2. Register a Spotify app at [developer.spotify.com](https://developer.spotify.com/dashboard)
3. Create `.env` in the repo root:
   ```
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   ```
4. For gold verification (optional): `uv tool install yt-dlp` and `sudo apt-get install ffmpeg`

## Evals

Ground truth files in `evals/ground-truth/` contain human-verified fighter → song mappings. Run evals with:

```bash
python3 scripts/eval.py               # all events
python3 scripts/eval.py ufc-229       # single event
```

Evals measure the skill's quality: does it list all fighters on the card (coverage), and does it get verified songs right (accuracy). See `evals/README.md` for details.
