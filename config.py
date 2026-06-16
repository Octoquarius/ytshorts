"""Ortam değişkenleri + hesap ayarlarının tek noktadan yüklenmesi.

Tüm modüller anahtarları ve ayarları buradan okur; böylece `.env` ve
`accounts.json` tek yerde yorumlanır. Eksik kritik anahtarlar erken hata verir.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Windows konsolu (cp1254 vb.) Unicode'u yazdıramayıp çökmesin diye stdout/stderr'i
# UTF-8'e çevir. Python 3.7+ destekler; eski/uyumsuz akışlarda sessizce geç.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

# Proje kök dizini (bu dosyanın bulunduğu klasör)
ROOT = Path(__file__).resolve().parent

# .env'i yükle (varsa). Yoksa sessizce geçer; eksik anahtar erişimde patlar.
load_dotenv(ROOT / ".env")

# ── Dizinler ─────────────────────────────────────────────────────────
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
    """Kritik anahtarı döndürür; yoksa anlamlı hata fırlatır."""
    val = _get(key)
    if not val:
        raise RuntimeError(
            f"Gerekli ortam değişkeni eksik: {key}. "
            f".env dosyanı .env.example'a göre doldur."
        )
    return val


# ── API anahtarları (lazy: gerçekten kullanılınca require() çağrılır) ─
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")
WAVESPEED_API_KEY = _get("WAVESPEED_API_KEY")
FAL_API_KEY = _get("FAL_API_KEY")

# ── Model seçimleri ──────────────────────────────────────────────────
CLAUDE_IDEA_MODEL = _get("CLAUDE_IDEA_MODEL", "claude-haiku-4-5")
CLAUDE_PROMPT_MODEL = _get("CLAUDE_PROMPT_MODEL", "claude-opus-4-8")

# ── Google Sheets ────────────────────────────────────────────────────
GOOGLE_SHEET_ID = _get("GOOGLE_SHEET_ID")
SHEETS_CLIENT_SECRET = ROOT / _get(
    "SHEETS_CLIENT_SECRET", "credentials/sheets/client_secret.json"
)
SHEETS_TOKEN = ROOT / _get("SHEETS_TOKEN", "credentials/sheets/token.json")

# ── Gmail bildirim ───────────────────────────────────────────────────
GMAIL_ADDRESS = _get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = _get("GMAIL_APP_PASSWORD")
NOTIFY_TO = _get("NOTIFY_TO") or GMAIL_ADDRESS

# ── Poll ayarları ────────────────────────────────────────────────────
POLL_INTERVAL = int(_get("POLL_INTERVAL", "10"))
POLL_TIMEOUT = int(_get("POLL_TIMEOUT", "600"))


@dataclass(frozen=True)
class Account:
    """accounts.json'daki tek bir hesabın ayarları."""

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
    """accounts.json'ı Account nesnelerine çevirir."""
    if not ACCOUNTS_FILE.exists():
        raise RuntimeError(f"accounts.json bulunamadı: {ACCOUNTS_FILE}")
    data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    accounts = [Account(**item) for item in data]
    ids = [a.id for a in accounts]
    if len(ids) != len(set(ids)):
        raise RuntimeError("accounts.json içinde tekrar eden 'id' var.")
    return accounts


def get_account(account_id: str) -> Account:
    for acc in load_accounts():
        if acc.id == account_id:
            return acc
    raise RuntimeError(f"Hesap bulunamadı: {account_id}")
