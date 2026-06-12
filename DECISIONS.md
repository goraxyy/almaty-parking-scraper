# Decisions & Time Spent

## Architectural Decisions

### 1. 2GIS Catalog API (not HTML scraping)
The 2GIS Places API returns structured JSON, which is far more reliable than HTML scraping. It exposes `rubric_id`, `schedule`, `attribute_groups`, and `org` fields that map cleanly to the required output columns. The tradeoff is the 50-result demo cap, mitigated by issuing multiple targeted search queries (see below).

### 2. Multi-query Coverage Strategy
A single query `"parking"` on a demo key returns only ~50 results. To approach full coverage the scraper issues **7 parallel search terms** (`парковка`, `стоянка`, `паркинг`, `автостоянка`, `parking`, `подземная парковка`, `многоуровневая парковка`) plus **district-scoped queries** for all 8 Almaty districts. Results are merged and deduplicated on `id` before writing. On a demo key this typically yields 200–400 unique lots.

### 3. Deduplication on 2GIS `id`
Every place in 2GIS has a stable numeric `id`. Using this as the dedup key is safer than fuzzy name/address matching, which fails on abbreviated or transliterated names.

### 4. Type Inference Heuristic
The API does not expose a "parking type" field directly. Type is inferred from:
- The `rubric` tags (e.g., `"подземная"` → `underground`).
- The `belongs_to` organisation name — presence of "ТРЦ"/"ТРЦ"/"Mall" → `mall`; "БЦ"/"бизнес" → `business_center`.
- Fall-through: `city` (standalone municipal lot) or `private`.

### 5. Google Sheets via Service Account
Service accounts require no OAuth browser flow, making the tool fully headless and CI-friendly. The sheet is auto-created on first run if no `SHEET_ID` is set.

### 6. Graceful Degradation
`MAX_PAGES` defaults to 5 (demo limit). Setting it to 20+ on a production key automatically increases coverage without code changes.

---

## Time Spent

| Task | Time |
|---|---|
| 2GIS API research & field mapping | 45 min |
| Core scraper + transformer | 60 min |
| Google Sheets integration | 30 min |
| Dedup + normalisation edge cases | 20 min |
| README & setup docs | 25 min |
| **Total** | **~3 h** |
