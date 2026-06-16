"""Aşama 2 (Adım 5) — Video klipleri üret (Wavespeed AI · ByteDance Seedance).

Her sahne promptu için ayrı bir 9:16 / 10sn klip üretir. Asenkron akış:
gönder → request id → poll → result URL.

NOT: Wavespeed endpoint/parametreleri zamanla değişebilir. Sabitleri buradan
ayarla; gerçek API dokümanını çalıştırmadan önce doğrula.
"""
from __future__ import annotations

import time

import requests

import config

# Wavespeed Seedance text-to-video endpoint'i (gerekirse güncelle).
# lite-480p en ucuz seçenek; daha yüksek kalite için:
#   bytedance/seedance-v1-pro-t2v-480p  veya  bytedance/seedance-2.0/text-to-video
SUBMIT_URL = "https://api.wavespeed.ai/api/v3/bytedance/seedance-v1-lite-t2v-480p"
RESULT_URL = "https://api.wavespeed.ai/api/v3/predictions/{request_id}/result"


def _headers() -> dict:
    key = config.WAVESPEED_API_KEY
    if not key:
        raise RuntimeError("WAVESPEED_API_KEY eksik (.env).")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def submit_clip(prompt: str, aspect_ratio: str = "9:16", duration: int = 10) -> str:
    """Tek sahne için video üretimini başlatır, request id döndürür."""
    payload = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "duration": duration,
    }
    resp = requests.post(SUBMIT_URL, json=payload, headers=_headers(), timeout=60)
    resp.raise_for_status()
    data = resp.json().get("data", resp.json())
    request_id = data.get("id") or data.get("request_id")
    if not request_id:
        raise RuntimeError(f"Wavespeed request id alınamadı: {resp.text[:300]}")
    return request_id


def poll_clip(request_id: str) -> str:
    """Klip tamamlanana kadar bekler; üretilen video URL'sini döndürür."""
    deadline = time.monotonic() + config.POLL_TIMEOUT
    while time.monotonic() < deadline:
        resp = requests.get(
            RESULT_URL.format(request_id=request_id), headers=_headers(), timeout=60
        )
        resp.raise_for_status()
        data = resp.json().get("data", resp.json())
        status = (data.get("status") or "").lower()

        if status in ("completed", "succeeded", "success"):
            outputs = data.get("outputs") or []
            if outputs:
                return outputs[0]
            url = data.get("output") or data.get("video_url")
            if url:
                return url
            raise RuntimeError(f"Tamamlandı ama çıktı URL yok: {data}")
        if status in ("failed", "error"):
            raise RuntimeError(f"Wavespeed üretimi başarısız: {data}")

        time.sleep(config.POLL_INTERVAL)

    raise TimeoutError(f"Wavespeed klip zaman aşımı (request_id={request_id}).")


def generate_clip(prompt: str, **kwargs) -> str:
    """Tek sahne için gönder + poll: video URL döndürür."""
    return poll_clip(submit_clip(prompt, **kwargs))


def generate_clips(prompts: list[str], **kwargs) -> list[str]:
    """3 sahne için sırayla klip üretir, video URL listesi döndürür."""
    urls = []
    for i, p in enumerate(prompts, 1):
        print(f"[video] Sahne {i}/{len(prompts)} üretiliyor...")
        urls.append(generate_clip(p, **kwargs))
    return urls
