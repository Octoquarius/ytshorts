"""Main flow — loops over all accounts.

Produces a separate/unique video for EACH of the 5 accounts every day (each
account generates a different idea from its own theme → the same video is
never repeated). In default mode, a video is prepared and the flow STOPS;
user approval is awaited before upload.

Usage:
  python -m src.pipeline                 # prepare a video for all accounts (awaits approval)
  python -m src.pipeline --account account1
  python -m src.pipeline --upload account1 <manifest.json>   # upload after approval
  python -m src.pipeline --auto-upload   # (caution) fully automatic without approval
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
    """Runs Stages 1–3 for one account; returns a manifest (approval card).

    Does NOT upload — the manifest is written to disk, and the approval step
    is left to the caller.
    """
    print(f"\n=== [{account.id}] {account.name} — theme: {account.theme} ===")

    # Stage 1 — Idea (based on the account's theme, deduped against history).
    prior = sheets.used_ideas(account.sheet_tab)
    idea = ideate.generate_unique_idea(account.theme, prior)
    print(f"[idea] {idea}")
    plan = ideate.expand_to_plan(idea, account.theme)

    row_id = uuid.uuid4().hex[:8]
    row_number = sheets.append_row(
        account.sheet_tab, row_id, account.name, plan["Idea"], plan["Caption"],
        plan["Environment"], plan["Sound"], production="In Progress",
    )

    # Stage 2 — 3 scene prompts → video → audio.
    scene_prompts = prompts.generate_scene_prompts(
        plan["Idea"], plan["Environment"], plan["Sound"]
    )
    clip_urls = video.generate_clips(scene_prompts)
    voiced_urls = audio.add_audio_to_clips(clip_urls, plan["Sound"])

    # Stage 3 — Combine + download.
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

    print(f"[ready] Video ready: {final_path}")
    print(f"[ready] Manifest: {manifest_path}")
    return manifest


def approve_and_upload(manifest: dict) -> str:
    """After approval: YouTube upload + Sheets update + email."""
    account = config.get_account(manifest["account_id"])
    video_path = Path(manifest["video_path"])
    if not video_path.exists():
        raise RuntimeError(f"Video not found: {video_path}")

    url = youtube_upload(account, video_path, manifest)
    sheets.update_status(
        manifest["sheet_tab"], manifest["row_number"],
        production="Done", youtube_url=url,
    )
    notify.notify_published(manifest["account_name"], manifest["title"], url)
    print(f"[done] Published: {url}")
    return url


def youtube_upload(account: config.Account, video_path: Path, manifest: dict) -> str:
    from src import youtube  # deferred import: not needed unless uploading
    return youtube.upload(
        account, video_path, manifest["title"], manifest["description"],
        manifest["caption"],
    )


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except EOFError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI ASMR YouTube Shorts factory")
    parser.add_argument("--account", help="Run for this account only")
    parser.add_argument(
        "--upload", nargs=2, metavar=("ACCOUNT", "MANIFEST"),
        help="Upload from a manifest after approval",
    )
    parser.add_argument(
        "--auto-upload", action="store_true",
        help="Fully automatic upload without approval (use with caution)",
    )
    args = parser.parse_args(argv)

    # Upload-only mode.
    if args.upload:
        _, manifest_path = args.upload
        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        approve_and_upload(manifest)
        return 0

    accounts = config.load_accounts()
    if args.account:
        accounts = [a for a in accounts if a.id == args.account]
        if not accounts:
            print(f"Account not found: {args.account}", file=sys.stderr)
            return 1

    manifests = []
    for account in accounts:
        try:
            manifests.append(prepare_account(account))
        except Exception as exc:  # one account's error shouldn't stop the others
            print(f"[error:{account.id}] {exc}", file=sys.stderr)

    # Approval step.
    print("\n================ APPROVAL STEP ================")
    for m in manifests:
        print(f"\n- {m['account_name']}")
        print(f"  Title: {m['title']}")
        print(f"  Description/Hashtags: {m['description']}")
        print(f"  Video: {m['video_path']}")

        if args.auto_upload:
            approve_and_upload(m)
        elif _confirm("  Upload this video to YouTube? (yes/no): "):
            approve_and_upload(m)
        else:
            print("  Skipped — status remains 'Pending Approval'.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
