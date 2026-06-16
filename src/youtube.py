"""Aşama 4 (Adım 10) — YouTube'a yükleme (hesap bazlı OAuth).

Her hesabın kendi `credentials/<account>/client_secret.json` + `token.json`
çiftini kullanır. İlk çalıştırmada tarayıcıda her hesap için ayrı izin verilir.

⚠️ Yükleme yalnızca pipeline'daki onay adımından SONRA çağrılır.
"""
from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import Account

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _service(account: Account):
    """Hesaba özel YouTube servisini OAuth ile döndürür."""
    creds = None
    token_path = account.token_path
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not account.client_secret_path.exists():
                raise RuntimeError(
                    f"client_secret.json bulunamadı: {account.client_secret_path}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(account.client_secret_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _parse_tags(caption: str) -> list[str]:
    """Caption içindeki #hashtag'leri etiket listesine çevirir."""
    return [w.lstrip("#") for w in caption.split() if w.startswith("#")][:15]


def upload(account: Account, video_path: Path, title: str, description: str,
           caption: str) -> str:
    """Videoyu hesabın kanalına yükler; YouTube URL'sini döndürür."""
    svc = _service(account)
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": _parse_tags(caption),
            "categoryId": "24",  # Entertainment
        },
        "status": {
            "privacyStatus": account.privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
    request = svc.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[youtube:{account.id}] Yükleniyor %{int(status.progress() * 100)}")

    video_id = response["id"]
    return f"https://www.youtube.com/watch?v={video_id}"
