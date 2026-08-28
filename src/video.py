"""Stage 2 (Step 5) — Generate video clips (Wavespeed AI · ByteDance Seedance).

Generates a separate 9:16 / 10s clip for each scene prompt. Asynchronous flow:
submit → request id → poll → result URL.

NOTE: Wavespeed endpoints/parameters may change over time. Adjust the
constants here; verify the current API docs before running.
"""
from __future__ import annotations

import time

import requests

import config

# Wavespeed Seedance text-to-video endpoint (update if needed).
# lite-480p is the cheapest option; for higher quality use:
#   bytedance/seedance-v1-pro-t2v-480p  or  bytedance/seedance-2.0/text-to-video
SUBMIT_URL = "https://api.wavespeed.ai/api/v3/bytedance/seedance-v1-lite-t2v-480p"
RESULT_URL = "https://api.wavespeed.ai/api/v3/predictions/{request_id}/result"


def _headers() -> dict:
    key = config.WAVESPEED_API_KEY
    if not key:
        raise RuntimeError("WAVESPEED_API_KEY missing (.env).")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def submit_clip(prompt: str, aspect_ratio: str = "9:16", duration: int = 10) -> str:
    """Starts video generation for a single scene, returns the request id."""
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
        raise RuntimeError(f"Could not get Wavespeed request id: {resp.text[:300]}")
    return request_id


def poll_clip(request_id: str) -> str:
    """Waits until the clip is complete; returns the generated video URL."""
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
            raise RuntimeError(f"Completed but no output URL: {data}")
        if status in ("failed", "error"):
            raise RuntimeError(f"Wavespeed generation failed: {data}")

        time.sleep(config.POLL_INTERVAL)

    raise TimeoutError(f"Wavespeed clip timed out (request_id={request_id}).")


def generate_clip(prompt: str, **kwargs) -> str:
    """Submit + poll for a single scene: returns the video URL."""
    return poll_clip(submit_clip(prompt, **kwargs))


def generate_clips(prompts: list[str], **kwargs) -> list[str]:
    """Generates clips sequentially for 3 scenes, returns a list of video URLs."""
    urls = []
    for i, p in enumerate(prompts, 1):
        print(f"[video] Generating scene {i}/{len(prompts)}...")
        urls.append(generate_clip(p, **kwargs))
    return urls
