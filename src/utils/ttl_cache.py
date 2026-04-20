"""Tiny thread-safe TTL cache for hot, low-write data (services menu, settings, packages).

Usage:
    cache = TTLCache(ttl_seconds=300)
    val = cache.get(("services", company_id))
    if val is None:
        val = expensive_lookup()
        cache.set(("services", company_id), val)

    cache.invalidate(("services", company_id))
    cache.invalidate_prefix("services")   # drop every services:* entry
    cache.clear()

Notes:
- In-process only. In a multi-worker setup, each worker has its own cache; a
  stale entry lives at most `ttl_seconds`. That's fine for values that are
  cheap to recompute and change rarely. For stronger consistency, use Redis.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Hashable, Optional


class TTLCache:
    __slots__ = ("_ttl", "_store", "_lock")

    def __init__(self, ttl_seconds: float = 300.0):
        self._ttl = float(ttl_seconds)
        self._store: dict[Hashable, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> Optional[Any]:
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < now:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: Hashable, value: Any, ttl_seconds: Optional[float] = None) -> None:
        ttl = self._ttl if ttl_seconds is None else float(ttl_seconds)
        expires_at = time.monotonic() + ttl
        with self._lock:
            self._store[key] = (expires_at, value)

    def invalidate(self, key: Hashable) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> None:
        """Drop entries whose key is a tuple starting with `prefix`."""
        with self._lock:
            to_delete = [
                k for k in self._store
                if isinstance(k, tuple) and len(k) > 0 and k[0] == prefix
            ]
            for k in to_delete:
                self._store.pop(k, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# Shared default cache for settings / services / packages (5 min TTL)
settings_cache = TTLCache(ttl_seconds=300)
