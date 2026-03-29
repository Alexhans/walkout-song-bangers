#!/usr/bin/env python3
"""Discover likely MMA Junkie Fight Tracks URLs for a UFC event.

Usage:
  python3 skill/scripts/discover_fight_tracks.py "UFC 307"
  python3 skill/scripts/discover_fight_tracks.py "UFC Fight Night: Perez vs. Taira"
  python3 skill/scripts/discover_fight_tracks.py ufc-fight-night-sandhagen-vs-nurmagomedov --json
"""

from __future__ import annotations

import hashlib
import base64
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from run_logging import RunLogger


CACHE_DIR = Path("/tmp/walkout-song-bangers-cache")
HTTP_CACHE_DIR = CACHE_DIR / "http"
DISCOVERY_CACHE_DIR = CACHE_DIR / "discovery"
UFCSTATS_EVENTS_CACHE = CACHE_DIR / "ufcstats-events.html"

UFCSTATS_EVENTS_URL = "http://www.ufcstats.com/statistics/events/completed?page=all"
YAHOO_SEARCH_ROOT = "https://search.yahoo.com/search?p="
BING_SEARCH_ROOT = "https://www.bing.com/search?q="

GOOD_DOMAINS = (
    "mmajunkie.usatoday.com",
    "mmajunkie-eu.usatoday.com",
    "sports.yahoo.com",
    "uk.news.yahoo.com",
    "ca.sports.yahoo.com",
    "www.inkl.com",
    "inkl.com",
)

NEGATIVE_URL_TOKENS = (
    "official-scorecards",
    "scorecards",
    "photo",
    "photos",
    "gallery",
    "results",
    "live",
    "what-time-is",
    "walkout-time",
    "preview",
    "countdown",
    "odds",
    "/events/",
)

POSITIVE_URL_TOKENS = (
    "fight-tracks",
    "walkout",
    "songs",
    "music",
)

STRONG_ARTICLE_SIGNALS = (
    "fight tracks",
    "walkout songs",
    "walkout music",
)


@dataclass(frozen=True)
class EventInfo:
    event: str
    event_slug: str
    event_url: str
    date: str


def _collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _slugify(s: str) -> str:
    s = html.unescape(s).lower()
    s = re.sub(r"['’`]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _norm(s: str) -> str:
    s = html.unescape(s).lower()
    s = re.sub(r"['’`]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return _collapse_ws(s)


def _ensure_cache_dirs() -> None:
    HTTP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DISCOVERY_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _http_get(
    url: str,
    cache_path: Path | None = None,
    use_cache: bool = True,
    logger: RunLogger | None = None,
    kind: str = "http",
) -> str:
    if cache_path and use_cache and cache_path.exists():
        if logger:
            logger.log_fetch(url=url, cache_hit=True, cache_path=str(cache_path), kind=kind)
        return cache_path.read_text(encoding="utf-8", errors="replace")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")

    if logger:
        logger.log_fetch(
            url=url,
            cache_hit=False,
            cache_path=str(cache_path) if cache_path else "",
            kind=kind,
        )
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(body, encoding="utf-8")
    return body


def _cached_http_get(url: str, use_cache: bool = True, logger: RunLogger | None = None, kind: str = "http") -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return _http_get(
        url,
        cache_path=HTTP_CACHE_DIR / f"{digest}.html",
        use_cache=use_cache,
        logger=logger,
        kind=kind,
    )


def _fetch_ufcstats_events(use_cache: bool = True, logger: RunLogger | None = None) -> str:
    return _http_get(
        UFCSTATS_EVENTS_URL,
        cache_path=UFCSTATS_EVENTS_CACHE,
        use_cache=use_cache,
        logger=logger,
        kind="ufcstats-events",
    )


def _parse_ufcstats_events(index_html: str) -> list[EventInfo]:
    out: list[EventInfo] = []
    seen: set[str] = set()
    for m in re.finditer(
        r'<a\s+href="(?P<url>http://www\.ufcstats\.com/event-details/[^"]+)"[^>]*>(?P<name>[^<]+)</a>',
        index_html,
    ):
        name = _collapse_ws(html.unescape(m.group("name")))
        if not name:
            continue
        numbered = re.match(r"(?i)^ufc\s+(\d{1,4})\b", name)
        slug = f"ufc-{numbered.group(1)}" if numbered else _slugify(name)
        if slug in seen:
            continue
        seen.add(slug)
        out.append(EventInfo(event=name, event_slug=slug, event_url=m.group("url"), date=""))
    return out


def _parse_ufcstats_date(event_url: str, use_cache: bool = True, logger: RunLogger | None = None) -> str:
    page = _cached_http_get(event_url, use_cache=use_cache, logger=logger, kind="ufcstats-event")
    match = re.search(r"Date:\s*</i>\s*([^<]+)</li>", page, flags=re.I)
    if not match:
        text = html.unescape(re.sub(r"<[^>]+>", " ", page))
        match = re.search(r"\bDate:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})\b", text)
    if not match:
        return ""

    date_text = _collapse_ws(match.group(1))
    dm = re.match(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", date_text)
    if not dm:
        return ""
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
    mon = month.get(dm.group(1).lower()[:3])
    if not mon:
        return ""
    return f"{int(dm.group(3)):04d}-{mon:02d}-{int(dm.group(2)):02d}"


def _parse_event_number(arg: str) -> int | None:
    s = arg.strip().lower().replace("ufc", "").replace("-", " ")
    m = re.fullmatch(r"\s*(\d{1,4})\s*", s)
    if not m:
        return None
    return int(m.group(1))


def _resolve_event(arg: str, use_cache: bool = True, logger: RunLogger | None = None) -> EventInfo:
    index_html = _fetch_ufcstats_events(use_cache=use_cache, logger=logger)
    events = _parse_ufcstats_events(index_html)
    raw = _collapse_ws(arg)
    norm = _norm(raw)
    slugish = _slugify(raw)
    event_number = _parse_event_number(raw)

    if event_number is not None:
        want = f"ufc-{event_number}"
        for event in events:
            if event.event_slug == want:
                return EventInfo(
                    event=event.event,
                    event_slug=event.event_slug,
                    event_url=event.event_url,
                    date=_parse_ufcstats_date(event.event_url, use_cache=use_cache, logger=logger),
                )

    for event in events:
        if event.event_slug == slugish:
            return EventInfo(
                event=event.event,
                event_slug=event.event_slug,
                event_url=event.event_url,
                date=_parse_ufcstats_date(event.event_url, use_cache=use_cache, logger=logger),
            )
        if _norm(event.event) == norm:
            return EventInfo(
                event=event.event,
                event_slug=event.event_slug,
                event_url=event.event_url,
                date=_parse_ufcstats_date(event.event_url, use_cache=use_cache, logger=logger),
            )

    for event in events:
        if event.event.startswith(raw):
            return EventInfo(
                event=event.event,
                event_slug=event.event_slug,
                event_url=event.event_url,
                date=_parse_ufcstats_date(event.event_url, use_cache=use_cache, logger=logger),
            )

    if "vs" in norm:
        want_tokens = set(norm.split())
        matches: list[tuple[int, EventInfo]] = []
        for event in events:
            tokens = set(_norm(event.event).split())
            overlap = len(tokens & want_tokens)
            if overlap >= 2:
                matches.append((overlap, event))
        if matches:
            matches.sort(key=lambda item: item[0], reverse=True)
            event = matches[0][1]
            return EventInfo(
                event=event.event,
                event_slug=event.event_slug,
                event_url=event.event_url,
                date=_parse_ufcstats_date(event.event_url, use_cache=use_cache, logger=logger),
            )

    raise RuntimeError(f"Could not resolve event from UFCStats: {arg!r}")


def _event_aliases(event: EventInfo) -> list[str]:
    aliases: list[str] = [event.event]
    short = event.event.split(":", 1)[0].strip()
    if short and short not in aliases:
        aliases.append(short)

    if ":" in event.event:
        tail = _collapse_ws(event.event.split(":", 1)[1])
        if tail and tail not in aliases:
            aliases.append(tail)

    m = re.match(r"(?i)^ufc\s+(\d{1,4})\b", event.event)
    if m:
        numbered = f"UFC {m.group(1)}"
        if numbered not in aliases:
            aliases.append(numbered)

    # Heuristic aliases for Fight Night cards. These do not assume the broadcast family,
    # but they give search engines enough headliner context to surface mirrors.
    if event.event.lower().startswith("ufc fight night:") and ":" in event.event:
        tail = _collapse_ws(event.event.split(":", 1)[1])
        if tail:
            aliases.append(f"Fight Tracks {tail}")
            aliases.append(f"UFC Fight Night {tail}")

    deduped: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        key = _norm(alias)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(alias)
    return deduped


def _search_queries(event: EventInfo) -> list[str]:
    aliases = _event_aliases(event)
    queries: list[str] = []

    for alias in aliases:
        queries.append(f"Fight Tracks {alias}")
        queries.append(f"walkout songs {alias} mmajunkie")
        queries.append(f"site:mmajunkie.usatoday.com {alias} walkout songs")
        queries.append(f"site:sports.yahoo.com {alias} walkout songs")
        queries.append(f"site:inkl.com {alias} walkout songs")

    headliner = None
    if ":" in event.event:
        headliner = _collapse_ws(event.event.split(":", 1)[1])
    if headliner:
        queries.append(f"Fight Tracks {headliner}")
        queries.append(f"{headliner} walkout songs mmajunkie")

    if re.match(r"(?i)^ufc\s+\d{1,4}\b", event.event):
        queries.append(f"Fight Tracks {event.event}")

    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        key = _norm(query)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(query)
    return deduped


def _extract_result_urls(search_html: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    for ru in re.findall(r"/RU=([^/]+)/RK=", search_html):
        url = urllib.parse.unquote(ru)
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls


def _extract_result_urls_bing(search_html: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    for raw in re.findall(r'href="([^"]+)"', search_html):
        href = html.unescape(raw)
        if "bing.com/ck/a" in href:
            parsed = urllib.parse.urlparse(href)
            payload = urllib.parse.parse_qs(parsed.query).get("u", [""])[0]
            if payload:
                payload = payload[2:] if payload.startswith("a1") else payload
                pad = "=" * ((4 - len(payload) % 4) % 4)
                try:
                    href = base64.b64decode(payload + pad).decode("utf-8", errors="replace")
                except Exception:
                    continue
        if not href.startswith("http"):
            continue
        if href in seen:
            continue
        seen.add(href)
        urls.append(href)
    return urls


def _candidate_domain(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.lower()


def _is_low_value_candidate(url: str) -> tuple[bool, str]:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower().strip()
    if not path or path in {"/", ""}:
        return (True, "site-root")
    if not any(token in url.lower() for token in POSITIVE_URL_TOKENS):
        if any(token in path for token in ("/events/", "/event/")):
            return (True, "event-index")
    for token in NEGATIVE_URL_TOKENS:
        if token in url.lower():
            return (True, f"negative-url-token:{token}")
    return (False, "")


def _extract_publication_date(page_html: str) -> str:
    patterns = (
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'property="article:published_time"\s+content="([^"]+)"',
        r'name="publish-date"\s+content="([^"]+)"',
        r'name="article:published_time"\s+content="([^"]+)"',
        r'<time[^>]+datetime="([^"]+)"',
    )
    for pattern in patterns:
        match = re.search(pattern, page_html, flags=re.I)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return ""


def _extract_page_title(page_html: str) -> str:
    for pattern in (
        r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
        r'<meta[^>]+name="twitter:title"[^>]+content="([^"]+)"',
        r"<title>(.*?)</title>",
    ):
        match = re.search(pattern, page_html, flags=re.I | re.S)
        if match:
            title = _collapse_ws(html.unescape(match.group(1)))
            if title:
                return title
    return ""


def _publication_date_score(event_date: str, published_at: str) -> tuple[int, list[str]]:
    reasons: list[str] = []
    if not event_date or not published_at:
        return 0, reasons

    pub_date: datetime | None = None
    candidates = [published_at]
    if published_at.endswith("Z"):
        candidates.append(published_at.replace("Z", "+00:00"))
    if len(published_at) >= 10:
        candidates.append(published_at[:10])

    for candidate in candidates:
        try:
            if len(candidate) == 10:
                pub_date = datetime.strptime(candidate, "%Y-%m-%d")
            else:
                pub_date = datetime.fromisoformat(candidate)
            break
        except ValueError:
            continue

    if pub_date is None:
        return 0, reasons

    try:
        event_dt = datetime.strptime(event_date, "%Y-%m-%d")
    except ValueError:
        return 0, reasons

    delta_days = abs((pub_date.date() - event_dt.date()).days)
    if delta_days <= 3:
        reasons.append(f"published-near-event:{delta_days}")
        return 25, reasons
    if delta_days <= 14:
        reasons.append(f"published-close:{delta_days}")
        return 10, reasons
    if pub_date.year == event_dt.year:
        reasons.append(f"published-same-year:{pub_date.year}")
        return 0, reasons

    reasons.append(f"published-year-mismatch:{pub_date.year}")
    return -35, reasons


def _has_strong_event_match(candidate: dict[str, object]) -> bool:
    reasons = [str(reason) for reason in candidate.get("reasons", [])]
    strong_prefixes = (
        "canonical-event-match",
        "headliner-match",
        "ufc-number-match:url",
        "ufc-number-match:text",
        "published-near-event",
    )
    return any(reason == prefix or reason.startswith(prefix) for reason in reasons for prefix in strong_prefixes)


def _score_candidate(event: EventInfo, url: str, page_html: str) -> tuple[int, list[str]]:
    domain = _candidate_domain(url)
    text = html.unescape(page_html)
    text_norm = _norm(re.sub(r"<[^>]+>", " ", text))
    title = _extract_page_title(page_html)
    title_norm = _norm(title)
    score = 0
    reasons: list[str] = []

    has_fight_tracks_signal = False
    has_event_match = False

    if any(domain.endswith(good) or domain == good for good in GOOD_DOMAINS):
        score += 20
        reasons.append("preferred-domain")
    low_value, why_low = _is_low_value_candidate(url)
    if low_value:
        score -= 40
        reasons.append(why_low)
    if "fight-tracks" in url or "fight_tracks" in url:
        score += 20
        reasons.append("fight-tracks-url")
        has_fight_tracks_signal = True
    if any(token in url.lower() for token in ("walkout", "songs", "music")):
        score += 10
        reasons.append("walkout-url")
        has_fight_tracks_signal = True
    if "fight tracks" in text_norm:
        score += 20
        reasons.append("fight-tracks-text")
        has_fight_tracks_signal = True
    for signal in STRONG_ARTICLE_SIGNALS:
        if signal in title_norm:
            score += 30
            reasons.append(f"title-signal:{signal}")
            has_fight_tracks_signal = True
            break
    if "fight tracks" in title_norm:
        score += 10
        reasons.append("fight-tracks-title")
        has_fight_tracks_signal = True

    pub_score, pub_reasons = _publication_date_score(event.date, _extract_publication_date(page_html))
    score += pub_score
    reasons.extend(pub_reasons)
    if any(reason.startswith("published-near-event") for reason in pub_reasons):
        has_event_match = True

    event_norm = _norm(event.event)
    if event_norm and (event_norm in text_norm or event_norm in title_norm):
        score += 25
        reasons.append("canonical-event-match")
        has_event_match = True

    numbered_event = re.match(r"(?i)^ufc\s+(\d{1,4})\b", event.event)
    if numbered_event:
        event_num = numbered_event.group(1)
        num_in_url = re.search(r"\bufc-(\d{1,4})\b", url.lower())
        num_in_text = re.search(r"\bufc\s+(\d{1,4})\b", text_norm)
        if num_in_url and num_in_url.group(1) == event_num:
            score += 20
            reasons.append("ufc-number-match:url")
            has_event_match = True
        elif num_in_url and num_in_url.group(1) != event_num:
            score -= 35
            reasons.append(f"ufc-number-mismatch:url:{num_in_url.group(1)}")
        num_in_title = re.search(r"\bufc\s+(\d{1,4})\b", title_norm)
        if num_in_text and num_in_text.group(1) == event_num:
            score += 10
            reasons.append("ufc-number-match:text")
            has_event_match = True
        elif num_in_text and num_in_text.group(1) != event_num:
            score -= 20
            reasons.append(f"ufc-number-mismatch:text:{num_in_text.group(1)}")
        if num_in_title and num_in_title.group(1) == event_num:
            score += 20
            reasons.append("ufc-number-match:title")
            has_event_match = True
        elif num_in_title and num_in_title.group(1) != event_num:
            score -= 40
            reasons.append(f"ufc-number-mismatch:title:{num_in_title.group(1)}")

    if ":" in event.event:
        tail = _norm(event.event.split(":", 1)[1])
        if tail and (tail in text_norm or tail in title_norm):
            score += 20
            reasons.append("headliner-match")
            has_event_match = True
        tail_parts = [part for part in re.split(r"\s+", tail) if len(part) > 2]
        overlap = sum(1 for part in tail_parts if part in text_norm)
        if overlap >= 2:
            score += min(overlap * 3, 12)
            reasons.append(f"headliner-token-overlap:{overlap}")
            has_event_match = True
        if tail_parts and all(part in text_norm for part in tail_parts):
            score += 15
            reasons.append("all-headliner-tokens")
            has_event_match = True

    event_year = event.date[:4] if event.date else ""
    year_in_url = re.search(r"/(20\d{2})/", url)
    if event_year and year_in_url:
        if year_in_url.group(1) == event_year:
            score += 10
            reasons.append("year-match")
        else:
            score -= 25
            reasons.append(f"year-mismatch:{year_in_url.group(1)}")

    song_patterns = (
        ' by ',
        ' def. ',
        ' vs. ',
        ' walked out to ',
        'walkout songs',
    )
    pattern_hits = sum(1 for pattern in song_patterns if pattern in text.lower())
    if pattern_hits >= 2:
        score += 10
        reasons.append("walkout-patterns")

    if not has_fight_tracks_signal:
        score -= 45
        reasons.append("no-fight-tracks-signal")

    if has_fight_tracks_signal and not has_event_match:
        score -= 35
        reasons.append("no-event-match")

    return score, reasons


def _fetch_search_html(query: str, use_cache: bool, logger: RunLogger | None) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []

    yahoo_url = YAHOO_SEARCH_ROOT + urllib.parse.quote_plus(query)
    try:
        results.append(
            ("yahoo", _cached_http_get(yahoo_url, use_cache=use_cache, logger=logger, kind="search:yahoo"))
        )
    except Exception as exc:
        if logger:
            logger.append("search_error", provider="yahoo", query=query, error=str(exc))

    bing_url = BING_SEARCH_ROOT + urllib.parse.quote_plus(query)
    try:
        results.append(
            ("bing", _cached_http_get(bing_url, use_cache=use_cache, logger=logger, kind="search:bing"))
        )
    except Exception as exc:
        if logger:
            logger.append("search_error", provider="bing", query=query, error=str(exc))

    return results


def _discover_candidates(
    event: EventInfo, use_cache: bool = True, logger: RunLogger | None = None
) -> list[dict[str, object]]:
    candidates: dict[str, dict[str, object]] = {}

    for query in _search_queries(event):
        for provider, search_html in _fetch_search_html(query, use_cache=use_cache, logger=logger):
            extracted = _extract_result_urls(search_html) if provider == "yahoo" else _extract_result_urls_bing(search_html)
            for url in extracted:
                domain = _candidate_domain(url)
                if not any(domain.endswith(good) or domain == good for good in GOOD_DOMAINS):
                    continue
                if url in candidates:
                    existing_queries = candidates[url]["queries"]
                    if isinstance(existing_queries, list):
                        stamp = f"{provider}:{query}"
                        if stamp not in existing_queries:
                            existing_queries.append(stamp)
                    continue
                low_value, why_low = _is_low_value_candidate(url)
                if low_value and why_low in {"site-root", "event-index"}:
                    if logger:
                        logger.append("candidate_skipped", provider=provider, query=query, url=url, reason=why_low)
                    continue
                try:
                    page_html = _cached_http_get(url, use_cache=use_cache, logger=logger, kind="candidate")
                except Exception as exc:
                    if logger:
                        logger.append("candidate_fetch_error", provider=provider, query=query, url=url, error=str(exc))
                    continue
                score, reasons = _score_candidate(event, url, page_html)
                if logger:
                    logger.append(
                        "candidate_scored",
                        provider=provider,
                        query=query,
                        url=url,
                        domain=domain,
                        score=score,
                        reasons=reasons,
                    )
                candidates[url] = {
                    "url": url,
                    "domain": domain,
                    "score": score,
                    "reasons": reasons,
                    "queries": [f"{provider}:{query}"],
                }

    ranked = sorted(candidates.values(), key=lambda item: int(item["score"]), reverse=True)
    return ranked



def _cache_path_for_event(slug: str) -> Path:
    return DISCOVERY_CACHE_DIR / f"{slug}.json"


def discover(arg: str, use_cache: bool = True, logger: RunLogger | None = None) -> dict[str, object]:
    _ensure_cache_dirs()
    event = _resolve_event(arg, use_cache=use_cache, logger=logger)
    cache_path = _cache_path_for_event(event.event_slug)

    if use_cache and cache_path.exists():
        if logger:
            logger.log_fetch(
                url=f"discovery:{event.event_slug}",
                cache_hit=True,
                cache_path=str(cache_path),
                kind="discovery-cache",
            )
        return json.loads(cache_path.read_text(encoding="utf-8", errors="replace"))

    aliases = _event_aliases(event)
    queries = _search_queries(event)
    candidates = _discover_candidates(event, use_cache=use_cache, logger=logger)
    best_candidate = None
    if (
        candidates
        and int(candidates[0]["score"]) >= 70
        and "no-fight-tracks-signal" not in candidates[0]["reasons"]
        and _has_strong_event_match(candidates[0])
    ):
        best_candidate = candidates[0]

    payload = {
        "event": event.event,
        "event_slug": event.event_slug,
        "date": event.date,
        "event_url": event.event_url,
        "aliases": aliases,
        "queries": queries,
        "best_url": best_candidate["url"] if best_candidate else "",
        "best_domain": best_candidate["domain"] if best_candidate else "",
        "candidates": candidates[:10],
    }
    cache_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if logger:
        logger.log_fetch(
            url=f"discovery:{event.event_slug}",
            cache_hit=False,
            cache_path=str(cache_path),
            kind="discovery-cache",
        )
        logger.set_field("event", event.event)
        logger.set_field("event_slug", event.event_slug)
        logger.set_field("date", event.date)
        logger.set_field("aliases", aliases)
        logger.set_field("queries", queries)
        logger.set_field("best_url", payload["best_url"])
        logger.set_field("candidate_count", len(candidates))
    return payload


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__.strip())
        return 2

    use_cache = True
    json_mode = False
    terms: list[str] = []
    for arg in argv[1:]:
        if arg == "--json":
            json_mode = True
            continue
        if arg == "--refresh":
            use_cache = False
            continue
        terms.append(arg)

    if not terms:
        print(__doc__.strip())
        return 2

    subject = " ".join(terms)
    logger = RunLogger(script="discover_fight_tracks", subject=subject)
    logger.set_field("use_cache", use_cache)
    try:
        with logger.stage("discover"):
            payload = discover(subject, use_cache=use_cache, logger=logger)
        log_path = logger.finalize()
    except Exception as exc:
        logger.append("exception", error_type=type(exc).__name__, error=str(exc))
        log_path = logger.finalize({"type": type(exc).__name__, "message": str(exc)})
        print(f"Log: {log_path}")
        raise
    if json_mode:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"Event: {payload['event']}")
    print(f"Slug: {payload['event_slug']}")
    print(f"UFCStats: {payload['event_url']}")
    print("Aliases:")
    for alias in payload["aliases"]:
        print(f"  - {alias}")
    print(f"Best: {payload['best_url'] or '(none)'}")
    if payload["candidates"]:
        print("Candidates:")
        for item in payload["candidates"]:
            reasons = ", ".join(item["reasons"])
            print(f"  - {item['score']:>3} {item['url']} [{reasons}]")
    print(f"Log: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
