# Almaty Parking Scraper

Collects structured data about parking lots in Almaty, Kazakhstan from the **2GIS Places API** and exports it to a **Google Sheets** document — deduplicated, clean, and ready in under 5 minutes.

---

## Quick Start (≤ 5 minutes)

### Prerequisites
- Python 3.9+
- A 2GIS API key (see below)
- A Google Cloud service account JSON (see below)

### 1. Clone & Install

```bash
git clone https://github.com/goraxyy/almaty-parking-scraper.git
cd almaty-parking-scraper
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your keys
```

### 3. Run

```bash
python scraper.py
```

The script will print progress and, when done, output the Google Sheet URL.

---

## Getting a 2GIS API Key (Free Demo)

1. Go to [https://dev.2gis.com](https://dev.2gis.com) and click **Sign Up** (or log in).
2. Create a new project — choose **"Places API"** (Catalog API).
3. A demo key is issued immediately. Copy it.
4. **Demo limits:** ~50 results per query (5 pages × 10 items). The scraper uses multiple search queries to maximise coverage even on demo keys.
5. Paste the key as `DGIS_API_KEY` in your `.env`.

> For production, apply for a commercial key on the same dashboard — quota increases to thousands of results.

---

## Setting Up Google Sheets API

### Step 1 — Create a Google Cloud Project
1. Go to [https://console.cloud.google.com](https://console.cloud.google.com).
2. Click the project dropdown → **New Project** → name it `parking-scraper` → **Create**.

### Step 2 — Enable the Sheets API
1. In the left menu: **APIs & Services → Library**.
2. Search for **"Google Sheets API"** → click it → **Enable**.
3. Also enable **"Google Drive API"** (needed to create/share the sheet).

### Step 3 — Create a Service Account
1. Go to **APIs & Services → Credentials**.
2. Click **"+ Create Credentials" → Service Account**.
3. Name it `parking-writer` → click **Done** (no roles needed for now).
4. Click the service account email → **Keys** tab → **Add Key → Create new key → JSON** → **Create**.
5. A `.json` file is downloaded. Rename it `service_account.json` and place it in the project root.

### Step 4 — Share the Sheet with the Service Account
After the first run the script auto-creates the sheet, but you need to share it:
1. Open the created Google Sheet.
2. Click **Share** → paste the service account email (looks like `parking-writer@your-project.iam.gserviceaccount.com`) → give **Editor** access.

> Alternatively, set `CREATE_SHEET=true` in `.env` and the script shares it automatically.

### Step 5 — Set Environment Variable
```
GOOGLE_SA_JSON=service_account.json
```

---

## Environment Variables

See `.env.example` for all options:

| Variable | Required | Default | Description |
|---|---|---|---|
| `DGIS_API_KEY` | ✅ | — | 2GIS Catalog/Places API key |
| `GOOGLE_SA_JSON` | ✅ | `service_account.json` | Path to GCP service account JSON |
| `SHEET_ID` | ❌ | auto-create | Existing Sheet ID to write to |
| `SHEET_NAME` | ❌ | `Parking Almaty` | Tab name inside the sheet |
| `MAX_PAGES` | ❌ | `5` | Max pages per query (10 results/page). Set higher for production keys |
| `REQUESTS_PER_SECOND` | ❌ | `2` | Rate limit (requests/sec) |
| `LOG_LEVEL` | ❌ | `INFO` | DEBUG for verbose output |

---

## Output Fields

Each row in the sheet contains:

| Field | Description |
|---|---|
| `id` | 2GIS internal object ID |
| `name` | Place name |
| `address` | Full street address |
| `lat` / `lon` | Coordinates |
| `dgis_url` | Direct link to place on 2GIS |
| `paid` | `Платная` / `Бесплатная` / `Unknown` |
| `tariff` | Tariff details (e.g., "200 ₸/hour") |
| `capacity` | Number of spaces |
| `type` | Inferred category (city / mall / business_center / private / underground) |
| `belongs_to` | Parent object (mall/building name if available) |
| `hours` | Opening hours |
| `phone` | Contact phone |
| `website` | Website if listed |
| `district` | City district |
| `scraped_at` | ISO timestamp of data collection |

---

## Project Structure

```
almaty-parking-scraper/
├── scraper.py          # Main entry point
├── dgis_client.py      # 2GIS API client
├── sheets_client.py    # Google Sheets writer
├── transformer.py      # Field extraction & normalisation
├── deduplicator.py     # Dedup logic
├── config.py           # Config & env loading
├── requirements.txt
├── .env.example
└── README.md
```

---

## Decisions & Time Spent

See [`DECISIONS.md`](DECISIONS.md).
