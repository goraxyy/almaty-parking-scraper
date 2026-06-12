"""Google Sheets writer.

Creates a new spreadsheet if SHEET_ID is not set, otherwise
clears and rewrites the target tab.
"""

import logging
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

from config import cfg
from transformer import HEADERS

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsClient:
    def __init__(self):
        creds = service_account.Credentials.from_service_account_file(
            cfg.GOOGLE_SA_JSON, scopes=SCOPES
        )
        self.sheets = build("sheets", "v4", credentials=creds)
        self.drive = build("drive", "v3", credentials=creds)
        self.sheet_id = cfg.SHEET_ID or self._create_sheet()

    def _create_sheet(self) -> str:
        log.info("Creating new Google Sheet: %r", cfg.SHEET_NAME)
        body = {
            "properties": {"title": cfg.SHEET_NAME},
            "sheets": [{"properties": {"title": cfg.SHEET_NAME}}],
        }
        result = self.sheets.spreadsheets().create(body=body, fields="spreadsheetId").execute()
        sheet_id = result["spreadsheetId"]
        log.info("Sheet created: https://docs.google.com/spreadsheets/d/%s", sheet_id)

        # Make it viewable by anyone with the link
        self.drive.permissions().create(
            fileId=sheet_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()
        return sheet_id

    def _ensure_tab(self):
        """Create the named tab if it does not already exist."""
        meta = self.sheets.spreadsheets().get(spreadsheetId=self.sheet_id).execute()
        existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
        if cfg.SHEET_NAME not in existing:
            self.sheets.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": cfg.SHEET_NAME}}}]},
            ).execute()

    def write(self, records: list[dict]):
        """Clear the sheet tab and write all records with a header row."""
        self._ensure_tab()
        range_name = f"{cfg.SHEET_NAME}!A1"

        # Clear existing content
        self.sheets.spreadsheets().values().clear(
            spreadsheetId=self.sheet_id, range=range_name
        ).execute()

        # Build rows: header + data
        rows = [HEADERS]
        for rec in records:
            rows.append([str(rec.get(h, "")) for h in HEADERS])

        self.sheets.spreadsheets().values().update(
            spreadsheetId=self.sheet_id,
            range=range_name,
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

        log.info(
            "Written %d rows to sheet: https://docs.google.com/spreadsheets/d/%s",
            len(records),
            self.sheet_id,
        )
        return self.sheet_id

    @property
    def url(self) -> str:
        return f"https://docs.google.com/spreadsheets/d/{self.sheet_id}"
