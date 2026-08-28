"""Stage 2 (Step 6) — Generate audio (Fal AI · mmaudio-v2).

Generates ASMR sound from the generated video clip + the Sound prompt and
embeds the sound into the video. Asynchronous flow: queue.fal.run →
request_id → poll → result URL.

NOTE: Fal endpoints/parameters may change; verify the constants.
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
        raise RuntimeError("FAL_API_KEY missing (.env).")
    return {"Authorization": f"Key {key}", "Content-Type": "application/json"}


def submit(video_url: str, sound_prompt: str) -> dict:
    """Submits the mmaudio job to the queue; returns the submit response (status/response URL)."""
    payload = {"video_url": video_url, "prompt": sound_prompt}
    resp = requests.post(
        f"{QUEUE_BASE}/{MODEL_ID}", json=payload, headers=_headers(), timeout=60
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("request_id"):
        raise RuntimeError(f"Could not get Fal request_id: {resp.text[:300]}")
    return data


def poll(submit_data: dict) -> str:
    """Waits until the job completes; returns the video-with-audio URL.

    URLs are taken from the submit response (constructing them manually for
    sub-path models is error-prone).
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
            raise RuntimeError(f"mmaudio completed but no URL: {data}")
        if status in ("ERROR", "FAILED"):
            raise RuntimeError(f"mmaudio failed: {resp.text[:300]}")

        time.sleep(config.POLL_INTERVAL)

    raise TimeoutError(f"mmaudio timed out (request_id={request_id}).")


def add_audio(video_url: str, sound_prompt: str) -> str:
    """Submit + poll for a single clip: returns the video-with-audio URL."""
    return poll(submit(video_url, sound_prompt))


def add_audio_to_clips(video_urls: list[str], sound_prompt: str) -> list[str]:
    """Adds ASMR sound to all clips, returns a list of video-with-audio URLs."""
    out = []
    for i, url in enumerate(video_urls, 1):
        print(f"[audio] Adding sound to clip {i}/{len(video_urls)}...")
        out.append(add_audio(url, sound_prompt))
    return out
