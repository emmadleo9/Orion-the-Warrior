# Orion Self-Writer — Setup & Usage

Orion can now rewrite and upgrade its own code from an admin command, 100%
free and local (no paid OpenAI API key required).

## What it does

- **Self-Writer Engine** (`orion/core/self_writer/self_writer.py`): `write_code(admin_command)` reads Orion's codebase, asks a code-writing model to generate/rewrite code, tests it in a sandbox, auto-fixes errors (max 5 loops), and shows you a diff.
- **Safety Sandbox** (`orion/core/self_writer/sandbox.py`): AST syntax checks for Python, structural/build checks for JS/HTML, auto self-correction loop, and backups of old files before any overwrite.
- **Admin Panel** (`orion_app/static/index.html` → "Self Writer" view): textarea command, live logs, diff review, Approve/Reject before deploy.
- **API** (`orion/core/self_writer/routes.py`): `POST /api/self-write/write`, `POST /api/self-write/apply`, `GET /api/self-write/status`, `GET /api/self-write/backups`.

## Files added

```
orion/__init__.py
orion/core/__init__.py
orion/core/self_writer/__init__.py
orion/core/self_writer/model_client.py   # Ollama + OpenRouter free fallback
orion/core/self_writer/model_loader.py   # model loader factory
orion/core/self_writer/codebase_scanner.py
orion/core/self_writer/sandbox.py
orion/core/self_writer/diff_utils.py
orion/core/self_writer/self_writer.py
orion/core/self_writer/routes.py
orion/core/self_writer/README.md
orion/backups/                           # created on first apply
```

Modified:
- `orion_app/main.py` — mounts the self-writer router
- `orion_app/static/index.html` — Self Writer nav button + panel view
- `orion_app/static/app.js` — self-writer UI logic

## 1. Install Ollama (recommended — 100% local, no key)

Download and install Ollama: https://ollama.com/download

Then pull the best free code-writing model:

```powershell
ollama pull qwen2.5-coder:32b
```

If 32B is too large for your hardware, use the 7B variant:

```powershell
ollama pull qwen2.5-coder:7b
```

Set the model Orion uses (optional, defaults to `qwen2.5-coder:32b`):

```powershell
$env:ORION_SELFWRITER_MODEL="qwen2.5-coder:32b"
python main.py
```

## 2. OpenRouter free-tier fallback (no Ollama)

If you can't run Ollama locally, Orion falls back to OpenRouter's free tier.
Get a free key at https://openrouter.ai/keys and set:

```powershell
$env:OPENROUTER_API_KEY="sk-or-..."
$env:ORION_SELFWRITER_OPENROUTER_MODEL="qwen/qwen2.5-coder-32b-instruct:free"
python main.py
```

The free tier requires no credit card for many models, but is rate-limited.

## 3. Browser-only fallback (no Ollama, no key)

If you have neither Ollama nor an OpenRouter key, the admin panel still loads
but code generation will report "No code-writing model available." You can run
a smaller 7B model in-browser via transformers.js/WebLLM separately, or just
install Ollama (recommended).

## 4. Start Orion

```powershell
cd "Orion The Warrior"
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

Open http://localhost:8000 and click **Self Writer** in the sidebar.

## 5. Using the Self Writer

1. Enter a command, e.g. `add a dark mode toggle` or `create a login page`.
2. Optionally set a target file (e.g. `orion_app/static/self_writer.html`).
3. Click **Make Orion Write It**.
4. Watch the live log: "Orion is writing code…" → "Testing…" → (if needed) "Fixing error…" → "Done!".
5. Review the unified diff. Click **Approve & Apply** or **Reject**.
6. On approve, Orion backs up the old file to `orion/backups/` and writes the new
   code. The change is live on the next page load (no server restart).

## Safety

- Nothing is written to a live source file until you click **Approve & Apply**.
- Every overwrite first backs up the previous file under `orion/backups/`.
- Python files are validated with `ast` + `compile()`; JS/HTML get structural
  checks plus an optional build/typecheck if `npm`/`tsc` are present.
- Failed generations are sent back to the model for self-correction (max 5 loops)
  before being shown to you as a rejected diff.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ORION_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama endpoint |
| `ORION_SELFWRITER_MODEL` | `qwen2.5-coder:32b` | Local code-writing model |
| `ORION_SELFWRITER_CONTEXT` | `16384` | Model context window |
| `ORION_SELFWRITER_MAX_TOKENS` | `4096` | Max generation tokens |
| `OPENROUTER_API_KEY` | (none) | OpenRouter free-tier key |
| `ORION_SELFWRITER_OPENROUTER_MODEL` | `qwen/qwen2.5-coder-32b-instruct:free` | OpenRouter model |
