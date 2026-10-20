FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VAULT_DATA_DIR=/srv/github-vault \
    VAULT_ARCHIVE_DIR=/srv/github-vault/archives \
    VAULT_DB_PATH=/srv/github-vault/vault.db \
    VAULT_API_URL=http://127.0.0.1:8080 \
    VAULT_PORT=8080

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY server.py telegram_bot.py docker-entrypoint.sh /app/
COPY static/ /app/static/
RUN chmod +x /app/docker-entrypoint.sh && \
    mkdir -p /srv/github-vault/archives

VOLUME ["/srv/github-vault"]
EXPOSE 8080

ENTRYPOINT ["/app/docker-entrypoint.sh"]
