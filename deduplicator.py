"""Deduplication of parking records.

Primary key: 2GIS `id` field (stable, numeric).
Secondary: fuzzy name+address fingerprint to catch any items
that arrive without an id (rare, but defensive).
"""

import re
from typing import Any


def _fingerprint(record: dict) -> str:
    """Normalised string combining name and address."""
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.lower().strip())
    return f"{norm(record.get('name',''))}__{norm(record.get('address',''))}"


def deduplicate(records: list[dict]) -> list[dict]:
    """Return list with duplicates removed; prefer records with more filled fields."""
    best: dict[str, dict] = {}  # id -> record
    fp_seen: dict[str, str] = {}  # fingerprint -> id

    def _score(r: dict) -> int:
        return sum(1 for v in r.values() if v and v != "Unknown")

    for record in records:
        rid = record.get("id", "")
        fp = _fingerprint(record)

        if rid:
            if rid not in best or _score(record) > _score(best[rid]):
                best[rid] = record
            fp_seen[fp] = rid
        else:
            # No id — use fingerprint
            if fp in fp_seen:
                existing_id = fp_seen[fp]
                if _score(record) > _score(best.get(existing_id, {})):
                    synthetic_id = existing_id
                    best[synthetic_id] = record
            else:
                synthetic_id = f"noid_{len(best)}"
                record["id"] = synthetic_id
                best[synthetic_id] = record
                fp_seen[fp] = synthetic_id

    return list(best.values())
