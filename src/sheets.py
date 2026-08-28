"""Stage 1/4 — Google Sheets read/write.

Each account has its own tab (`account.sheet_tab`). Column layout:
id | account | idea | caption | production | environment_prompt | sound_prompt | final_output | youtube_url

A single Google Cloud project + single OAuth (the Sheets API doesn't cause
quota issues).
"""
from __future__ import annotations

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
HEADER = [
    "id", "account", "idea", "caption", "production",
    "environment_prompt", "sound_prompt", "final_output", "youtube_url",
]


def _service():
    """Returns the Sheets API service via OAuth (stores the token on disk)."""
    creds = None
    token_path = config.SHEETS_TOKEN
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(config.SHEETS_CLIENT_SECRET), SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _ensure_tab(svc, tab: str) -> None:
    """Creates the tab if it doesn't exist — so the user doesn't have to create it manually."""
    meta = svc.spreadsheets().get(
        spreadsheetId=config.GOOGLE_SHEET_ID, fields="sheets.properties.title"
    ).execute()
    titles = {s["properties"]["title"] for s in meta.get("sheets", [])}
    if tab not in titles:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=config.GOOGLE_SHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": tab}}}]},
        ).execute()


def _ensure_header(svc, tab: str) -> None:
    """Creates the tab if needed and adds a header to its first row."""
    _ensure_tab(svc, tab)
    rng = f"{tab}!A1:I1"
    resp = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=config.GOOGLE_SHEET_ID, range=rng)
        .execute()
    )
    if not resp.get("values"):
        svc.spreadsheets().values().update(
            spreadsheetId=config.GOOGLE_SHEET_ID,
            range=rng,
            valueInputOption="RAW",
            body={"values": [HEADER]},
        ).execute()


def used_ideas(tab: str) -> list[str]:
    """Returns ideas previously used for this account (for dedupe)."""
    svc = _service()
    _ensure_header(svc, tab)
    resp = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=config.GOOGLE_SHEET_ID, range=f"{tab}!C2:C")
        .execute()
    )
    return [row[0] for row in resp.get("values", []) if row]


def append_row(tab: str, row_id: str, account: str, idea: str, caption: str,
               environment: str, sound: str, production: str = "In Progress") -> int:
    """Appends a new row; returns the number of the added row."""
    svc = _service()
    _ensure_header(svc, tab)
    values = [[row_id, account, idea, caption, production, environment, sound, "", ""]]
    result = svc.spreadsheets().values().append(
        spreadsheetId=config.GOOGLE_SHEET_ID,
        range=f"{tab}!A:I",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": values},
    ).execute()
    # 'Sheet1!A5:I5' -> 5
    updated_range = result.get("updates", {}).get("updatedRange", "")
    try:
        return int(updated_range.split("!")[1].split(":")[0].lstrip("ABCDEFGHIJ"))
    except (IndexError, ValueError):
        return -1


def update_status(tab: str, row_number: int, *, production: str | None = None,
                  final_output: str | None = None, youtube_url: str | None = None) -> None:
    """Updates the status/output/youtube fields on the given row."""
    svc = _service()
    updates = []
    if production is not None:
        updates.append((f"{tab}!E{row_number}", production))
    if final_output is not None:
        updates.append((f"{tab}!H{row_number}", final_output))
    if youtube_url is not None:
        updates.append((f"{tab}!I{row_number}", youtube_url))
    for rng, val in updates:
        svc.spreadsheets().values().update(
            spreadsheetId=config.GOOGLE_SHEET_ID,
            range=rng,
            valueInputOption="RAW",
            body={"values": [[val]]},
        ).execute()
