"""Google Sheets writer — OAuth 2.0 Desktop App flow (no service account key)."""

import logging
import os

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from config import cfg
from transformer import HEADERS, HEADER_LABELS

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
TOKEN_FILE = "token.json"


def _get_credentials() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                cfg.GOOGLE_OAUTH_JSON, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as fh:
            fh.write(creds.to_json())
    return creds


class SheetsClient:
    def __init__(self):
        creds = _get_credentials()
        self.sheets = build("sheets", "v4", credentials=creds)
        self.drive = build("drive", "v3", credentials=creds)
        self.sheet_id = cfg.SHEET_ID or self._create_sheet()

    def _create_sheet(self) -> str:
        log.info("Creating new Google Sheet: %r", cfg.SHEET_NAME)
        body = {
            "properties": {"title": cfg.SHEET_NAME},
            "sheets": [{"properties": {"title": cfg.SHEET_NAME}}],
        }
        result = (
            self.sheets.spreadsheets()
            .create(body=body, fields="spreadsheetId")
            .execute()
        )
        sheet_id = result["spreadsheetId"]
        log.info("Sheet created: https://docs.google.com/spreadsheets/d/%s", sheet_id)
        self.drive.permissions().create(
            fileId=sheet_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()
        return sheet_id

    def _ensure_tab(self) -> int:
        """Ensure the named tab exists; return its sheetId (integer)."""
        meta = (
            self.sheets.spreadsheets()
            .get(spreadsheetId=self.sheet_id)
            .execute()
        )
        for s in meta.get("sheets", []):
            if s["properties"]["title"] == cfg.SHEET_NAME:
                return s["properties"]["sheetId"]
        resp = self.sheets.spreadsheets().batchUpdate(
            spreadsheetId=self.sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": cfg.SHEET_NAME}}}]},
        ).execute()
        return resp["replies"][0]["addSheet"]["properties"]["sheetId"]

    def _remove_bandings(self, tab_id: int):
        """Delete any existing banded ranges on this tab (prevents 500 on re-run)."""
        meta = (
            self.sheets.spreadsheets()
            .get(spreadsheetId=self.sheet_id)
            .execute()
        )
        for s in meta.get("sheets", []):
            if s["properties"]["sheetId"] == tab_id:
                banded = s.get("bandedRanges", [])
                if banded:
                    requests = [
                        {"deleteBanding": {"bandedRangeId": b["bandedRangeId"]}}
                        for b in banded
                    ]
                    self.sheets.spreadsheets().batchUpdate(
                        spreadsheetId=self.sheet_id,
                        body={"requests": requests},
                    ).execute()
                break

    def _apply_formatting(self, tab_id: int, num_rows: int):
        """Apply header colours, freeze, auto-resize, alternating row shading."""
        # Must remove old banding first or Google returns 500 on addBanding
        self._remove_bandings(tab_id)

        num_cols = len(HEADERS)
        requests = [
            # 1. Freeze row 1
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": tab_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            # 2. Header row — dark navy background, white bold text
            {
                "repeatCell": {
                    "range": {
                        "sheetId": tab_id,
                        "startRowIndex": 0, "endRowIndex": 1,
                        "startColumnIndex": 0, "endColumnIndex": num_cols,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.13, "green": 0.29, "blue": 0.45},
                            "textFormat": {
                                "bold": True,
                                "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                                "fontSize": 10,
                            },
                            "verticalAlignment": "MIDDLE",
                            "horizontalAlignment": "CENTER",
                            "wrapStrategy": "CLIP",
                        }
                    },
                    "fields": "userEnteredFormat",
                }
            },
            # 3. Alternating row shading (white / light blue)
            {
                "addBanding": {
                    "bandedRange": {
                        "range": {
                            "sheetId": tab_id,
                            "startRowIndex": 1, "endRowIndex": num_rows + 1,
                            "startColumnIndex": 0, "endColumnIndex": num_cols,
                        },
                        "rowProperties": {
                            "firstBandColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                            "secondBandColor": {"red": 0.91, "green": 0.95, "blue": 0.99},
                        },
                    }
                }
            },
            # 4. Auto-resize all columns
            {
                "autoResizeDimensions": {
                    "dimensions": {
                        "sheetId": tab_id,
                        "dimension": "COLUMNS",
                        "startIndex": 0,
                        "endIndex": num_cols,
                    }
                }
            },
            # 5. Row height 22px
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": tab_id,
                        "dimension": "ROWS",
                        "startIndex": 0,
                        "endIndex": num_rows + 1,
                    },
                    "properties": {"pixelSize": 22},
                    "fields": "pixelSize",
                }
            },
            # 6. Data rows: vertically centred, font 9
            {
                "repeatCell": {
                    "range": {
                        "sheetId": tab_id,
                        "startRowIndex": 1, "endRowIndex": num_rows + 1,
                        "startColumnIndex": 0, "endColumnIndex": num_cols,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "verticalAlignment": "MIDDLE",
                            "textFormat": {"fontSize": 9},
                            "wrapStrategy": "CLIP",
                        }
                    },
                    "fields": "userEnteredFormat",
                }
            },
        ]
        self.sheets.spreadsheets().batchUpdate(
            spreadsheetId=self.sheet_id, body={"requests": requests}
        ).execute()

    def write(self, records: list[dict]):
        """Clear the sheet tab, write header + all records, then format."""
        tab_id = self._ensure_tab()
        range_name = f"{cfg.SHEET_NAME}!A1"

        self.sheets.spreadsheets().values().clear(
            spreadsheetId=self.sheet_id, range=range_name
        ).execute()

        rows = [HEADER_LABELS]
        for rec in records:
            rows.append([str(rec.get(h, "")) for h in HEADERS])

        self.sheets.spreadsheets().values().update(
            spreadsheetId=self.sheet_id,
            range=range_name,
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        self._apply_formatting(tab_id, len(records))

        log.info(
            "Written %d rows to sheet: https://docs.google.com/spreadsheets/d/%s",
            len(records),
            self.sheet_id,
        )
        return self.sheet_id

    @property
    def url(self) -> str:
        return f"https://docs.google.com/spreadsheets/d/{self.sheet_id}"
