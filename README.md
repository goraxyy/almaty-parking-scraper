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
pip3 install -r requirements.txt
```

### 3. Google Cloud credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project
2. Enable **Google Sheets API** and **Google Drive API**
3. Go to **APIs & Services → Credentials** → create **OAuth 2.0 credentials** (Desktop App) → download the JSON
4. Save it as `oauth_credentials.json` in the project root

> On the **first run**, a browser window will open for OAuth consent. After you approve, a `token.json` is saved locally and reused on subsequent runs. Both files are already listed in `.gitignore` — never commit them.

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your keys. All variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `DGIS_API_KEY` | ✅ | — | 2GIS API key — get one free at [dev.2gis.com](https://dev.2gis.com) |
| `YANDEX_API_KEY` | ✅ | — | Yandex Geocoder key — free, 1000 req/day at [developer.tech.yandex.com](https://developer.tech.yandex.com) |
| `GOOGLE_OAUTH_JSON` | ✅ | `oauth_credentials.json` | Path to the OAuth credentials JSON downloaded in Step 3 |
| `SHEET_ID` | ❌ | *(blank)* | Existing Google Sheet ID to reuse; leave blank to auto-create a new sheet |
| `SHEET_NAME` | ❌ | `Parking Almaty` | Tab name inside the Google Sheet |
| `MAX_PAGES` | ❌ | `5` | Max pages fetched per search query (10 results/page). Free 2GIS keys support up to 5; production keys can be set to 20+ |
| `REQUESTS_PER_SECOND` | ❌ | `2` | Rate limit for 2GIS API requests |
| `LOG_LEVEL` | ❌ | `INFO` | Logging verbosity: `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |

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
