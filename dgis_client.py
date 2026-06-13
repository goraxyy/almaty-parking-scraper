"""2GIS Catalog API client.

Strategy:
  Step 1 - Search queries collect item IDs (search endpoint returns minimal fields).
  Step 2 - byid in batches of 50 fetches full data (point, schedule, capacity, etc.).
  Step 3 - Reverse geocode coordinates -> street address for items missing address.name.

Docs: https://docs.2gis.com/en/api/search/places/overview
      https://docs.2gis.com/en/api/search/geocoder/overview
"""

import logging
import time
from typing import Iterator

import requests

from config import cfg

log = logging.getLogger(__name__)

SEARCH_URL = "https://catalog.api.2gis.com/3.0/items"
BYID_URL = "https://catalog.api.2gis.com/3.0/items/byid"
GEOCODE_URL = "https://catalog.api.2gis.com/3.0/items/geocode"
REGION_ID = "67"  # Almaty

SEARCH_QUERIES = [
    "парковка",
    "стоянка",
    "паркинг",
    "автостоянка",
    "parking",
    "подземная парковка",
    "многоуровная парковка",
]

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

# Full fields available via byid endpoint
_BYID_FIELDS = (
    "items.id,items.name,items.full_name,"
    "items.address.name,items.address.components,"
    "items.point,items.url,items.schedule,"
    "items.rubrics,items.attribute_groups,items.capacity,"
    "items.org"
)


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

    def _fetch_search_page(self, query: str, page: int) -> dict:
        """Search endpoint — returns IDs only (address/schedule not available here)."""
        self._throttle()
        params = {
            "q": query,
            "region_id": REGION_ID,
            "page": page,
            "page_size": 10,
            "fields": "items.id",
            "key": cfg.DGIS_API_KEY,
        }
        resp = self.session.get(SEARCH_URL, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _fetch_byid_batch(self, ids: list[str]) -> list[dict]:
        """Fetch full details for up to 50 IDs at once via byid endpoint."""
        self._throttle()
        params = {
            "id": ",".join(ids),
            "fields": _BYID_FIELDS,
            "key": cfg.DGIS_API_KEY,
        }
        resp = self.session.get(BYID_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", {}).get("items", [])

    def _reverse_geocode(self, lat: float, lon: float) -> str:
        """Return nearest street address for given coordinates, or empty string."""
        self._throttle()
        params = {
            "lat": lat,
            "lon": lon,
            "fields": "items.address.name",
            "key": cfg.DGIS_API_KEY,
        }
        try:
            resp = self.session.get(GEOCODE_URL, params=params, timeout=10)
            resp.raise_for_status()
            items = resp.json().get("result", {}).get("items", [])
            if items:
                return (items[0].get("address") or {}).get("name", "")
        except Exception as exc:
            log.debug("Reverse geocode failed (%s, %s): %s", lat, lon, exc)
        return ""

    def _collect_ids(self) -> list[str]:
        """Run all search queries and return a deduplicated list of item IDs."""
        seen: set[str] = set()
        ordered: list[str] = []

        queries = list(SEARCH_QUERIES)
        for district in DISTRICTS:
            queries.append(f"парковка {district}")

        for query in queries:
            log.info("Searching: %r", query)
            for page in range(1, cfg.MAX_PAGES + 1):
                try:
                    data = self._fetch_search_page(query, page)
                except requests.HTTPError as exc:
                    log.warning("Search error query=%r page=%d: %s", query, page, exc)
                    break

                items = data.get("result", {}).get("items", [])
                if not items:
                    break

                for item in items:
                    item_id = str(item.get("id", ""))
                    if item_id and item_id not in seen:
                        seen.add(item_id)
                        ordered.append(item_id)

                total = data.get("result", {}).get("total", 0)
                if page * 10 >= total:
                    break

        log.info("Collected %d unique IDs.", len(ordered))
        return ordered

    def collect_all(self) -> list[dict]:
        """Collect IDs via search, fetch full data via byid, enrich missing addresses."""
        # Step 1: collect IDs
        all_ids = self._collect_ids()
        if not all_ids:
            return []

        # Step 2: fetch full data in batches of 50
        all_items: list[dict] = []
        batch_size = 50
        total_batches = (len(all_ids) + batch_size - 1) // batch_size
        for i in range(0, len(all_ids), batch_size):
            batch = all_ids[i: i + batch_size]
            batch_num = i // batch_size + 1
            log.info("byid batch %d/%d (%d IDs)", batch_num, total_batches, len(batch))
            try:
                items = self._fetch_byid_batch(batch)
                all_items.extend(items)
            except requests.HTTPError as exc:
                log.warning("byid batch %d failed: %s", batch_num, exc)

        log.info("Fetched full data for %d items.", len(all_items))

        # Step 3: reverse geocode items missing an address
        missing_addr = [
            item for item in all_items
            if not (item.get("address") or {}).get("name")
            and (item.get("point") or {}).get("lat")
        ]
        log.info(
            "Reverse geocoding %d items with missing address (of %d total)...",
            len(missing_addr), len(all_items)
        )
        for item in missing_addr:
            point = item["point"]
            addr_str = self._reverse_geocode(point["lat"], point["lon"])
            if addr_str:
                if "address" not in item or item["address"] is None:
                    item["address"] = {}
                item["address"]["name"] = addr_str

        filled = sum(
            1 for item in missing_addr
            if (item.get("address") or {}).get("name")
        )
        log.info("Reverse geocode filled %d/%d missing addresses.", filled, len(missing_addr))

        return all_items
