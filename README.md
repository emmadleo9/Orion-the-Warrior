# Orion the Warrior

Orion the Warrior is a local-first command center and personal automation starter for consolidating communication, device management, and a local AI assistant called Nico de Angelo.

## Features

- AI assistant panel for summaries and action plans
- Private, context-aware chat with Nico powered by a local Ollama model
- Live web search, weather by named location, local time, and Orion device/task status
- Persistent local chat archive (up to 999,999 messages per browser conversation) with relevant-history retrieval and streamed replies
- Device registry and task queue for connected devices
- Live Tasks monitor for Orion operation progress, logs, and outcomes
- Archer image generation with selectable online and offline modes, generated-image preview, and a local Stable Diffusion Turbo model
- Social Hub workspaces for WhatsApp, Discord, and Instagram with official web-app handoffs and browser-local message drafts
- Orion brand artwork used as the app logo, favicon, and dashboard hero image, with the Matrix-green theme blended with gold and amber highlights

## Quick start

```bash
cd "Orion The Warrior"
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

Then open:

- http://localhost:8000

If you want the fastest manual startup on Windows, run the launcher from the repo root:

```powershell
start_orion.bat
```

## Deploy to Render

The repository includes a Render Blueprint in `render.yaml`. Push this project
to a GitHub, GitLab, or Bitbucket repository, sign in to Render, create a new
Blueprint, and select that repository. Render will build the lightweight web
runtime and start Orion on its assigned port. The larger local PyTorch/
Diffusers image-generation stack is deliberately excluded from the cloud
requirements.

The service is configured as a public, unauthenticated web app. Anyone with
its URL can access the app's API and use configured integrations; do not put
private conversations or account actions on this deployment. Local SQLite data,
generated images, Nico's conversation archive, task-run history, and Instagram
tokens are not durable across Render free-instance restarts. Persistent storage
or a database migration is required before using the cloud service for data you
need to retain.

Cloud Orion cannot reach Ollama at `127.0.0.1` on your laptop. Configure
`ORION_OLLAMA_URL` in Render to point to an Ollama service reachable from the
cloud, or Nico chat will remain unavailable. Do not expose an unauthenticated
Ollama server to the public internet. Offline Archer generation is not included
on this lightweight deployment; online generation depends on the external
image service. Instagram authorization tokens are memory-only and are lost
when the service restarts. Set `ORION_INSTAGRAM_REDIRECT_URI` to the exact
HTTPS callback URL for the Render service and register the same URI in the Meta
developer console before connecting Instagram. Add secrets through Render's
environment settings, never to `render.yaml` or source control.

## Enable Nico chat

Install [Ollama](https://ollama.com/download), open it, then download the default model:

```powershell
ollama pull qwen2.5:3b
```

Start Orion with `python main.py` and use the chat panel. Conversation context is
archived locally by Orion and sent to Ollama running on this computer; no
external AI API key is used. By default, Orion connects to
`http://127.0.0.1:11434` and uses `qwen2.5:3b`. To change these, set
`ORION_OLLAMA_URL` or `ORION_OLLAMA_MODEL` before starting Orion. The chat panel
shows whether Ollama and the selected model are ready.

Nico can use bounded tools for DuckDuckGo web search, Open-Meteo weather,
computer-local time, and Orion's current device/task lists. Web search queries
are sent to DuckDuckGo; weather location queries and coordinates are sent to
Open-Meteo. Orion device and task data stays on this computer. Ask for weather
by city or location; Nico does not automatically access device location. Search
and weather require an internet connection.

## Live task activity

Open **Tasks** in the sidebar to view live runs for Nico responses, Archer image
generation, Instagram actions, and device/task requests. Orion streams status
changes and safe progress messages to the browser and keeps the most recent
100 runs in process memory; task history resets when Orion restarts. Prompts,
message contents, credentials, and generated output are not copied into the
activity log. This monitor reports Orion's built-in operations; it does not run
arbitrary code submitted by users or display source code.

Chat is archived in `orion_app/data/conversations.sqlite3` by default (or the path
set by `ORION_MEMORY_PATH`). Nico recalls recent messages plus a small set of
relevant older messages; the complete 999,999-message archive is not sent to the
model at once because local models have finite context windows. Use **Clear
memory** to remove this browser conversation. Replies stream as the local model
generates them. For faster responses, Orion defaults to a 4096-token context and
256 generated tokens. Set `ORION_OLLAMA_CONTEXT` and `ORION_OLLAMA_MAX_TOKENS`
to raise these limits if you prefer longer context or replies; smaller values
generally use less memory and respond faster.
The archive is local SQLite data and is not encrypted by the app; protect the
computer account and database file accordingly.

Nico does not automatically install or execute every open-source tool on the
internet. That ecosystem is not a single compatible or trusted tool set.
Currently, only the explicitly built-in search, weather, local-time, and
read-only Orion-status tools are available; additional integrations need a
specific, reviewed connector.

## Social Hub

Select **Social Hub** in the sidebar for the Instagram account manager and
web-app shortcuts for WhatsApp and Discord.
WhatsApp and Discord still open their official services in a separate browser
tab and support per-platform local message drafts; their inboxes are not synced.
Browser drafts are stored in local storage on this device.

### Instagram account manager

Orion includes a Meta OAuth connection and account manager using Instagram's
official Instagram Login API. It supports professional-account profile/media
and insights, image publishing from a publicly reachable HTTPS image URL,
comment reading/replies, and eligible customer conversations/messages. Instagram
does not provide unrestricted API access: this requires a Business or Creator
account, an Instagram app configured in Meta for Developers, the listed
permissions, and Standard/Advanced Access as appropriate. Messaging is subject
to Meta's conversation and response-window policies. Personal/consumer accounts
are not supported by this API.

Configure the Meta app's Instagram Business Login callback URL to exactly:

```text
http://localhost:8000/api/instagram/callback
```

Then set the app ID and secret in the PowerShell session used to start Orion:

```powershell
$env:ORION_INSTAGRAM_APP_ID = "<Instagram App ID>"
$env:ORION_INSTAGRAM_APP_SECRET = "<Instagram App Secret>"
python main.py
```

Optionally set `ORION_INSTAGRAM_REDIRECT_URI` if the registered callback differs,
and `ORION_INSTAGRAM_API_VERSION` to the version enabled for your Meta app
(defaults to `v25.0`). Do not commit app secrets. Click **Connect Instagram**
in the built-in manager and approve the permissions in Meta's official login.
Access tokens are held only in Orion's process memory, never written to the
repository or browser storage; restarting Orion requires reconnecting. Use
**Disconnect** to immediately clear the in-memory token. Orion's built-in
launcher binds to `127.0.0.1` so this account manager is not exposed on the
local network by default.

## Archer image generation

The **Archer** panel generates images from its own prompt field. Choose **Online**
to use the Pollinations hosted image service (the prompt is sent to that
service), **Offline** to use the local model without network access, or **Auto**
to try online and then use the installed local model. Generated PNGs are saved
in `generated/` and previewed in the panel.

The offline backend uses Stable Diffusion Turbo (`stabilityai/sd-turbo`) through
PyTorch and Diffusers. Install the Python dependencies from `requirements.txt`,
then download the model once while online:

```powershell
python scripts\download_archer_model.py
```

The model files are stored in the Hugging Face cache (not in the source tree).
The first offline generation loads the model and can take a while, especially
on CPU. Archer uses CUDA when a compatible PyTorch/CUDA installation is
available; otherwise it runs on CPU. For speed, the default is one SD-Turbo
inference step at 512×512; set `ORION_ARCHER_STEPS` to 2–4 for higher quality
with longer generation time. Set `ORION_ARCHER_MODEL` to use a different
Diffusers-compatible model repository. The Archer status in the UI indicates
whether the selected local model is cached.

## Repo upload

```bash
git init
git add .
git commit -m "Initial Orion the Warrior prototype"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```

## Notes

This starter is intentionally local and platform-agnostic. Real access to external services such as Instagram, Telegram, WhatsApp, Discord, and Google requires user credentials, official APIs, and clear consent.

## License

This project is for local experimentation and prototyping.
