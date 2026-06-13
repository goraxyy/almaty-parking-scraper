"""2GIS Catalog API client.

Docs: https://docs.2gis.com/en/api/search/places/overview
"""

import logging
import time
from typing import Iterator

import requests

from config import cfg

log = logging.getLogger(__name__)

BASE_URL = "https://catalog.api.2gis.com/3.0/items"
REGION_ID = "67"  # Almaty region_id from v2 region search

# All search terms that surface parking lots in 2GIS Almaty.
# Multiple terms maximise coverage within the demo key page cap.
SEARCH_QUERIES = [
    "парковка",
    "стоянка",
    "паркинг",
    "автостоянка",
    "parking",
    "подземная парковка",
    "многоуровневая парковка",
]

# Almaty district names for district-scoped queries.
DISTRICTS = [
    "Алатауский район",
    "Алмалинский район",
    "Ауэзовский район",
    "Бостандыкский район",
    "Жетысуский район",
    "Медеуский район",
    "Наурызбайский район",
    "Турксибский район",
]


class DGisClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "almaty-parking-scraper/1.0"})
        self._delay = 1.0 / cfg.REQUESTS_PER_SECOND
        self._last_call = 0.0

    def _throttle(self):
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last_call = time.monotonic()

    def _fetch_page(self, query: str, page: int) -> dict:
        self._throttle()
        params = {
            "q": query,
            "city_id": REGION_ID,
            "page": page,
            "page_size": 10,
            "fields": (
                "items.id,items.name,items.full_name,items.address,"
                "items.point,items.url,items.schedule,items.contact_groups,"
                "items.rubrics,items.attribute_groups,items.org,"
                "items.ads.options,items.capacity"
            ),
            "key": cfg.DGIS_API_KEY,
        }
        resp = self.session.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def iter_places(self, query: str) -> Iterator[dict]:
        """Yield raw place dicts for a given query, up to MAX_PAGES."""
        for page in range(1, cfg.MAX_PAGES + 1):
            try:
                data = self._fetch_page(query, page)
            except requests.HTTPError as exc:
                log.warning("HTTP error on query=%r page=%d: %s", query, page, exc)
                break

            items = data.get("result", {}).get("items", [])
            if not items:
                log.debug("No items on query=%r page=%d — stopping.", query, page)
                break

            yield from items
            log.debug("Fetched %d items (query=%r, page=%d)", len(items), query, page)

            total = data.get("result", {}).get("total", 0)
            fetched_so_far = page * 10
            if fetched_so_far >= total:
                break

    def collect_all(self) -> list[dict]:
        """Run all queries + district-scoped queries and return deduplicated raw items."""
        seen_ids: set[str] = set()
        all_items: list[dict] = []

        queries = list(SEARCH_QUERIES)
        # District-scoped queries: e.g. "парковка Медеуский район"
        for district in DISTRICTS:
            queries.append(f"парковка {district}")

        for query in queries:
            log.info("Querying: %r", query)
            for item in self.iter_places(query):
                item_id = str(item.get("id", ""))
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    all_items.append(item)

        log.info("Total unique raw items collected: %d", len(all_items))
        return all_items
