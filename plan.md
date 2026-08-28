# Automatic AI YouTube Shorts Factory (ASMR) — Plan

> An automation that does what n8n would do, using **only Python + Claude Code**,
> producing ASMR YouTube Shorts at set times every day. It publishes to **5
> different YouTube accounts a day, each with a video that is DIFFERENT FROM THE
> OTHERS** (the same video is not copied to 5 places; each account produces its
> own separate idea → separate clips → separate edit chain). **User approval is
> always required** before a video is uploaded to YouTube.

---

## 1. Decisions Already Made

| Topic | Decision |
|---|---|
| Language / Runtime | **Python 3.11+** |
| Text generation (idea + scene prompts) | **Claude (Anthropic API)** — `claude-opus-4-8` / `claude-haiku-4-5` |
| Video generation | **Wavespeed AI** — ByteDance Seedance (text-to-video) |
| Audio generation + composition | **Fal AI** — `mmaudio-v2` (audio) + `ffmpeg-api/compose` (editing) |
| Scheduling | **Claude Code `/schedule`** (cron-based cloud routine) |
| Content theme | **ASMR** (kinetic sand, slicing/scooping, etc.) |
| Content language | **English** (title, description, hashtags) |
| Logging | **Google Sheets** |
| Notification | **Email (Gmail)** |
| Upload approval | **User approval mandatory for every video** |
| Target number of accounts | **5 different YouTube accounts per day** |
| Video–account mapping | **1 DIFFERENT video per account** → 5 unique videos total per day (no repeated content) |

---

## 2. Workflow (Pipeline)

A direct Python equivalent of the n8n workflow. 4 stages.

> 🔁 **Multi-account loop**: the 4 stages below run **separately for each of the
> 5 accounts** every day. The pipeline loops over the accounts listed in
> `accounts.json`; each account uses its own **theme**, OAuth token, Sheets tab,
> and publish time. Since each account generates **a separate idea based on its
> own theme** in Stage 1, the output is naturally unique: **5 videos, each
> DIFFERENT FROM THE OTHERS**, are produced and uploaded to 5 separate channels
> every day. **The same video is never copied to multiple accounts.** Generated
> ideas are checked against the history in Sheets (dedupe) to prevent repeats
> within a day and across days.

### Stage 1 — Idea Generation (Claude)
1. **Generate a trending idea**: ask Claude for a one-line, viral, simple ASMR
   concept (< 10 words).
2. **Turn the idea into a production plan**: in a second call, Claude expands
   the idea into structured JSON:
   ```json
   {
     "Caption": "... 1 emoji + 12 hashtags ...",
     "Idea": "(color/style) (object) being (action)",
     "Environment": "< 20-word scene description",
     "Sound": "< 15-word sound description",
     "Status": "for production"
   }
   ```
3. **Add a new row to Google Sheets**: `idea, caption, environment_prompt,
   sound_prompt, production=In Progress`.

### Stage 2 — Asset Generation
4. **Generate 3 scene prompts** (Claude): from the Idea + Environment + Sound
   inputs, each 1000–2000 characters, describing scenes with camera work and motion.
5. **Generate video clips** (Wavespeed Seedance): a separate clip per scene,
   `aspect_ratio: 9:16`, `duration: 10`. Asynchronous: submit → request id → poll.
6. **Generate audio** (Fal mmaudio-v2): ASMR sound from the generated video +
   the Sound prompt. Asynchronous: queue.fal.run → request_id → poll.

### Stage 3 — Final Edit
7. **Combine the clips** (Fal ffmpeg-api/compose): 3 × 10s = ~30s single video.
8. **Download the final video** (to the local `output/` folder as `.mp4`).

### Stage 4 — Distribution & Logging
9. **🔔 APPROVAL STEP**: the pipeline stops and shows the user:
   - Title, description, hashtags
   - The local video file path (so the user can watch and review it)
   - "Do you approve uploading this video to YouTube? (yes/no)"
   - If not approved, the video is not uploaded and the status in Sheets stays
     `Pending Approval`.
10. **Upload to YouTube** (after approval): title, description, tags, `privacyStatus`.
11. **Update Google Sheets**: update the same row with `final_output`,
    `youtube_url`, `production=Done`.
12. **Send a Gmail notification**: "New video published" + the YouTube link.

---

## 3. Required API Keys and How to Get Them

None exist yet. We'll set them up one by one. All will be kept in the `.env`
file (never committed to the repo).

| Service | What it's for | Where to get it | Estimated cost |
|---|---|---|---|
| **Anthropic** | Idea + scene prompts | console.anthropic.com → API Keys | Very low (text) |
| **Wavespeed AI** | Seedance video generation | wavespeed.ai → sign up → API key | Charged per video |
| **Fal AI** | Audio (mmaudio) + editing (ffmpeg) | fal.ai → sign up → API key | Charged per operation |
| **Google Cloud** | YouTube + Sheets OAuth | console.cloud.google.com | Free (within quota) |
| **Gmail** | Email notification | Google Account → App Password | Free |

### Google Cloud setup (the longest step) — for 5 accounts
1. Create project(s) in console.cloud.google.com. **Because of the quota (see
   below), a SEPARATE Google Cloud project per YouTube account is recommended
   → 5 projects total.**
2. Enable **YouTube Data API v3** in each project. (A single project is enough
   for the Google Sheets API — writing to Sheets doesn't cause quota issues.)
3. Configure the OAuth consent screen in each project (External; add the
   relevant account as a test user).
4. Create an **OAuth 2.0 Client ID** (Desktop app) for each project →
   download `client_secret.json`.
5. On first run, a separate browser permission prompt per account produces an
   **account-specific `token.json`** (subsequent runs are automatic). A total
   of **5 OAuth approvals** are given.
6. Create a **Google Sheet**. Use either a separate tab per account or an
   `account` column. Columns:
   `id | account | idea | caption | production | environment_prompt | sound_prompt | final_output | youtube_url`

### Gmail App Password
- Enable 2-step verification → App Passwords → generate a 16-digit password.

> ⚠️ **YouTube quota (critical for 5 accounts!)**: the YouTube Data API quota is
> 10,000 units per day **per Google Cloud project** (NOT per account).
> A `videos.insert` call costs ~1600 units → only ~6 uploads per day with a
> single project. Uploading for 5 accounts from a single project is risky
> (quota runs out, errors start). **Solution**: a separate Google Cloud project
> per account → a separate 10,000-unit quota for each. Alternative: a single
> project + a quota increase request (approval process is slow).

---

## 4. Project Structure

```
ytshorts/
├── plan.md                  # this file
├── README.md                # setup + usage instructions
├── requirements.txt         # Python dependencies
├── .env.example             # key template (empty)
├── .env                     # actual keys (gitignored)
├── .gitignore
├── config.py                # environment variables + settings
├── accounts.json            # settings for the 5 accounts (theme, token path, time, tab)
├── credentials/             # per-account OAuth (gitignored)
│   ├── account1/            #   client_secret.json + token.json
│   ├── account2/
│   ├── account3/
│   ├── account4/
│   └── account5/
├── output/                  # generated .mp4 files (per-account subfolder)
├── logs/                    # run logs
└── src/
    ├── ideate.py            # Claude: idea + plan generation
    ├── prompts.py           # Claude: 3 scene prompts
    ├── video.py             # Wavespeed Seedance integration
    ├── audio.py             # Fal mmaudio integration
    ├── compose.py           # Fal ffmpeg composition + download
    ├── sheets.py            # Google Sheets read/write
    ├── youtube.py           # YouTube upload (OAuth)
    ├── notify.py            # Gmail notification
    └── pipeline.py          # main flow running all steps in order
```

### `accounts.json` schema (5 accounts = 5 different themes = 5 different videos)

Each account has a **different `theme` value**; this diversifies the idea
prompt given to Claude in Stage 1, so that every channel gets a unique video.

```json
[
  { "id": "account1", "name": "Kinetic Sand ASMR", "theme": "kinetic sand cutting and crushing",
    "credentials_dir": "credentials/account1", "sheet_tab": "account1",
    "publish_time": "10:00", "privacy_status": "public" },
  { "id": "account2", "name": "Soap Cutting ASMR", "theme": "soap slicing and shaving",
    "credentials_dir": "credentials/account2", "sheet_tab": "account2",
    "publish_time": "12:00", "privacy_status": "public" },
  { "id": "account3", "name": "Ice & Glass ASMR", "theme": "ice and glass cracking",
    "credentials_dir": "credentials/account3", "sheet_tab": "account3",
    "publish_time": "14:00", "privacy_status": "public" },
  { "id": "account4", "name": "Slime Squish ASMR", "theme": "slime squishing and poking",
    "credentials_dir": "credentials/account4", "sheet_tab": "account4",
    "publish_time": "16:00", "privacy_status": "public" },
  { "id": "account5", "name": "Paint Mixing ASMR", "theme": "paint mixing and swirling",
    "credentials_dir": "credentials/account5", "sheet_tab": "account5",
    "publish_time": "18:00", "privacy_status": "public" }
]
```

| Field | Description |
|---|---|
| `id` | Unique identifier for the account (matches the folder/tab name) |
| `name` | Channel / human-readable label |
| `theme` | **Account-specific ASMR theme** → the source of each account's unique video |
| `credentials_dir` | Path to the account's own `client_secret.json` + `token.json` |
| `sheet_tab` | This account's Google Sheets tab |
| `publish_time` | This account's daily publish time (different times → quota/rate spread) |
| `privacy_status` | `public` / `unlisted` / `private` |

---

## 5. Dependencies (`requirements.txt`)

```
anthropic               # Claude API
requests                # HTTP (Wavespeed, Fal)
google-api-python-client
google-auth-oauthlib
google-auth-httplib2
python-dotenv
```

---

## 6. Approval Mechanism (the most critical requirement)

`pipeline.py` will run in two modes:

- **Without `--auto-upload` (default)**: the video is generated, downloaded,
  then STOPS. The user watches the file, and if they say "I approve" inside
  Claude Code, `youtube.py` is called. The automation running via `/schedule`
  prepares the video every day and waits for approval.
- **With `--auto-upload`**: (if requested later) fully automatic upload without approval.

Default behavior: **never upload without approval.** This is per your request.

---

## 7. Scheduling (`/schedule`)

- The "video preparation" part of the pipeline (Stages 1–3 + download) runs
  automatically at set daily time(s) via `/schedule`.
- The ready video + info card is presented, and **approval is awaited**.
- After approval, upload + logging + email are triggered.
- We'll configure together at the end of setup which times it should run at
  (e.g. every day at 10:00 and 18:00).

---

## 8. Implementation Order (To Do)

1. [ ] Project skeleton + `requirements.txt` + `.env.example` + `.gitignore`
2. [ ] `accounts.json` — 5 accounts, **5 different themes** (a separate/unique video per account)
3. [ ] `config.py` (load environment variables)
4. [ ] `ideate.py` — idea + plan with Claude (testable)
5. [ ] `prompts.py` — 3 scene prompts with Claude
6. [ ] `video.py` — Wavespeed Seedance (submit + poll)
7. [ ] `audio.py` — Fal mmaudio (submit + poll)
8. [ ] `compose.py` — Fal ffmpeg composition + download
9. [ ] `sheets.py` — Google Sheets integration
10. [ ] `youtube.py` — YouTube OAuth + upload
11. [ ] `notify.py` — Gmail notification
12. [ ] `pipeline.py` — loop over all accounts + approval step (a different video per account)
13. [ ] Enter keys in `.env`, end-to-end test (dry-run first)
14. [ ] Set up daily triggering with `/schedule`

---

## 9. Open Notes / Risks

- **Cost**: each video involves multiple paid API calls (video + audio). Setting
  up budget alerts on all dashboards is recommended.
- **API rate limits**: Wavespeed/Fal may temporarily block frequent calls →
  poll intervals will be tuned.
- **Seedance/Fal endpoint changes**: verify the current API docs while writing
  the integration (URLs/parameters may have changed).
- **YouTube quota limit**: the daily upload count is limited accordingly.

---

## 10. Next Step

Once this plan is approved, we'll start with **Step 1** (project skeleton).
I can also tell you which API keys to start obtaining first, if you'd like.
