# Design Decisions

## Data Source: 2GIS Catalog API

**Chosen:** 2GIS Catalog API (`catalog.api.2gis.com/3.0/items`)

| Alternative | Pros | Cons |
|---|---|---|
| **2GIS API** ✓ | Best coverage of Almaty; structured fields (schedule, rubrics, capacity); free tier | Page cap on demo key (~500 results/query); some fields sparse |
| OpenStreetMap (Overpass API) | Fully open; no key needed | Very sparse parking data for Almaty; no structured attributes |
| Google Places API | Global coverage; rich attributes | Paid above low quota; worse CIS coverage than 2GIS |
| Manual scraping of 2gis.kz | No API limit | Fragile; against ToS; JS-heavy page |

**Why 2GIS:** It is the dominant mapping platform in Kazakhstan and has the most complete parking inventory for Almaty. The structured API avoids HTML scraping fragility.

## Coverage: Multi-Query Strategy

**Chosen:** 15 queries (7 keyword + 8 district-scoped) with ID-based deduplication.

| Alternative | Pros | Cons |
|---|---|---|
| **Multi-query** ✓ | Maximises recall; surfaces entries only tagged under one term | More API calls; slower |
| Single query `парковка` | Simple | Misses entries labelled `стоянка`, `паркинг`, etc. |
| Bounding-box scan | Covers every object regardless of name | 2GIS free tier does not expose a bbox-only endpoint |

**Why multi-query:** A single query misses ~20–30% of listings that use alternative Russian/English terms or are tagged at district level only.

## District Enrichment: Polygon Fallback

**Chosen:** 2GIS address component first; if empty, point-in-polygon lookup against hardcoded Almaty district boundaries using `shapely`.

| Alternative | Pros | Cons |
|---|---|---|
| **Polygon lookup** ✓ | Offline; no extra API calls; fills ~90% of blank district fields | Approximate boundaries; edge cases near district borders |
| 2GIS reverse-geocode API | Exact official district | 1 extra API call per record (~350 extra calls, slow) |
| Leave blank | No dependency | ~60% of records missing район |

**Why polygon:** Zero cost, no rate-limit risk, and accurate enough for district-level reporting.

## Missing Data: н/д Marker

**Chosen:** All fields that cannot be filled show `н/д` (not available).

The 2GIS API does not require listings to include tariff, capacity, schedule, or organisation. Rather than leaving blank cells (which look like scraper errors), `н/д` explicitly signals that the data was queried but not present in the source. Columns with no realistic fill path (телефон, сайт) were removed entirely rather than showing a column of `н/д`.

## Output: Google Sheets

**Chosen:** Google Sheets via the Sheets API v4 (service account auth).

| Alternative | Pros | Cons |
|---|---|---|
| **Google Sheets** ✓ | Shareable URL; no setup for reviewer; familiar UI | Requires Google Cloud service account |
| CSV file | Simplest | Requires separate file sharing |
| SQLite | Queryable | Reviewer needs DB tooling |
| Airtable | Nice UI | Paid above 1 000 rows; separate account |

**Why Sheets:** The assignment asks for a shareable result. A Google Sheets link works for any reviewer instantly.

## Deduplication Strategy

**Chosen:** Deduplicate by 2GIS object `id` at collection time, then by normalised `(name, address)` pair in `deduplicator.py`.

Two-stage deduplication is needed because the multi-query strategy intentionally requests the same geographic area with different keywords — the same parking lot often appears in multiple query results. The `id` check is O(1) and handles exact duplicates; the name+address normalisation handles cases where the same physical lot has two slightly different 2GIS listings.
