"""Persistent cache for Nominatim reverse geocoding results.

Stores results in geocache.json keyed by "lat,lon" (6 decimal places).
This avoids re-calling Nominatim for the same coordinates on every run.
"""

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).parent / "geocache.json"
_PRECISION = 6  # decimal places — ~0.1m precision, good enough to deduplicate


def _key(lat: float, lon: float) -> str:
    return f"{lat:.{_PRECISION}f},{lon:.{_PRECISION}f}"


class GeoCache:
    def __init__(self):
        self._data: dict[str, str] = {}
        self._dirty = False
        self._load()

    def _load(self):
        if _CACHE_FILE.exists():
            try:
                self._data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
                log.info("Geocache loaded: %d entries from %s", len(self._data), _CACHE_FILE)
            except Exception as exc:
                log.warning("Could not load geocache: %s", exc)
                self._data = {}

    def get(self, lat: float, lon: float) -> str | None:
        """Return cached address or None if not cached."""
        return self._data.get(_key(lat, lon))

    def set(self, lat: float, lon: float, address: str):
        """Store address in cache (in memory; call save() to persist)."""
        k = _key(lat, lon)
        if self._data.get(k) != address:
            self._data[k] = address
            self._dirty = True

    def save(self):
        """Write cache to disk only if anything changed."""
        if not self._dirty:
            return
        try:
            _CACHE_FILE.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info("Geocache saved: %d entries -> %s", len(self._data), _CACHE_FILE)
            self._dirty = False
        except Exception as exc:
            log.warning("Could not save geocache: %s", exc)
