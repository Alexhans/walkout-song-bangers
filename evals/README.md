# Eval: Walkout Songs Pipeline

## Ground truth files

`ground-truth/{slug}.expected.json` — human-verified fighter → song → artist mappings.

Fighters with empty `song_title`/`artist` are coverage-only: they verify the skill listed all fighters on the card, but don't score song accuracy.

Schema (no confidence or spotify_url — those are pipeline concerns):
```json
{
  "event": "UFC 229: Khabib vs McGregor",
  "event_slug": "ufc-229",
  "date": "2018-10-06",
  "location": "T-Mobile Arena, Las Vegas, Nevada",
  "songs": [
    {"fighter": "Khabib Nurmagomedov", "song_title": "Dagestan (Remix)", "artist": "SABINA, timaro"},
    {"fighter": "Scott Holtzman", "song_title": "", "artist": ""}
  ]
}
```

## Running evals

```bash
python3 skill/scripts/eval.py                                    # all events, data from data/
python3 skill/scripts/eval.py ufc-229                            # single event
python3 skill/scripts/eval.py --data-dir /tmp/fresh-run          # eval a fresh skill run
python3 skill/scripts/eval.py --data-dir /tmp/fresh-run ufc-229  # same, single event
```

Use `--data-dir` to point evals at a temp directory where the skill wrote fresh output. This avoids the merge behavior (where the skill preserves existing confidence) and gives a clean measure of the skill's raw accuracy.

## What evals measure

Evals measure the **skill's quality** (did it do its job?), not data completeness:

- **Fighter coverage**: Did the skill list all fighters on the card? Fighters with `confidence: "missing"` still count — the skill found them, it just didn't find their song.
- **Song accuracy**: For fighters with human-verified songs, did the skill get the right song? (fuzzy match, ≥70%)
- **Artist accuracy**: Same, for artist names (fuzzy, ≥60%)
- **Spotify quality**: Direct track links vs search fallbacks vs none

## Current ground truth events

| Event | Fighters | Verified songs | Source of verification |
|-------|----------|----------------|----------------------|
| UFC 229: Khabib vs McGregor | 24 | 9 | Broadcast video |
| UFC 217: Bisping vs St-Pierre | 22 | 8 | Broadcast video + Shazam |
| UFC Fight Night 140: Magny vs Ponzinibbio | 24 | 4 | Broadcast video |
