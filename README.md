# almaty-parking-scraper

Scrapes all parking lots in Almaty from the 2GIS Catalog API and writes a structured table to Google Sheets. Covers all 8 districts via 15 search queries, deduplicates by object ID, and reverse-geocodes coordinates via Yandex Geocoder (cached in `geocache.json`).

## What it does

1. **Collects IDs** — searches 2GIS for `парковка`, `стоянка`, `паркинг` + 8 district-scoped variants
2. **Fetches full data** — batches of 50 via `byid` endpoint (name, coordinates, schedule, capacity, org)
3. **Reverse-geocodes** — Yandex Geocoder for street addresses; results cached in `geocache.json`
4. **Writes to Google Sheets** — creates the sheet automatically if `SHEET_ID` is blank

## Output columns

`ID` · `Название` · `Адрес` · `Координаты` · `Ссылка на 2ГИС` · `Платная?` · `Тариф` · `Мест (всего)` · `Тип` · `Объект / организация` · `Часы работы` · `Район` · `Дата сбора`

## Setup

### 1. Clone

```bash
git clone https://github.com/goraxyy/almaty-parking-scraper.git
cd almaty-parking-scraper
```

### 2. Install dependencies

```bash
pip3 install requests python-dotenv numpy shapely cryptography requests-oauthlib google-auth-oauthlib google-api-python-client
```

> All packages in one command — avoids the slow `requirements.txt` resolver.

### 3. Keys

| Key | Where to get it |
|---|---|
| `DGIS_API_KEY` | [dev.2gis.com](https://dev.2gis.com) — free, create an app |
| `YANDEX_API_KEY` | [developer.tech.yandex.com](https://developer.tech.yandex.com) — free, 1000 req/day |
| `GOOGLE_OAUTH_JSON` | Google Cloud Console — OAuth 2.0 Desktop App credentials JSON |

**Google Sheets setup:**
1. [Google Cloud Console](https://console.cloud.google.com/) — create a project
2. Enable **Google Sheets API** and **Google Drive API**
3. Create **OAuth 2.0 credentials** (Desktop App) → download JSON
4. Save as `oauth_credentials.json` in the project root

### 4. Configure

```bash
cp .env.example .env
```

Minimum required fields in `.env`:

```env
DGIS_API_KEY=your_2gis_key
YANDEX_API_KEY=your_yandex_key
GOOGLE_OAUTH_JSON=oauth_credentials.json
```

Leave `SHEET_ID` blank to auto-create a new Google Sheet on first run.

### 5. Run

```bash
python3 scraper.py
```

First run: ~2–3 min (geocoding all coordinates). Re-runs: ~30 sec (cache hits).

To re-geocode from scratch:

```bash
rm geocache.json && python3 scraper.py
```

## Requirements

- Python 3.9+
- See `requirements.txt` for full package list
