"""Single-point loading of environment variables + account settings.

All modules read keys and settings from here, so `.env` and `accounts.json`
are parsed in one place. Missing critical keys raise an error early.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Switch stdout/stderr to UTF-8 so the Windows console (cp1254 etc.) doesn't
# crash trying to print Unicode. Supported on Python 3.7+; silently skipped on
# older/incompatible streams.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

# Project root directory (the folder containing this file)
ROOT = Path(__file__).resolve().parent

# Load .env (if present). Skipped silently if missing; missing keys raise on access.
load_dotenv(ROOT / ".env")

# ── Directories ──────────────────────────────────────────────────────
OUTPUT_DIR = ROOT / "output"
LOGS_DIR = ROOT / "logs"
CREDENTIALS_DIR = ROOT / "credentials"
ACCOUNTS_FILE = ROOT / "accounts.json"

for _d in (OUTPUT_DIR, LOGS_DIR, CREDENTIALS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _get(key: str, default: str | None = None) -> str | None:
    val = os.getenv(key, default)
    return val.strip() if isinstance(val, str) else val


def require(key: str) -> str:
    """Returns the critical key; raises a meaningful error if missing."""
    val = _get(key)
    if not val:
        raise RuntimeError(
            f"Missing required environment variable: {key}. "
            f"Fill in your .env file based on .env.example."
        )
    return val


# ── API keys (lazy: require() is only called when actually used) ─────
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")
WAVESPEED_API_KEY = _get("WAVESPEED_API_KEY")
FAL_API_KEY = _get("FAL_API_KEY")

# ── Model selection ──────────────────────────────────────────────────
CLAUDE_IDEA_MODEL = _get("CLAUDE_IDEA_MODEL", "claude-haiku-4-5")
CLAUDE_PROMPT_MODEL = _get("CLAUDE_PROMPT_MODEL", "claude-opus-4-8")

# ── Google Sheets ────────────────────────────────────────────────────
GOOGLE_SHEET_ID = _get("GOOGLE_SHEET_ID")
SHEETS_CLIENT_SECRET = ROOT / _get(
    "SHEETS_CLIENT_SECRET", "credentials/sheets/client_secret.json"
)
SHEETS_TOKEN = ROOT / _get("SHEETS_TOKEN", "credentials/sheets/token.json")

# ── Gmail notification ───────────────────────────────────────────────
GMAIL_ADDRESS = _get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = _get("GMAIL_APP_PASSWORD")
NOTIFY_TO = _get("NOTIFY_TO") or GMAIL_ADDRESS

# ── Poll settings ────────────────────────────────────────────────────
POLL_INTERVAL = int(_get("POLL_INTERVAL", "10"))
POLL_TIMEOUT = int(_get("POLL_TIMEOUT", "600"))


@dataclass(frozen=True)
class Account:
    """Settings for a single account from accounts.json."""

    id: str
    name: str
    theme: str
    credentials_dir: str
    sheet_tab: str
    publish_time: str
    privacy_status: str = "public"

    @property
    def client_secret_path(self) -> Path:
        return ROOT / self.credentials_dir / "client_secret.json"

    @property
    def token_path(self) -> Path:
        return ROOT / self.credentials_dir / "token.json"

    @property
    def output_dir(self) -> Path:
        d = OUTPUT_DIR / self.id
        d.mkdir(parents=True, exist_ok=True)
        return d


def load_accounts() -> list[Account]:
    """Converts accounts.json into Account objects."""
    if not ACCOUNTS_FILE.exists():
        raise RuntimeError(f"accounts.json not found: {ACCOUNTS_FILE}")
    data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    accounts = [Account(**item) for item in data]
    ids = [a.id for a in accounts]
    if len(ids) != len(set(ids)):
        raise RuntimeError("accounts.json contains a duplicate 'id'.")
    return accounts


def get_account(account_id: str) -> Account:
    for acc in load_accounts():
        if acc.id == account_id:
            return acc
    raise RuntimeError(f"Account not found: {account_id}")
