"""Stage 3 — Final Edit (Fal AI · ffmpeg-api/compose) + download.

Combines 3 × 10s clips with audio into a single ~30s video, then downloads it
locally.

NOTE: the Fal ffmpeg-api/compose schema may change; verify the constants.
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

# Target loudness for social media (YouTube ~ -14 LUFS).
LOUDNORM_TARGET = "I=-14:TP=-1.5:LRA=11"


def _ffmpeg_exe() -> str | None:
    """Finds the local ffmpeg binary (imageio-ffmpeg package or PATH)."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def _headers() -> dict:
    key = config.FAL_API_KEY
    if not key:
        raise RuntimeError("FAL_API_KEY missing (.env).")
    return {"Authorization": f"Key {key}", "Content-Type": "application/json"}


def _build_compose_payload(video_urls: list[str], clip_seconds: float = 10.0) -> dict:
    """Builds a compose request that appends consecutive clips end-to-end.

    Fal ffmpeg compose expects timestamp/duration values in MILLISECONDS. To
    preserve audio, BOTH a video AND an audio track are built from the same
    clips — only the 'video' track takes the picture and drops the sound.
    """
    keyframes = []
    cursor_ms = 0.0
    duration_ms = clip_seconds * 1000.0
    for url in video_urls:
        keyframes.append({"url": url, "timestamp": cursor_ms, "duration": duration_ms})
        cursor_ms += duration_ms
    # The same keyframe list is used for both tracks.
    return {
        "tracks": [
            {"id": "video", "type": "video", "keyframes": list(keyframes)},
            {"id": "audio", "type": "audio", "keyframes": list(keyframes)},
        ]
    }


def compose(video_urls: list[str], clip_seconds: float = 10.0) -> str:
    """Combines the clips; returns the final video URL."""
    payload = _build_compose_payload(video_urls, clip_seconds)
    resp = requests.post(
        f"{QUEUE_BASE}/{MODEL_ID}", json=payload, headers=_headers(), timeout=60
    )
    resp.raise_for_status()
    submit = resp.json()
    request_id = submit.get("request_id")
    if not request_id:
        raise RuntimeError(f"Could not get compose request_id: {resp.text[:300]}")

    # For sub-path models (fal-ai/ffmpeg-api/compose), the status/result URLs
    # don't include /compose; the safest approach is to use the URLs from the
    # submit response.
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
            raise RuntimeError(f"compose completed but no URL: {data}")
        if status in ("ERROR", "FAILED"):
            raise RuntimeError(f"compose failed: {s.text[:300]}")

        time.sleep(config.POLL_INTERVAL)

    raise TimeoutError(f"compose timed out (request_id={request_id}).")


def download(url: str, dest: Path) -> Path:
    """Downloads the final video locally."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                if chunk:
                    f.write(chunk)
    return dest


def normalize_audio(src: Path, dest: Path) -> Path:
    """Brings the ASMR sound up to an audible level (ffmpeg loudnorm).

    If ffmpeg is missing or fails, copies the source to dest as-is (fails
    silently — the pipeline doesn't stop). The picture is not re-encoded
    (-c:v copy).
    """
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        print("[compose] ffmpeg not found — skipping audio normalization.")
        if src != dest:
            shutil.copyfile(src, dest)
        return dest

    # Force the output into the most compatible format: 48kHz stereo AAC + faststart.
    # (loudnorm alone can produce 96kHz mono; some players won't play that.)
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
        print(f"[compose] Audio normalized -> {dest}")
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"[compose] Normalization failed ({exc}); using the raw file instead.")
        if src != dest:
            shutil.copyfile(src, dest)
    return dest


def compose_and_download(video_urls: list[str], dest: Path,
                         clip_seconds: float = 10.0, normalize: bool = True) -> Path:
    """Combine + download (+ normalize audio): returns the local .mp4 path."""
    print("[compose] Combining clips...")
    final_url = compose(video_urls, clip_seconds)

    if normalize:
        raw = dest.with_name(dest.stem + "_raw.mp4")
        print(f"[compose] Downloading -> {raw}")
        download(final_url, raw)
        normalize_audio(raw, dest)
        raw.unlink(missing_ok=True)
        return dest

    print(f"[compose] Downloading -> {dest}")
    return download(final_url, dest)
