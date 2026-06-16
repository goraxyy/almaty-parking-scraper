"""2GIS Catalog API client.

Strategy:
  Step 1 - Search queries collect item IDs (search endpoint returns minimal fields).
  Step 2 - byid in batches of 50 fetches full data (point, schedule, capacity, etc.).
  Step 3 - Reverse geocode via Yandex Geocoder for all items
           (2GIS free key does not return address fields).
           Results are cached in geocache.json — re-runs skip already-geocoded coords.

Docs: https://docs.2gis.com/en/api/search/places/overview
      https://yandex.com/dev/geocode/doc/en/request
"""

import logging
import time
from typing import Dict, List

import requests

from config import cfg
from geocache import GeoCache

log = logging.getLogger(__name__)

SEARCH_URL = "https://catalog.api.2gis.com/3.0/items"
BYID_URL = "https://catalog.api.2gis.com/3.0/items/byid"
YANDEX_GEOCODER_URL = "https://geocode-maps.yandex.ru/1.x/"
REGION_ID = "67"  # Almaty

_YANDEX_DELAY = 0.1  # Yandex free tier: 1000/day, no hard per-second limit; be polite

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

_BYID_FIELDS = (
    "items.id,items.name,items.full_name,"
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
        self._last_yandex_call = 0.0
        self._cache = GeoCache()

    def _throttle(self):
        elapsed = time.monotonic() - self._last_call
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)
        self._last_call = time.monotonic()

    def _throttle_yandex(self):
        elapsed = time.monotonic() - self._last_yandex_call
        if elapsed < _YANDEX_DELAY:
            time.sleep(_YANDEX_DELAY - elapsed)
        self._last_yandex_call = time.monotonic()

    def _fetch_search_page(self, query: str, page: int) -> dict:
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

    def _fetch_byid_batch(self, ids: List[str]) -> List[dict]:
        self._throttle()
        params = {
            "id": ",".join(ids),
            "fields": _BYID_FIELDS,
            "key": cfg.DGIS_API_KEY,
        }
        resp = self.session.get(BYID_URL, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("result", {}).get("items", [])

    def _reverse_geocode(self, lat: float, lon: float) -> str:
        """Return address from cache, or fetch from Yandex Geocoder and cache it.

        Yandex expects geocode=lon,lat (longitude first).
        Address is extracted from:
          response.GeoObjectCollection.featureMember[0]
            .GeoObject.metaDataProperty.GeocoderMetaData.text
        """
        cached = self._cache.get(lat, lon)
        if cached is not None:
            return cached

        self._throttle_yandex()
        addr_str = ""
        try:
            params = {
                "apikey": cfg.YANDEX_API_KEY,
                "geocode": f"{lon},{lat}",  # Yandex: lon,lat order
                "format": "json",
                "results": 1,
                "kind": "house",
            }
            resp = self.session.get(YANDEX_GEOCODER_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            members = (
                data.get("response", {})
                .get("GeoObjectCollection", {})
                .get("featureMember", [])
            )
            if members:
                addr_str = (
                    members[0]
                    .get("GeoObject", {})
                    .get("metaDataProperty", {})
                    .get("GeocoderMetaData", {})
                    .get("text", "")
                )
        except Exception as exc:
            log.debug("Yandex Geocoder failed (%s, %s): %s", lat, lon, exc)

        # Cache even empty results to avoid retrying failed coords
        self._cache.set(lat, lon, addr_str)
        return addr_str

    def _collect_ids(self) -> List[str]:
        seen = set()  # type: ignore
        ordered: List[str] = []
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

    def collect_all(self) -> List[dict]:
        # Step 1: IDs via search
        all_ids = self._collect_ids()
        if not all_ids:
            return []

        # Step 2: full data via byid in batches of 50
        all_items: List[dict] = []
        batch_size = 50
        total_batches = (len(all_ids) + batch_size - 1) // batch_size
        for i in range(0, len(all_ids), batch_size):
            batch = all_ids[i: i + batch_size]
            batch_num = i // batch_size + 1
            log.info("byid batch %d/%d (%d IDs)", batch_num, total_batches, len(batch))
            try:
                all_items.extend(self._fetch_byid_batch(batch))
            except requests.HTTPError as exc:
                log.warning("byid batch %d failed: %s", batch_num, exc)

        log.info("Fetched full data for %d items.", len(all_items))

        # Step 3: reverse geocode via Yandex Geocoder (cached)
        cache_hits = 0
        api_calls = 0
        filled = 0
        for item in all_items:
            point = item.get("point") or {}
            lat, lon = point.get("lat"), point.get("lon")
            if not lat or not lon:
                continue
            was_cached = self._cache.get(lat, lon) is not None
            addr_str = self._reverse_geocode(lat, lon)
            if was_cached:
                cache_hits += 1
            else:
                api_calls += 1
            if addr_str:
                item["address"] = {"name": addr_str}
                filled += 1

        log.info(
            "Geocoding done: %d filled | %d cache hits | %d Yandex API calls.",
            filled, cache_hits, api_calls,
        )
        self._cache.save()
        return all_items
