# 2025 Source Findings

## Scope

Checked `UFC 311`, `UFC 312`, and `UFC 313` against the same source families that have been productive for 2026:

- Sherdog / The Walkmen
- MMA Junkie / Yahoo / Inkl Fight Tracks mirrors
- EssentiallySports
- Sportskeeda
- YouTube walkout clips

## Findings

### UFC 311

- `discover_fight_tracks.py` found plausible Yahoo, MMA Junkie, and Inkl candidates.
- It returned no `best_url`, which is acceptable under the strict rule if no true Fight Tracks page exists.
- The candidate list shows discovery is not empty, but the winning candidates lack explicit Fight Tracks signals.
- Web search surfaced pre-event sources from EssentiallySports and Sportskeeda, which are not strict enough for event data.
- Web search also surfaced fighter-specific YouTube entries for some fighters, including:
  - Islam Makhachev
  - Renato Moicano
  - Merab Dvalishvili
- Those can help individual verification, but they do not solve full-card event coverage on their own.

### UFC 312

- `discover_fight_tracks.py` incorrectly selected a `walkout-time` MMA Junkie page as `best_url`.
- That page is about timing, not a Fight Tracks walkout-source article.
- This is a real discovery bug: walkout-related wording alone was enough to beat the strict filter.
- Web search again mostly surfaced pre-event "used before" or "likely to use" articles from EssentiallySports and Sportskeeda.

### UFC 313

- `discover_fight_tracks.py` found plausible Yahoo, MMA Junkie, and Inkl candidates but returned no `best_url`.
- Web search again mostly surfaced pre-event "used before" articles.
- There is at least one fighter-specific post-event YouTube walkout source for Justin Gaethje, but not enough reliable event-level coverage from search alone.

## Skill Issues Identified

### 1. Discovery promoted non-source pages

- `walkout-time`
- `what-time-is`
- similar timing / preview pages

These should be retained as diagnostics only, not selected as `best_url`.

### 2. Discovery is too permissive about "walkout" wording

Pages can win based on:

- walkout-related URL tokens
- event match
- publication date proximity

without any true Fight Tracks-style evidence.

### 3. Discovery is too slow when sources are weak

- The live discovery and Walkmen paths can hang for a long time instead of failing fast.
- This makes 2025 backfill work expensive even when it produces no usable result.

### 4. Strict coverage for 2025 PPVs is still source-limited

- Pre-event "used before" articles are easy to find.
- True post-event, full-card walkout sources are much harder to surface for these events.

## Changes Applied

Updated `skill/scripts/discover_fight_tracks.py` so a candidate now needs:

- a strong event match
- a strong Fight Tracks-style signal
- and no disqualifying timing / preview reasons

before it can become `best_url`.

Specifically, `best_url` selection now disqualifies candidates with:

- `negative-url-token:walkout-time`
- `negative-url-token:what-time-is`
- `negative-url-token:preview`
- `negative-url-token:live`

and requires stronger Fight Tracks signals than `walkout-url` alone.

## Recommended Next Improvements

1. Add provider-level timeouts and fail-fast behavior to discovery.
2. Record a clearer final reason when no `best_url` is chosen.
3. Consider a separate fallback lane for fighter-specific post-event YouTube walkout evidence.
4. Consider a numbered-PPV workflow that tries Sherdog / Walkmen, then Fight Tracks, then stops quickly.
