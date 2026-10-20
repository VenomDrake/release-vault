#!/usr/bin/env bash
set -e

mkdir -p "${VAULT_DATA_DIR:-/srv/github-vault}" "${VAULT_ARCHIVE_DIR:-/srv/github-vault/archives}"

# Launch 24/7 Telegram Bot in background (reads token/chat_id dynamically from SQLite)
python3 /app/telegram_bot.py &

# Launch FastAPI Web Server
exec uvicorn server:app --host 0.0.0.0 --port "${VAULT_PORT:-8080}"
