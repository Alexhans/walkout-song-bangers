# Source Gating Plan

## Goal

Prevent the walkout-songs skill from promoting fighters out of `missing` based on pre-fight previews, profile pieces, or "usually walks out to" guesswork.

## Problem

Some articles look event-specific because they mention a card and list fighters, but they do not confirm what actually happened at that event. They instead describe:

- potential walkout songs
- songs fighters have used in previous appearances
- songs fighters typically or usually use
- fight-night previews written before the event happened

Those sources are invalid for `bronze` or `silver` coverage.

## Proposed Eval

Add a source-gating eval that tests source classification before extraction.

### Fixture

Store a short saved excerpt from an invalid article that contains tempting but disallowed phrasing such as:

- `tonight`
- `potential walkout songs`
- `have chosen for their previous Octagon appearances`
- `typically marches to the Octagon`

### Expected behavior

- classify the source as `invalid_guesswork`
- reject all fighter-song pairs from that source
- keep affected fighters as `missing`
- do not emit `bronze` or `silver` from that source

## Suggested files

- `evals/source-gating/lowkick-pre-fight-328.txt`
- `evals/source-gating/lowkick-pre-fight-328.expected.json`
- `skill/scripts/eval_source_gating.py`

## Pass criteria

- the source is rejected
- no extracted pair from the fixture appears in output coverage
- the eval reports which banned phrases triggered rejection

## Follow-up

If this eval proves useful, add at least one valid post-event fixture as the positive control so the gating logic is tested both ways.
