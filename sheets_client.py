"""Google Sheets writer — OAuth 2.0 Desktop App flow (no service account key)."""

import logging
import os

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from config import cfg
from transformer import HEADERS

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
TOKEN_FILE = "token.json"


def _get_credentials() -> Credentials:
    """Return valid credentials, refreshing or running the browser flow as needed."""
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
        log.info(
            "Sheet created: https://docs.google.com/spreadsheets/d/%s", sheet_id
        )
        # Make viewable by anyone with the link
        self.drive.permissions().create(
            fileId=sheet_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()
        return sheet_id

    def _ensure_tab(self):
        meta = (
            self.sheets.spreadsheets()
            .get(spreadsheetId=self.sheet_id)
            .execute()
        )
        existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
        if cfg.SHEET_NAME not in existing:
            self.sheets.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={
                    "requests": [
                        {"addSheet": {"properties": {"title": cfg.SHEET_NAME}}}
                    ]
                },
            ).execute()

    def write(self, records: list[dict]):
        """Clear the sheet tab and write header + all records."""
        self._ensure_tab()
        range_name = f"{cfg.SHEET_NAME}!A1"

        self.sheets.spreadsheets().values().clear(
            spreadsheetId=self.sheet_id, range=range_name
        ).execute()

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
