# Almaty Parking Scraper

Collects parking lot data across all 8 Almaty districts from the 2GIS Catalog API and writes a structured table to Google Sheets.

## Quick Start (5 minutes)

### 1. Clone and install

```bash
git clone https://github.com/goraxyy/almaty-parking-scraper.git
cd almaty-parking-scraper
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Get API keys

**2GIS key** — register at [https://dev.2gis.com](https://dev.2gis.com), create an app, copy the Catalog API key.

**Google Sheets credentials**:
1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create a project
2. Enable **Google Sheets API** and **Google Drive API**
3. Create a **Service Account** → download the JSON key file
4. Save it as `credentials.json` in the project root

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```env
DGIS_API_KEY=your_2gis_key_here
GOOGLE_CREDENTIALS_PATH=credentials.json
```

### 4. Run

```bash
python3 scraper.py
```

Output:
```
=== Almaty Parking Scraper ===
...
Done!  353 parking lots written.
Sheet: https://docs.google.com/spreadsheets/d/...
```

The Google Sheet is created automatically and shared publicly (view-only).

## Output Columns

| Column | Description | Filled by |
|---|---|---|
| ID | 2GIS internal object ID | API |
| Название | Parking name | API |
| Адрес | Street address from 2GIS | API |
| Координаты | lat, lon | API |
| Ссылка на 2ГИС | Direct link to listing | API / constructed |
| Платная? | Платная / Бесплатная / н/д | Inferred from attributes + name |
| Тариф | Price text if listed | API attributes |
| Мест (всего) | Capacity if listed | API |
| Тип | Городская / ТРЦ / БЦ / Подземная / Частная | Inferred from name + rubrics |
| Объект / организация | Parent building or org | API |
| Часы работы | Schedule or 24/7 | API |
| Район | Almaty district | API address component → polygon fallback |
| Дата сбора | UTC timestamp of scrape run | Generated |

`н/д` = data not available from 2GIS for this listing.

## Coverage Strategy

The scraper runs 15 search queries total:
- 7 keyword queries: `парковка`, `стоянка`, `паркинг`, `автостоянка`, `parking`, `подземная парковка`, `многоуровневая парковка`
- 8 district-scoped queries: `парковка <район>` for each Almaty district

Results are deduplicated by 2GIS object ID before writing.

## Requirements

- Python 3.9+
- 2GIS Catalog API key (free tier)
- Google Cloud service account with Sheets + Drive API enabled
