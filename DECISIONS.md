# Engineering Decisions

Decisions are listed chronologically. Each entry includes alternatives considered, trade-offs, and approximate time spent.

---

## 1. Data Source — 2GIS Catalog API
**~1 h** · Initial commit (Jun 12)

| Option | Pros | Cons |
|---|---|---|
| **2GIS API** ✓ | Best Almaty coverage; structured fields (schedule, capacity, rubrics); free tier | Demo key caps at ~500 results/query |
| OpenStreetMap (Overpass) | Fully open; no key | Very sparse parking data for Almaty |
| Google Places API | Global; rich attributes | Paid above low quota; worse CIS coverage |
| Manual scraping of 2gis.kz | No API limit | Fragile; ToS violation; JS-heavy |

2GIS is the dominant mapping platform in Kazakhstan. It has the most complete parking inventory and avoids HTML scraping fragility.

---

## 2. Google Sheets Auth — OAuth 2.0 over Service Account
**~2 h** · Jun 12 (two failed attempts before working flow)

| Option | Pros | Cons |
|---|---|---|
| **OAuth 2.0 desktop flow** ✓ | Works with personal Google account; no org domain needed | Browser prompt on first run; token must be refreshed |
| Service account | Fully headless; no browser needed | Requires G Suite / Workspace domain to share sheets with SA email |

Service account was tried first but failed — sharing a sheet with a service account email is blocked on personal Google accounts without Workspace. Switched to OAuth desktop flow.

---

## 3. 2GIS region_id vs city_id
**~15 min** · Jun 13

The initial query used `city_id` which returned 0 results. 2GIS Catalog API uses `region_id=67` for Almaty. One-line fix, but required reading API docs carefully.

---

## 4. Multi-Query Coverage Strategy
**~30 min** · Jun 13 (initial commit included this)

| Option | Pros | Cons |
|---|---|---|
| **15 queries (7 keyword + 8 district-scoped)** ✓ | Maximises recall; surfaces district-only entries | More API calls |
| Single query `парковка` | Simple | Misses ~20–30% labelled `стоянка`, `паркинг`, etc. |
| Bounding-box scan | Complete coverage regardless of name | 2GIS free tier has no bbox-only endpoint |

A single keyword misses listings that use alternative Russian/English terms or are only tagged at district level.

---

## 5. Address Column — Three-Stage Fallback
**~2 h** · Jun 13 (three separate commits)

Problem: `address.name` from the 2GIS search endpoint was empty for most parking lots.

**Attempts in order:**
1. Request `address.name` and `address.components` sub-fields explicitly → still empty (2GIS free key doesn't return address for parking category).
2. Build address from `address.components` array → field absent entirely.
3. **Switched to two-step search→byid** and added reverse geocoding on coordinates.

| Geocoder | Pros | Cons |
|---|---|---|
| 2GIS reverse geocode | Same ecosystem | Not available on free API key |
| **Nominatim (OSM)** (interim) | Free; no key | 1 req/s policy; ~5 min first run; lower RU/KZ quality |
| **Yandex Geocoder** ✓ (current) | Best RU/KZ address quality; faster; 1 000 req/day free | Requires Yandex API key |

Nominatim was added first to unblock the pipeline. Replaced by Yandex on Jun 16 once a key was obtained.

---

## 6. Geocache — Skip Re-Geocoding on Re-Runs
**~20 min** · Jun 13

`geocache.py` persists `{lat,lon} → address` pairs in `geocache.json`. Re-runs skip API calls for already-resolved coordinates. This reduced re-run time from ~5 min to ~30 s and avoids burning the Yandex daily quota on unchanged data.

---

## 7. District Enrichment — Polygon Fallback
**~1 h** · Jun 13

| Option | Pros | Cons |
|---|---|---|
| **Point-in-polygon (shapely)** ✓ | Offline; no extra API calls; fills ~90% of blank district fields | Approximate boundaries; edge cases near borders |
| 2GIS reverse-geocode district field | Exact official value | ~350 extra API calls; rate-limit risk |
| Leave blank | No dependency | ~60% of records missing район |

District is derived from 2GIS `address.components` first; shapely polygon lookup is the fallback for the majority that lack it.

---

## 8. Deduplication — Two-Stage
**~30 min** · Jun 13

Multi-query strategy intentionally overlaps coverage, so deduplication is mandatory.

- **Stage 1:** 2GIS object `id` check at collection time (O(1)) — eliminates exact duplicates.
- **Stage 2:** Normalised `(name, address)` pair in `deduplicator.py` — catches the same physical lot with two slightly different listings.

---

## 9. Dropped Columns — Телефон & Сайт
**~10 min** · Jun 13

2GIS does not return contact data (phone, website) for parking category objects — only for businesses like restaurants. Both columns were 100% `н/д`. Removed entirely rather than keeping empty columns.

---

## 10. Missing Data Marker — н/д
**~5 min** · Jun 13

Fields that cannot be filled show `н/д` (not available) rather than a blank cell. Blank looks like a scraper bug; `н/д` explicitly signals the data was queried and not found in the source.

---

## 11. Google Sheets Formatting — Individual batchUpdate Requests
**~45 min** · Jun 13 (three bug-fix commits)

Sending all formatting requests in a single `batchUpdate` call caused a `500` error from the Sheets API when any one sub-request was invalid (e.g., `addBanding` on a sheet that already had banding). Fixed by:
1. Removing existing banding before applying new banding.
2. Splitting formatting into individual `batchUpdate` calls so one failure doesn't abort the rest.

---

## 12. Python 3.9 Compatibility
**~20 min** · Jun 16

Code used `X | Y` union types and built-in generics (`list[str]`, `dict[str, int]`) introduced in Python 3.10. Replaced with `typing` imports (`Union`, `List`, `Dict`, `Optional`) for compatibility with the system Python 3.9.
