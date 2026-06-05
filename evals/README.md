# Eval: Walkout Songs Pipeline

## Ground truth files

`ground-truth/{slug}.expected.json` — human-verified fighter → song → artist mappings.

Fighters with empty `song_title`/`artist` are coverage-only: they verify the skill listed all fighters on the card, but don't score song accuracy.

Schema (no confidence or spotify_url — those are pipeline concerns):
```json
{
  "event": "UFC 207: Nunes vs Rousey",
  "event_slug": "ufc-207",
  "date": "2016-12-30",
  "location": "T-Mobile Arena, Las Vegas, Nevada",
  "songs": [
    {"fighter": "Amanda Nunes", "song_title": "American Oxygen", "artist": "Rihanna"},
    {"fighter": "Ronda Rousey", "song_title": "Bad Reputation", "artist": "Joan Jett"}
  ]
}
```

## Running evals

For a clean agent test, do not evaluate from committed `data/`. Evaluate from a fresh temp directory.

```bash
python3 skill/scripts/eval.py --data-dir /tmp/fresh-run ufc-207
python3 skill/scripts/compare_runs.py /tmp/fresh-run ufc-207
```

Use `eval.py` to score the fresh run against human ground truth.

Use `compare_runs.py` to compare the fresh run against the committed baseline in `data/`. This answers a different question: whether a fresh Codex run matches the previously committed Claude output.

If you want to score all fresh outputs in a temp dir, you can still run:

```bash
python3 skill/scripts/eval.py --data-dir /tmp/fresh-run
python3 skill/scripts/compare_runs.py /tmp/fresh-run
```

## Source-gating evals

These evals test whether a source should be accepted for coverage at all before extraction happens.

They do not score full event output. They score source classification:

- reject invalid guesswork such as pre-fight previews and "usually walks out to" profile pieces
- accept valid post-event coverage that explicitly confirms what fighters walked out to

Run them with:

```bash
python3 skill/scripts/eval_source_gating.py
python3 skill/scripts/eval_source_gating.py lowkick-pre-fight-328
python3 skill/scripts/eval_source_gating.py mmajunkie-post-event-229
```

Current fixtures:

| Fixture | Expected result | Purpose |
|---------|-----------------|---------|
| `lowkick-pre-fight-328` | reject (`invalid_guesswork`) | guards against pre-fight/profile guesswork being promoted to coverage |
| `essentiallysports-profile-postdated-328` | reject (`invalid_guesswork`) | guards against post-dated but still non-confirmatory profile wording such as `known for` or `have used before` |
| `mmajunkie-post-event-229` | accept (`valid_post_event`) | verifies that explicit post-event wording passes the gate and yields extractable fighter/song pairs |

## What evals measure

Evals measure the **skill's quality** (did it do its job?), not data completeness:

- **Fighter coverage**: Did the skill list all fighters on the card? Fighters with `confidence: "missing"` still count — the skill found them, it just didn't find their song.
- **Song accuracy**: For fighters with human-verified songs, did the skill get the right song? (fuzzy match, ≥70%)
- **Artist accuracy**: Same, for artist names (fuzzy, ≥60%)
- **Spotify quality**: Direct track links vs search fallbacks vs none

Source-gating evals additionally measure:

- **Source eligibility**: Is the article valid for `bronze`/`silver` promotion at all?
- **Rejection of guesswork**: Does the gate block pre-fight/profile wording?
- **Acceptance of confirmation**: Does the gate allow explicit post-event confirmation wording?

## Current ground truth events

| Event | Fighters | Verified songs | Source of verification |
|-------|----------|----------------|----------------------|
| UFC 207: Nunes vs Rousey | 20 | 2 | Broadcast video |
| UFC 229: Khabib vs McGregor | 24 | 9 | Broadcast video |
| UFC 217: Bisping vs St-Pierre | 22 | 8 | Broadcast video + Shazam |
| UFC Fight Night 140: Magny vs Ponzinibbio | 24 | 4 | Broadcast video |
