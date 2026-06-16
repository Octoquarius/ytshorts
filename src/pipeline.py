"""Ana akış — tüm hesaplar üzerinde döngü.

Her gün 5 hesabın HER BİRİ için ayrı/benzersiz bir video üretir (her hesap kendi
temasından farklı bir fikir üretir → aynı video tekrarlanmaz). Varsayılan modda
video hazırlanır ve DURUR; yükleme için kullanıcı onayı beklenir.

Kullanım:
  python -m src.pipeline                 # tüm hesaplar için video hazırla (onay bekler)
  python -m src.pipeline --account account1
  python -m src.pipeline --upload account1 <manifest.json>   # onay sonrası yükle
  python -m src.pipeline --auto-upload   # (dikkat) onaysız tam otomatik
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import date
from pathlib import Path

import config
from src import audio, compose, ideate, notify, prompts, sheets, video


def prepare_account(account: config.Account) -> dict:
    """Bir hesap için Aşama 1–3'ü çalıştırır; manifest (onay kartı) döndürür.

    Yükleme YAPMAZ — manifest diske yazılır, onay adımı çağırana bırakılır.
    """
    print(f"\n=== [{account.id}] {account.name} — tema: {account.theme} ===")

    # Aşama 1 — Fikir (hesabın temasına göre, geçmişe karşı dedupe).
    prior = sheets.used_ideas(account.sheet_tab)
    idea = ideate.generate_unique_idea(account.theme, prior)
    print(f"[idea] {idea}")
    plan = ideate.expand_to_plan(idea, account.theme)

    row_id = uuid.uuid4().hex[:8]
    row_number = sheets.append_row(
        account.sheet_tab, row_id, account.name, plan["Idea"], plan["Caption"],
        plan["Environment"], plan["Sound"], production="In Progress",
    )

    # Aşama 2 — 3 sahne promptu → video → ses.
    scene_prompts = prompts.generate_scene_prompts(
        plan["Idea"], plan["Environment"], plan["Sound"]
    )
    clip_urls = video.generate_clips(scene_prompts)
    voiced_urls = audio.add_audio_to_clips(clip_urls, plan["Sound"])

    # Aşama 3 — Birleştir + indir.
    out_path = account.output_dir / f"{date.today().isoformat()}_{row_id}.mp4"
    final_path = compose.compose_and_download(voiced_urls, out_path)

    sheets.update_status(
        account.sheet_tab, row_number,
        production="Pending Approval", final_output=str(final_path),
    )

    manifest = {
        "account_id": account.id,
        "account_name": account.name,
        "sheet_tab": account.sheet_tab,
        "row_number": row_number,
        "title": plan["Idea"],
        "description": plan["Caption"],
        "caption": plan["Caption"],
        "video_path": str(final_path),
    }
    manifest_path = final_path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"[ready] Video hazır: {final_path}")
    print(f"[ready] Manifest: {manifest_path}")
    return manifest


def approve_and_upload(manifest: dict) -> str:
    """Onay sonrası: YouTube yükleme + Sheets güncelleme + e-posta."""
    account = config.get_account(manifest["account_id"])
    video_path = Path(manifest["video_path"])
    if not video_path.exists():
        raise RuntimeError(f"Video bulunamadı: {video_path}")

    url = youtube_upload(account, video_path, manifest)
    sheets.update_status(
        manifest["sheet_tab"], manifest["row_number"],
        production="Done", youtube_url=url,
    )
    notify.notify_published(manifest["account_name"], manifest["title"], url)
    print(f"[done] Yayında: {url}")
    return url


def youtube_upload(account: config.Account, video_path: Path, manifest: dict) -> str:
    from src import youtube  # gecikmeli import: yükleme yapılmadıkça gerekmez
    return youtube.upload(
        account, video_path, manifest["title"], manifest["description"],
        manifest["caption"],
    )


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in ("e", "evet", "y", "yes")
    except EOFError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI ASMR YouTube Shorts fabrikası")
    parser.add_argument("--account", help="Sadece bu hesap için çalıştır")
    parser.add_argument(
        "--upload", nargs=2, metavar=("ACCOUNT", "MANIFEST"),
        help="Onay sonrası manifest'ten yükleme yap",
    )
    parser.add_argument(
        "--auto-upload", action="store_true",
        help="Onaysız tam otomatik yükleme (dikkatli kullan)",
    )
    args = parser.parse_args(argv)

    # Yalnızca yükleme modu.
    if args.upload:
        _, manifest_path = args.upload
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        approve_and_upload(manifest)
        return 0

    accounts = config.load_accounts()
    if args.account:
        accounts = [a for a in accounts if a.id == args.account]
        if not accounts:
            print(f"Hesap bulunamadı: {args.account}", file=sys.stderr)
            return 1

    manifests = []
    for account in accounts:
        try:
            manifests.append(prepare_account(account))
        except Exception as exc:  # bir hesabın hatası diğerlerini durdurmasın
            print(f"[hata:{account.id}] {exc}", file=sys.stderr)

    # Onay adımı.
    print("\n================ ONAY ADIMI ================")
    for m in manifests:
        print(f"\n• {m['account_name']}")
        print(f"  Başlık: {m['title']}")
        print(f"  Açıklama/Hashtag: {m['description']}")
        print(f"  Video: {m['video_path']}")

        if args.auto_upload:
            approve_and_upload(m)
        elif _confirm("  Bu videoyu YouTube'a yükleyeyim mi? (evet/hayır): "):
            approve_and_upload(m)
        else:
            print("  Atlandı — durum 'Pending Approval' olarak kaldı.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
