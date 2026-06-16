"""Aşama 3 — Final Kurgu (Fal AI · ffmpeg-api/compose) + indirme.

3 × 10sn sesli klibi tek ~30sn videoda birleştirir, sonra lokale indirir.

NOT: Fal ffmpeg-api/compose şeması değişebilir; sabitleri doğrula.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import requests

import config

MODEL_ID = "fal-ai/ffmpeg-api/compose"
QUEUE_BASE = "https://queue.fal.run"

# Sosyal medya için hedef ses yüksekliği (YouTube ~ -14 LUFS).
LOUDNORM_TARGET = "I=-14:TP=-1.5:LRA=11"


def _ffmpeg_exe() -> str | None:
    """Lokal ffmpeg ikilisini bulur (imageio-ffmpeg paketi veya PATH)."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def _headers() -> dict:
    key = config.FAL_API_KEY
    if not key:
        raise RuntimeError("FAL_API_KEY eksik (.env).")
    return {"Authorization": f"Key {key}", "Content-Type": "application/json"}


def _build_compose_payload(video_urls: list[str], clip_seconds: float = 10.0) -> dict:
    """Ardışık klipleri uç uca ekleyen compose isteği oluşturur.

    Fal ffmpeg compose, timestamp/duration değerlerini MİLİSANİYE bekler. Sesi
    korumak için aynı kliplerden HEM video HEM audio track'i oluşturulur — yalnızca
    'video' track'i görüntüyü alır, sesi düşürür.
    """
    keyframes = []
    cursor_ms = 0.0
    duration_ms = clip_seconds * 1000.0
    for url in video_urls:
        keyframes.append({"url": url, "timestamp": cursor_ms, "duration": duration_ms})
        cursor_ms += duration_ms
    # Aynı keyframe listesi iki track için de kullanılır.
    return {
        "tracks": [
            {"id": "video", "type": "video", "keyframes": list(keyframes)},
            {"id": "audio", "type": "audio", "keyframes": list(keyframes)},
        ]
    }


def compose(video_urls: list[str], clip_seconds: float = 10.0) -> str:
    """Klipleri birleştirir; final video URL'sini döndürür."""
    payload = _build_compose_payload(video_urls, clip_seconds)
    resp = requests.post(
        f"{QUEUE_BASE}/{MODEL_ID}", json=payload, headers=_headers(), timeout=60
    )
    resp.raise_for_status()
    submit = resp.json()
    request_id = submit.get("request_id")
    if not request_id:
        raise RuntimeError(f"compose request_id alınamadı: {resp.text[:300]}")

    # Alt-yollu modellerde (fal-ai/ffmpeg-api/compose) status/result URL'leri
    # /compose içermez; en sağlamı submit cevabındaki URL'leri kullanmak.
    status_url = submit.get("status_url")
    result_url = submit.get("response_url")
    deadline = time.monotonic() + config.POLL_TIMEOUT

    while time.monotonic() < deadline:
        s = requests.get(status_url, headers=_headers(), timeout=60)
        s.raise_for_status()
        status = (s.json().get("status") or "").upper()

        if status == "COMPLETED":
            r = requests.get(result_url, headers=_headers(), timeout=60)
            r.raise_for_status()
            data = r.json()
            video = data.get("video_url") or (data.get("video") or {}).get("url")
            if video:
                return video
            raise RuntimeError(f"compose tamamlandı ama URL yok: {data}")
        if status in ("ERROR", "FAILED"):
            raise RuntimeError(f"compose başarısız: {s.text[:300]}")

        time.sleep(config.POLL_INTERVAL)

    raise TimeoutError(f"compose zaman aşımı (request_id={request_id}).")


def download(url: str, dest: Path) -> Path:
    """Final videoyu lokale indirir."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
    return dest


def normalize_audio(src: Path, dest: Path) -> Path:
    """ASMR sesini duyulur seviyeye getirir (ffmpeg loudnorm).

    ffmpeg yoksa veya hata olursa kaynağı olduğu gibi dest'e kopyalar (sessizce
    geçer — pipeline durmaz). Görüntü yeniden kodlanmaz (-c:v copy).
    """
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        print("[compose] ffmpeg yok — ses normalizasyonu atlanıyor.")
        if src != dest:
            shutil.copyfile(src, dest)
        return dest

    # Çıktıyı en uyumlu formata zorla: 48kHz stereo AAC + faststart.
    # (loudnorm tek başına 96kHz mono üretebiliyor; bazı oynatıcılar çalmıyor.)
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-af", f"loudnorm={LOUDNORM_TARGET}",
        "-ar", "48000", "-ac", "2",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(dest),
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"[compose] Ses normalize edildi -> {dest}")
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"[compose] Normalizasyon başarısız ({exc}); ham dosya kullanılıyor.")
        if src != dest:
            shutil.copyfile(src, dest)
    return dest


def compose_and_download(video_urls: list[str], dest: Path,
                         clip_seconds: float = 10.0, normalize: bool = True) -> Path:
    """Birleştir + indir (+ ses normalize): lokal .mp4 yolunu döndürür."""
    print("[compose] Klipler birleştiriliyor...")
    final_url = compose(video_urls, clip_seconds)

    if normalize:
        raw = dest.with_name(dest.stem + "_raw.mp4")
        print(f"[compose] İndiriliyor -> {raw}")
        download(final_url, raw)
        normalize_audio(raw, dest)
        raw.unlink(missing_ok=True)
        return dest

    print(f"[compose] İndiriliyor -> {dest}")
    return download(final_url, dest)
