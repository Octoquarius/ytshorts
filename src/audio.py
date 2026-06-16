"""Aşama 2 (Adım 6) — Sesleri üret (Fal AI · mmaudio-v2).

Üretilen video klibi + Sound prompt'undan ASMR sesi üretir ve sesi videoya
gömer. Asenkron akış: queue.fal.run → request_id → poll → result URL.

NOT: Fal endpoint/parametreleri değişebilir; sabitleri doğrula.
"""
from __future__ import annotations

import time

import requests

import config

MODEL_ID = "fal-ai/mmaudio-v2"
QUEUE_BASE = "https://queue.fal.run"


def _headers() -> dict:
    key = config.FAL_API_KEY
    if not key:
        raise RuntimeError("FAL_API_KEY eksik (.env).")
    return {"Authorization": f"Key {key}", "Content-Type": "application/json"}


def submit(video_url: str, sound_prompt: str) -> dict:
    """mmaudio işini kuyruğa gönderir; submit cevabını (status/response URL) döndürür."""
    payload = {"video_url": video_url, "prompt": sound_prompt}
    resp = requests.post(
        f"{QUEUE_BASE}/{MODEL_ID}", json=payload, headers=_headers(), timeout=60
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("request_id"):
        raise RuntimeError(f"Fal request_id alınamadı: {resp.text[:300]}")
    return data


def poll(submit_data: dict) -> str:
    """İş tamamlanana kadar bekler; sesli video URL'sini döndürür.

    URL'leri submit cevabından alır (alt-yollu modellerde elle kurmak hataya açık).
    """
    request_id = submit_data["request_id"]
    status_url = submit_data.get("status_url") or (
        f"{QUEUE_BASE}/{MODEL_ID}/requests/{request_id}/status"
    )
    result_url = submit_data.get("response_url") or (
        f"{QUEUE_BASE}/{MODEL_ID}/requests/{request_id}"
    )
    deadline = time.monotonic() + config.POLL_TIMEOUT

    while time.monotonic() < deadline:
        resp = requests.get(status_url, headers=_headers(), timeout=60)
        resp.raise_for_status()
        status = (resp.json().get("status") or "").upper()

        if status == "COMPLETED":
            result = requests.get(result_url, headers=_headers(), timeout=60)
            result.raise_for_status()
            data = result.json()
            video = data.get("video") or {}
            url = video.get("url") if isinstance(video, dict) else None
            if url:
                return url
            raise RuntimeError(f"mmaudio tamamlandı ama URL yok: {data}")
        if status in ("ERROR", "FAILED"):
            raise RuntimeError(f"mmaudio başarısız: {resp.text[:300]}")

        time.sleep(config.POLL_INTERVAL)

    raise TimeoutError(f"mmaudio zaman aşımı (request_id={request_id}).")


def add_audio(video_url: str, sound_prompt: str) -> str:
    """Tek klip için gönder + poll: sesli video URL döndürür."""
    return poll(submit(video_url, sound_prompt))


def add_audio_to_clips(video_urls: list[str], sound_prompt: str) -> list[str]:
    """Tüm kliplere ASMR sesi ekler, sesli video URL listesi döndürür."""
    out = []
    for i, url in enumerate(video_urls, 1):
        print(f"[audio] Klip {i}/{len(video_urls)} seslendiriliyor...")
        out.append(add_audio(url, sound_prompt))
    return out
