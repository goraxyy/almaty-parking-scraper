"""Main entry point for the Almaty Parking Scraper.

Usage:
    python scraper.py
"""

import logging
import sys

from config import cfg
from dgis_client import DGisClient
from transformer import transform
from deduplicator import deduplicate
from sheets_client import SheetsClient

logging.basicConfig(
    level=getattr(logging, cfg.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scraper")


def main():
    log.info("=== Almaty Parking Scraper ===")
    log.info("Settings: MAX_PAGES=%d, RPS=%.1f", cfg.MAX_PAGES, cfg.REQUESTS_PER_SECOND)

    # Step 1: Collect raw data from 2GIS
    client = DGisClient()
    raw_items = client.collect_all()

    if not raw_items:
        log.error("No items collected. Check your DGIS_API_KEY and network connection.")
        sys.exit(1)

    # Step 2: Transform to clean records
    records = [transform(item) for item in raw_items]
    log.info("Transformed %d records.", len(records))

    # Step 3: Deduplicate
    records = deduplicate(records)
    log.info("After deduplication: %d unique records.", len(records))

    # Step 4: Filter out garbage rows (no name AND no address)
    records = [r for r in records if r.get("название") != "н/д" or r.get("адрес") != "н/д"]
    log.info("After garbage filter: %d records.", len(records))

    # Step 5: Enrich org phone numbers (1 API call per record with an org_id)
    org_phone_cache: dict[str, str] = {}
    enriched = 0
    for r in records:
        org_id = r.get("_org_id", "")
        if not org_id:
            r["телефон"] = "н/д"
            continue
        if org_id not in org_phone_cache:
            org_phone_cache[org_id] = client.fetch_org_phone(org_id)
        phone = org_phone_cache[org_id]
        r["телефон"] = phone if phone else "н/д"
        if phone:
            enriched += 1
    log.info("Org phone enrichment: %d/%d records filled.", enriched, len(records))

    # Step 6: Sort by district then name
    records.sort(key=lambda r: (r.get("район", ""), r.get("название", "")))

    # Step 7: Write to Google Sheets
    sheets = SheetsClient()
    sheets.write(records)

    print("\n" + "=" * 60)
    print(f"  Done!  {len(records)} parking lots written.")
    print(f"  Sheet: {sheets.url}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
