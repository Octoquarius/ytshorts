# AI ASMR YouTube Shorts Factory

A Python automation that generates **5 different YouTube accounts, each with its
own distinct ASMR Short**, every day. Each account generates an idea independent
of the others' themes → 5 unique videos per day. **User approval for every
video** is mandatory before upload.

See [`plan.md`](plan.md) for the detailed design.

## Flow

1. **Idea** (Claude): a one-line concept based on the account's theme + a structured plan.
2. **Assets** (Wavespeed Seedance + Fal mmaudio): 3 scene prompts → 3 clips → ASMR sound.
3. **Edit** (Fal ffmpeg): combine the clips into one ~30s video + download.
4. **Distribution**: approval → YouTube upload → Sheets log → Gmail notification.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
pip install -r requirements.txt
cp .env.example .env            # then fill in .env
```

### `.env` keys
Fill in every field in `.env.example`: Anthropic, Wavespeed, Fal,
`GOOGLE_SHEET_ID`, Gmail App Password.

### Accounts (`accounts.json`)
5 accounts and **5 different themes** are defined. Credentials per account:

```
credentials/sheets/client_secret.json    # Sheets (a single project is enough)
credentials/account1/client_secret.json  # a SEPARATE project for each YouTube account
credentials/account2/client_secret.json
...  (account3, account4, account5)
```

> ⚠️ **YouTube quota**: the quota is per Google Cloud project (10,000 units/day,
> `videos.insert` ~1600 units). Uploading for 5 accounts from a single project
> exhausts the quota → use **a separate Google Cloud project for each account**.

## Usage

```bash
# Prepare a video for all accounts (a different video for each), then ask for approval:
python -m src.pipeline

# Single account only:
python -m src.pipeline --account account1

# Manual upload after approval (using the manifest produced during preparation):
python -m src.pipeline --upload account1 output/account1/2026-06-16_ab12cd34.manifest.json

# Fully automatic without approval (use with caution):
python -m src.pipeline --auto-upload
```

On first run, a browser OAuth prompt appears for each account + Sheets; tokens
are stored as `credentials/.../token.json` (subsequent runs are automatic).

## Testing module by module

```bash
python -m src.ideate      # idea + plan generation (requires an Anthropic key)
python -m src.prompts     # 3 scene prompts
```

## Scheduling

Claude Code `/schedule` is used to trigger the video-preparation step daily;
prepared videos wait for approval, and upload is triggered after approval.
