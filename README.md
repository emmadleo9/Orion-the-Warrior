# Orion the Warrior

Orion the Warrior is a local-first command center and personal automation starter for consolidating communication, device management, and a local AI assistant called Nico de Angelo.

## Features

- AI assistant panel for summaries and action plans
- Device registry and task queue for connected devices
- Local image generation prototype using Pillow
- Start point for integrations with Gmail, Discord, WhatsApp, Telegram, Instagram, and other web services

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
