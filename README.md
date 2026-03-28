# Walkout Song Bangers

Automated pipeline that finds combat sports walkout songs per event and gives you clickable Spotify links.

Run it after any event → get a JSON data file + browsable markdown table → click and listen.

Currently focused on UFC events, but the pattern works for any combat sports promotion (Bellator, ONE, boxing, etc.).

## Browse the data

**By event** — walkout songs for each processed event:
- [`viz/`](viz/) — markdown tables with Spotify links per event
- [`data/`](data/) — raw JSON source files

**Aggregations** — cross-event views:
- [Top walkout songs](viz/agg/top-songs.md) — songs used by the most fighters, with Spotify links
- [Coverage by year](viz/agg/by-year.md) — walkout song coverage per year
- [`viz/agg/by-fighter/`](viz/agg/by-fighter/) — one page per fighter showing their walkout history (e.g., [Max Holloway](viz/agg/by-fighter/max-holloway.md))

<!-- BEGIN EVENTS -->
| Event | Fighters | Gold | Silver | Bronze | Missing |
|-------|----------|------|--------|--------|---------|
| [UFC 200: Tate vs. Nunes](viz/ufc-200.md) | 24 | 0 | 0 | 23 | 1 |
| [UFC 202: Diaz vs. McGregor 2](viz/ufc-202.md) | 24 | 0 | 0 | 21 | 3 |
| [UFC 203: Miocic vs. Overeem](viz/ufc-203.md) | 20 | 0 | 0 | 19 | 1 |
| [UFC 204: Bisping vs. Henderson 2](viz/ufc-204.md) | 22 | 0 | 0 | 21 | 1 |
| [UFC 205: Alvarez vs. McGregor](viz/ufc-205.md) | 22 | 0 | 0 | 19 | 3 |
| [UFC 206: Holloway vs. Pettis](viz/ufc-206.md) | 24 | 0 | 0 | 23 | 1 |
| [UFC 207: Nunes vs. Rousey](viz/ufc-207.md) | 20 | 0 | 0 | 20 | 0 |
| [UFC 209: Woodley vs. Thompson 2](viz/ufc-209.md) | 22 | 0 | 0 | 22 | 0 |
| [UFC 211: Miocic vs. Dos Santos 2](viz/ufc-211.md) | 24 | 0 | 0 | 23 | 1 |
| [UFC 212: Aldo vs. Holloway](viz/ufc-212.md) | 24 | 0 | 0 | 22 | 2 |
| [UFC 213: Romero vs. Whittaker](viz/ufc-213.md) | 22 | 0 | 0 | 22 | 0 |
| [UFC 214: Cormier vs. Jones 2](viz/ufc-214.md) | 24 | 0 | 0 | 24 | 0 |
| [UFC 216: Ferguson vs. Lee](viz/ufc-216.md) | 22 | 0 | 0 | 22 | 0 |
| [UFC 217: Bisping vs. St-Pierre](viz/ufc-217.md) | 22 | 1 | 0 | 21 | 0 |
| [UFC 218: Holloway vs. Aldo 2](viz/ufc-218.md) | 26 | 0 | 0 | 26 | 0 |
| [UFC 219: Cyborg vs. Holm](viz/ufc-219.md) | 20 | 0 | 0 | 20 | 0 |
| [UFC 226: Miocic vs. Cormier](viz/ufc-226.md) | 22 | 0 | 0 | 6 | 16 |
| [UFC 229: Khabib vs McGregor](viz/ufc-229.md) | 24 | 1 | 13 | 10 | 0 |
| [UFC 230: Cormier vs. Lewis](viz/ufc-230.md) | 24 | 0 | 0 | 19 | 5 |
| [UFC Fight Night 140: Magny vs. Ponzinibbio](viz/ufc-fight-night-140.md) | 24 | 0 | 0 | 24 | 0 |
| [UFC 236: Holloway vs. Poirier 2](viz/ufc-236.md) | 26 | 0 | 0 | 11 | 15 |
| [UFC 237: Namajunas vs. Andrade](viz/ufc-237.md) | 24 | 0 | 0 | 11 | 13 |
| [UFC 238: Cejudo vs. Moraes](viz/ufc-238.md) | 26 | 0 | 0 | 13 | 13 |
| [UFC 239: Jones vs. Santos](viz/ufc-239.md) | 24 | 0 | 0 | 24 | 0 |
| [UFC 241: Cormier vs. Miocic 2](viz/ufc-241.md) | 24 | 0 | 0 | 17 | 7 |
| [UFC 242: Khabib vs. Poirier](viz/ufc-242.md) | 26 | 0 | 0 | 12 | 14 |
| [UFC 243: Whittaker vs. Adesanya](viz/ufc-243.md) | 22 | 0 | 0 | 14 | 8 |
| [UFC 244: Masvidal vs. Diaz](viz/ufc-244.md) | 24 | 0 | 0 | 9 | 15 |
| [UFC 245: Usman vs. Covington](viz/ufc-245.md) | 26 | 0 | 0 | 18 | 8 |
| [UFC 246: McGregor vs. Cowboy](viz/ufc-246.md) | 22 | 0 | 0 | 14 | 8 |
| [UFC 247: Jones vs. Reyes](viz/ufc-247.md) | 24 | 0 | 0 | 14 | 10 |
| [UFC 248: Adesanya vs. Romero](viz/ufc-248.md) | 22 | 0 | 0 | 10 | 12 |
| [UFC 249: Ferguson vs. Gaethje](viz/ufc-249.md) | 22 | 0 | 0 | 9 | 13 |
| [UFC 250: Nunes vs. Spencer](viz/ufc-250.md) | 24 | 0 | 0 | 16 | 8 |
| [UFC 252: Miocic vs. Cormier 3](viz/ufc-252.md) | 22 | 0 | 0 | 11 | 11 |
| [UFC 254: Khabib vs. Gaethje](viz/ufc-254.md) | 24 | 0 | 0 | 6 | 18 |
| [UFC 257: Poirier vs. McGregor 2](viz/ufc-257.md) | 22 | 0 | 0 | 6 | 16 |
| [UFC 264: Poirier vs. McGregor 3](viz/ufc-264.md) | 24 | 0 | 0 | 11 | 13 |
| [UFC 265: Lewis vs. Gane](viz/ufc-265.md) | 26 | 0 | 0 | 11 | 15 |
| [UFC 266: Volkanovski vs. Ortega](viz/ufc-266.md) | 26 | 0 | 0 | 13 | 13 |
| [UFC 268: Usman vs. Covington 2](viz/ufc-268.md) | 28 | 0 | 0 | 12 | 16 |
| [UFC 269: Oliveira vs. Poirier](viz/ufc-269.md) | 28 | 0 | 0 | 26 | 2 |
| [UFC 270: Ngannou vs. Gane](viz/ufc-270.md) | 22 | 0 | 0 | 10 | 12 |
| [UFC 271: Adesanya vs. Whittaker 2](viz/ufc-271.md) | 28 | 0 | 0 | 10 | 18 |
| [UFC 273: Volkanovski vs. The Korean Zombie](viz/ufc-273.md) | 24 | 0 | 0 | 12 | 12 |
| [UFC 274: Oliveira vs. Gaethje](viz/ufc-274.md) | 28 | 0 | 0 | 13 | 15 |
| [UFC 275: Teixeira vs. Prochazka](viz/ufc-275.md) | 22 | 0 | 0 | 7 | 15 |
| [UFC 276: Adesanya vs. Cannonier](viz/ufc-276.md) | 24 | 0 | 0 | 13 | 11 |
| [UFC 277: Pena vs. Nunes 2](viz/ufc-277.md) | 26 | 0 | 0 | 11 | 15 |
| [UFC 280: Oliveira vs. Makhachev](viz/ufc-280.md) | 24 | 0 | 0 | 9 | 15 |
| [UFC 281: Adesanya vs. Pereira](viz/ufc-281.md) | 28 | 0 | 0 | 26 | 2 |
| [UFC 282: Blachowicz vs. Ankalaev](viz/ufc-282.md) | 24 | 0 | 0 | 12 | 12 |
| [UFC 283: Teixeira vs. Hill](viz/ufc-283.md) | 30 | 0 | 0 | 8 | 22 |
| [UFC 284: Makhachev vs. Volkanovski](viz/ufc-284.md) | 26 | 0 | 0 | 14 | 12 |
| [UFC Fight Night: Muniz vs. Allen](viz/ufc-fight-night-muniz-vs-allen.md) | 20 | 0 | 0 | 19 | 1 |
| [UFC 285: Jones vs. Gane](viz/ufc-285.md) | 28 | 0 | 0 | 27 | 1 |
| [UFC Fight Night: Yan vs. Dvalishvili](viz/ufc-fight-night-yan-vs-dvalishvili.md) | 26 | 0 | 0 | 23 | 3 |
| [UFC 287: Pereira vs. Adesanya 2](viz/ufc-287.md) | 24 | 0 | 0 | 10 | 14 |
| [UFC 288: Sterling vs. Cejudo](viz/ufc-288.md) | 24 | 0 | 0 | 23 | 1 |
| [UFC 289: Nunes vs. Aldana](viz/ufc-289.md) | 22 | 0 | 0 | 13 | 9 |
| [UFC 290: Volkanovski vs. Rodriguez](viz/ufc-290.md) | 26 | 0 | 0 | 26 | 0 |
| [UFC 291: Poirier vs. Gaethje 2](viz/ufc-291.md) | 22 | 0 | 0 | 9 | 13 |
| [UFC 292: Sterling vs. O'Malley](viz/ufc-292.md) | 24 | 0 | 0 | 22 | 2 |
| [UFC 293: Adesanya vs. Strickland](viz/ufc-293.md) | 24 | 0 | 0 | 22 | 2 |
| [UFC Fight Night: Fiziev vs. Gamrot](viz/ufc-fight-night-fiziev-vs-gamrot.md) | 22 | 0 | 0 | 14 | 8 |
| [UFC 294: Makhachev vs. Volkanovski 2](viz/ufc-294.md) | 26 | 0 | 0 | 25 | 1 |
| [UFC Fight Night: Almeida vs. Lewis](viz/ufc-fight-night-almeida-vs-lewis.md) | 20 | 0 | 0 | 19 | 1 |
| [UFC 295: Prochazka vs. Pereira](viz/ufc-295.md) | 26 | 0 | 0 | 25 | 1 |
| [UFC Fight Night: Allen vs. Craig](viz/ufc-fight-night-allen-vs-craig.md) | 28 | 0 | 0 | 26 | 2 |
| [UFC 296: Edwards vs. Covington](viz/ufc-296.md) | 24 | 0 | 0 | 23 | 1 |
| [UFC Fight Night: Ankalaev vs. Walker 2](viz/ufc-fight-night-ankalaev-vs-walker-2.md) | 22 | 0 | 0 | 18 | 4 |
| [UFC 297: Strickland vs. Du Plessis](viz/ufc-297.md) | 24 | 0 | 0 | 24 | 0 |
| [UFC Fight Night: Dolidze vs. Imavov](viz/ufc-fight-night-dolidze-vs-imavov.md) | 26 | 0 | 0 | 19 | 7 |
| [UFC Fight Night: Hermansson vs. Pyfer](viz/ufc-fight-night-hermansson-vs-pyfer.md) | 28 | 0 | 0 | 21 | 7 |
| [UFC 298: Volkanovski vs. Topuria](viz/ufc-298.md) | 24 | 0 | 0 | 24 | 0 |
| [UFC Fight Night: Moreno vs. Royval 2](viz/ufc-fight-night-moreno-vs-royval-2.md) | 24 | 0 | 0 | 19 | 5 |
| [UFC Fight Night: Rozenstruik vs. Gaziev](viz/ufc-fight-night-rozenstruik-vs-gaziev.md) | 22 | 0 | 0 | 19 | 3 |
| [UFC 299: O'Malley vs. Vera 2](viz/ufc-299.md) | 28 | 0 | 0 | 24 | 4 |
| [UFC Fight Night: Blanchfield vs. Fiorot](viz/ufc-fight-night-blanchfield-vs-fiorot.md) | 26 | 0 | 0 | 25 | 1 |
| [UFC Fight Night: Allen vs. Curtis 2](viz/ufc-fight-night-allen-vs-curtis-2.md) | 24 | 0 | 0 | 19 | 5 |
| [UFC 300: Pereira vs. Hill](viz/ufc-300.md) | 26 | 0 | 0 | 25 | 1 |
| [UFC Fight Night: Nicolau vs. Perez](viz/ufc-fight-night-nicolau-vs-perez.md) | 26 | 0 | 0 | 23 | 3 |
| [UFC 301: Pantoja vs. Erceg](viz/ufc-301.md) | 26 | 0 | 0 | 18 | 8 |
| [UFC 302: Makhachev vs. Poirier](viz/ufc-302.md) | 24 | 0 | 0 | 21 | 3 |
| [UFC Fight Night: Perez vs. Taira](viz/ufc-fight-night-perez-vs-taira.md) | 22 | 0 | 0 | 22 | 0 |
| [UFC 303: Pereira vs. Prochazka 2](viz/ufc-303.md) | 26 | 0 | 0 | 11 | 15 |
| [UFC 304: Edwards vs. Muhammad 2](viz/ufc-304.md) | 28 | 0 | 0 | 28 | 0 |
| [UFC Fight Night: Sandhagen vs. Nurmagomedov](viz/ufc-fight-night-sandhagen-vs-nurmagomedov.md) | 26 | 0 | 0 | 24 | 2 |
| [UFC 305: Du Plessis vs. Adesanya](viz/ufc-305.md) | 24 | 0 | 0 | 24 | 0 |
| [UFC Fight Night: Burns vs. Brady](viz/ufc-fight-night-burns-vs-brady.md) | 24 | 0 | 0 | 19 | 5 |
| [UFC 307: Pereira vs. Rountree Jr.](viz/ufc-307.md) | 24 | 0 | 0 | 22 | 2 |
| [UFC Fight Night: Moreno vs. Albazi](viz/ufc-fight-night-moreno-vs-albazi.md) | 26 | 0 | 0 | 21 | 5 |
| [UFC 309: Jones vs. Miocic](viz/ufc-309.md) | 24 | 0 | 0 | 6 | 18 |
| [UFC 318: Holloway vs. Poirier 3](viz/ufc-318.md) | 28 | 0 | 0 | 17 | 11 |
| [UFC 322: Della Maddalena vs. Makhachev](viz/ufc-322.md) | 28 | 0 | 0 | 28 | 0 |
| [UFC 324: Gaethje vs. Pimblett](viz/ufc-324.md) | 22 | 0 | 0 | 20 | 2 |
| [UFC 325: Volkanovski vs. Lopes 2](viz/ufc-325.md) | 26 | 0 | 0 | 23 | 3 |
| [UFC Fight Night: Bautista vs. Oliveira](viz/ufc-fight-night-bautista-vs-oliveira.md) | 26 | 0 | 0 | 25 | 1 |
| [UFC Fight Night: Strickland vs. Hernandez](viz/ufc-fight-night-strickland-vs-hernandez.md) | 28 | 0 | 0 | 12 | 16 |
| [UFC Fight Night: Moreno vs. Kavanagh](viz/ufc-fight-night-moreno-vs-kavanagh.md) | 26 | 0 | 0 | 26 | 0 |
| [UFC 326: Holloway vs. Oliveira 2](viz/ufc-326.md) | 24 | 0 | 0 | 10 | 14 |
| [UFC Fight Night: Emmett vs. Vallejos](viz/ufc-fight-night-emmett-vs-vallejos.md) | 28 | 0 | 0 | 10 | 18 |
| [UFC Fight Night: Evloev vs. Murphy](viz/ufc-fight-night-evloev-vs-murphy.md) | 26 | 0 | 0 | 9 | 17 |
<!-- END EVENTS -->

## How it works

This runs as an Agent Skill — an AI-powered pipeline that searches, scrapes, cross-references, and matches songs on Spotify. No Python dependencies for the pipeline itself.

The skill:
1. Searches multiple post-event sources for walkout song data
2. Cross-references sources and assigns confidence tiers
3. Gets the full fight card from UFCStats for coverage
4. Matches every song on Spotify for direct track links
5. Writes JSON to `data/` and markdown to `viz/`

## Confidence tiers

How much should you trust that this song is what actually played at the event?

| Tier | What it means | How it's obtained |
|------|--------------|-------------------|
| **gold** | Human verified from broadcast video, optionally confirmed by Shazam | See [Gold verification](#gold-verification) below |
| **silver** | 2+ independent post-event sources agree on the same song | Automatic cross-referencing |
| **bronze** | 1 post-event source reports it, no corroboration | Single source |
| **missing** | No walkout song data found for this fighter at this event | — |

Pre-event or historical associations ("fighter has used X in the past") are **not** included. If no post-event source confirms it for this specific event, the fighter is marked as `missing`.

**Note on song matching:** Song names and artists are not normalized across events — the same song may appear with different titles, artist spellings, or Spotify links (e.g., multi-song walkouts get matched to different tracks depending on the search query). Aggregations reflect this as-is. Normalization is a future improvement.

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

## Build a Spotify playlist

Aggregated data lives in `agg/` (generated from `data/`). To build a playlist for any year:

```bash
python3 skill/scripts/aggregate.py                          # regenerate all aggregations
python3 skill/scripts/aggregate.py --year 2026 --urls-only  # get Spotify track URLs
```

Then in Spotify desktop: **Create new playlist** → **Ctrl+V / Cmd+V** to paste the URLs. Spotify resolves them into tracks.

```bash
# Copy all 2026 tracks to clipboard (macOS)
python3 skill/scripts/aggregate.py --year 2026 --urls-only | pbcopy

# Copy all 2026 tracks to clipboard (Linux)
python3 skill/scripts/aggregate.py --year 2026 --urls-only | xclip -selection clipboard
```

Other aggregation modes:

```bash
python3 skill/scripts/aggregate.py --year 2026              # full year JSON with stats
python3 skill/scripts/aggregate.py --fighter "Max Holloway"  # single fighter history
```

## Output format

**JSON** (`data/{slug}.json`) — source of truth:
```json
{
  "event": "UFC 207: Nunes vs Rousey",
  "event_slug": "ufc-207",
  "songs": [
    {
      "fighter": "Amanda Nunes",
      "song_title": "American Oxygen",
      "artist": "Rihanna",
      "confidence": "silver",
      "spotify_url": "https://open.spotify.com/track/0bHA8LApeZHv7ZlhVUWg8X"
    },
    {
      "fighter": "Ronda Rousey",
      "song_title": "Bad Reputation",
      "artist": "Joan Jett",
      "confidence": "gold",
      "spotify_url": "https://open.spotify.com/track/7pu8AhGUxHZSCWTkQ2eb5M",
      "verified_by": {"user": "your_github_username", "method": "human", "reason": "Human verified from broadcast video"}
    }
  ]
}
```

**Markdown** (`viz/{slug}.md`) — generated from JSON:
```bash
python3 skill/scripts/generate_md.py                    # all events
python3 skill/scripts/generate_md.py data/ufc-207.json  # single event
```

## Evals

Ground truth files in `evals/ground-truth/` contain human-verified fighter → song mappings.

There are two different checks:

- `eval.py`: compares a fresh run against human ground truth
- `compare_runs.py`: compares a fresh run against the committed baseline in `data/`

Recommended workflow for testing the skill from scratch:

```bash
python3 skill/scripts/eval.py --data-dir /tmp/fresh-run ufc-207
python3 skill/scripts/compare_runs.py /tmp/fresh-run ufc-207
```

The first command answers “did the fresh run get the truth right?” The second answers “did the fresh run match the previously committed result?”

Use eval mode in the skill to write fresh output to a temp directory first. That avoids the merge behavior and gives a clean measure of the skill's raw output. See `evals/README.md` for details.

## Setup

1. Install an AI coding assistant that supports Agent Skills (e.g., [Claude Code](https://docs.anthropic.com/en/docs/claude-code))
2. Register a Spotify app at [developer.spotify.com](https://developer.spotify.com/dashboard)
3. Create `.env` in the repo root:
   ```
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   ```
4. For gold verification (optional): `uv tool install yt-dlp` and `sudo apt-get install ffmpeg`
