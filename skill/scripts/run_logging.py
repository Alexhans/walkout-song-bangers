#!/usr/bin/env python3
"""Structured JSON run logging for walkout-song scripts."""

from __future__ import annotations

import json
import re
import socket
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


LOG_ROOT = Path("/tmp/walkout-song-bangers-cache/logs")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_name(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "run"


class RunLogger:
    def __init__(self, script: str, subject: str) -> None:
        self.script = script
        self.subject = subject
        self.started_at = _utc_now()
        self._started_perf = time.perf_counter()
        self.data: dict = {
            "script": script,
            "subject": subject,
            "started_at": self.started_at,
            "hostname": socket.gethostname(),
            "events": [],
            "timings_ms": {},
        }

    def set_field(self, key: str, value) -> None:
        self.data[key] = value

    def append(self, event_type: str, **fields) -> None:
        event = {"type": event_type, "at": _utc_now()}
        event.update(fields)
        self.data["events"].append(event)

    def log_fetch(self, url: str, cache_hit: bool, cache_path: str = "", kind: str = "http") -> None:
        self.append(
            "fetch",
            kind=kind,
            url=url,
            cache_hit=cache_hit,
            cache_path=cache_path,
        )

    @contextmanager
    def stage(self, name: str):
        started = time.perf_counter()
        self.append("stage_start", stage=name)
        try:
            yield
        finally:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            self.data["timings_ms"][name] = elapsed_ms
            self.append("stage_end", stage=name, elapsed_ms=elapsed_ms)

    def finalize(self, error: dict | None = None) -> Path:
        total_ms = round((time.perf_counter() - self._started_perf) * 1000, 1)
        self.data["finished_at"] = _utc_now()
        self.data["total_ms"] = total_ms
        if error is not None:
            self.data["error"] = error
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        stamp = self.started_at.replace(":", "-")
        path = LOG_ROOT / f"{stamp}-{_safe_name(self.script)}-{_safe_name(self.subject)}.json"
        path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path
