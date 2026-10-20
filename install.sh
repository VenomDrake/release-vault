#!/usr/bin/env bash
# ==============================================================================
# Release Vault — Automated Linux / Proxmox LXC Installer
# Installs Python venv, dependencies, and systemd services (Web UI + Telegram Bot)
# ==============================================================================
set -euo pipefail

APP_DIR="/opt/github-vault"
DATA_DIR="${VAULT_DATA_DIR:-/srv/github-vault}"
ARCHIVE_DIR="${VAULT_ARCHIVE_DIR:-/srv/github-vault/archives}"
PORT="${VAULT_PORT:-8080}"

echo "=================================================================="
echo " 🚀 Release Vault — Installer"
echo "=================================================================="

if [[ $EUID -ne 0 ]]; then
   echo "❌ Please run this script as root (sudo ./install.sh)"
   exit 1
fi

echo "📦 [1/4] Installing system dependencies (Python3, venv, curl)..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip curl ca-certificates

echo "📁 [2/4] Creating application and archive directories..."
mkdir -p "$APP_DIR/static"
mkdir -p "$DATA_DIR" "$ARCHIVE_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/server.py" "$APP_DIR/server.py"
cp "$SCRIPT_DIR/telegram_bot.py" "$APP_DIR/telegram_bot.py"
cp "$SCRIPT_DIR/requirements.txt" "$APP_DIR/requirements.txt"
cp "$SCRIPT_DIR/static/index.html" "$APP_DIR/static/index.html"

echo "🐍 [3/4] Setting up Python virtual environment & packages..."
if [[ ! -d "$APP_DIR/venv" ]]; then
    python3 -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/pip" install --upgrade pip -q
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt" -q

echo "⚙️  [4/4] Configuring systemd services (github-vault & github-vault-bot)..."

cat >/etc/systemd/system/github-vault.service <<EOF
[Unit]
Description=Release Vault Web Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
Environment="VAULT_DATA_DIR=${DATA_DIR}"
Environment="VAULT_ARCHIVE_DIR=${ARCHIVE_DIR}"
Environment="VAULT_DB_PATH=${DATA_DIR}/vault.db"
ExecStart=${APP_DIR}/venv/bin/uvicorn server:app --host 0.0.0.0 --port ${PORT}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/github-vault-bot.service <<EOF
[Unit]
Description=Release Vault 24/7 Telegram Bot
After=network-online.target github-vault.service
Wants=github-vault.service

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
Environment="VAULT_DATA_DIR=${DATA_DIR}"
Environment="VAULT_DB_PATH=${DATA_DIR}/vault.db"
Environment="VAULT_API_BASE=http://127.0.0.1:${PORT}"
Environment="VAULT_API_URL=http://127.0.0.1:${PORT}"
ExecStart=${APP_DIR}/venv/bin/python ${APP_DIR}/telegram_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now github-vault.service
systemctl enable --now github-vault-bot.service

HOST_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "=================================================================="
echo " ✅ Installation Completed Successfully!"
echo " 🌐 Web UI:        http://${HOST_IP}:${PORT}"
echo " 🔑 First Login:   Username: admin   |   Password: admin"
echo " 📖 On first login, the 5-Step Setup Wizard will guide you through"
echo "    setting your password, GitHub Token, Nexus Mods & Telegram Bot!"
echo "=================================================================="
