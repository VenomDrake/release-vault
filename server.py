import asyncio
import hashlib
import html as html_lib
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import smtplib
import time
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from curl_cffi import requests as cffi_requests
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

# --- Configuration & Paths ---
BASE_DIR = Path("/opt/github-vault")
DATA_DIR = Path("/srv/github-vault")
ARCHIVE_DIR = DATA_DIR / "archive"
DB_PATH = DATA_DIR / "vault.db"

BASE_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("github-vault")

# Active sessions in memory
SESSIONS: Dict[str, float] = {}
DOWNLOAD_QUEUE: asyncio.Queue = asyncio.Queue()
QUEUED_RELEASES: set[int] = set()
ACTIVE_DOWNLOADS: Dict[int, Dict[str, Any]] = {}  # release_id -> progress info
GLOBAL_PAUSED: bool = False
PAUSED_REPOS: set[int] = set()
CHECK_LOCK = asyncio.Lock()
LAST_CHECK_TIME: Optional[str] = None
NEXT_CHECK_TIME: Optional[str] = None


class DownloadPausedException(Exception):
    pass


def hash_password(password: str, salt: str = "gh-vault-salt-2026") -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    conn = get_db()
    with conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS repositories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner TEXT NOT NULL,
                name TEXT NOT NULL,
                full_name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                html_url TEXT NOT NULL,
                avatar_url TEXT DEFAULT '',
                category TEXT DEFAULT 'Generale',
                tags TEXT DEFAULT '',
                include_prereleases INTEGER DEFAULT 1,
                download_source INTEGER DEFAULT 1,
                asset_filter TEXT DEFAULT '',
                stars INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_checked_at TEXT,
                status TEXT DEFAULT 'idle',
                error_message TEXT DEFAULT '',
                provider TEXT DEFAULT 'github',
                nexus_domain TEXT DEFAULT '',
                nexus_mod_id INTEGER DEFAULT 0,
                nexus_game_id INTEGER DEFAULT 0,
                nexus_game_name TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS releases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
                github_release_id INTEGER NOT NULL,
                tag_name TEXT NOT NULL,
                name TEXT NOT NULL,
                body TEXT DEFAULT '',
                prerelease INTEGER DEFAULT 0,
                draft INTEGER DEFAULT 0,
                published_at TEXT NOT NULL,
                author TEXT DEFAULT '',
                html_url TEXT DEFAULT '',
                tarball_url TEXT DEFAULT '',
                zipball_url TEXT DEFAULT '',
                folder_path TEXT NOT NULL,
                status TEXT DEFAULT 'pending', -- pending, downloading, completed, partial, error
                downloaded_at TEXT,
                total_size INTEGER DEFAULT 0,
                error_message TEXT DEFAULT '',
                UNIQUE(repo_id, tag_name)
            );

            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                release_id INTEGER NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
                github_asset_id INTEGER DEFAULT 0,
                name TEXT NOT NULL,
                asset_type TEXT DEFAULT 'binary', -- binary, source_zip, source_tar
                size INTEGER DEFAULT 0,
                download_url TEXT NOT NULL,
                local_path TEXT NOT NULL,
                sha256 TEXT DEFAULT '',
                status TEXT DEFAULT 'pending', -- pending, downloading, completed, error
                downloaded_at TEXT,
                UNIQUE(release_id, name)
            );

            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                level TEXT DEFAULT 'info',
                repo_name TEXT DEFAULT '',
                message TEXT NOT NULL
            );
            """
        )

        # Ensure new columns exist on existing repositories table
        existing_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(repositories)").fetchall()
        }
        new_cols = [
            ("provider", "TEXT DEFAULT 'github'"),
            ("nexus_domain", "TEXT DEFAULT ''"),
            ("nexus_mod_id", "INTEGER DEFAULT 0"),
            ("nexus_game_id", "INTEGER DEFAULT 0"),
            ("nexus_game_name", "TEXT DEFAULT ''"),
            ("paused", "INTEGER DEFAULT 0"),
            ("only_latest", "INTEGER DEFAULT 0"),
        ]
        for col_name, col_def in new_cols:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE repositories ADD COLUMN {col_name} {col_def}")

        has_existing_repos = conn.execute("SELECT COUNT(*) as c FROM repositories").fetchone()["c"] > 0
        defaults = {
            "setup_completed": "1" if has_existing_repos else "0",
            "language": "it",
            "auth_username": "admin",
            "auth_password_hash": hash_password("admin"),
            "github_token": "",
            "check_interval_minutes": "60",
            "global_sync_paused": "0",
            "download_source_default": "1",
            "include_prereleases_default": "1",
            "notify_on_initial_sync": "0",
            "discord_webhook_url": "",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "nexus_username": "",
            "nexus_password": "",
            "nexus_api_key": "",
            "nexus_session_cookie": "",
            "smtp_host": "",
            "smtp_port": "587",
            "smtp_user": "",
            "smtp_password": "",
            "smtp_from": "",
            "smtp_to": "",
        }
        for k, v in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
            )

    global GLOBAL_PAUSED, PAUSED_REPOS
    gp_row = conn.execute("SELECT value FROM settings WHERE key='global_sync_paused'").fetchone()
    GLOBAL_PAUSED = bool(gp_row and gp_row["value"] == "1")
    PAUSED_REPOS = {
        r["id"] for r in conn.execute("SELECT id FROM repositories WHERE paused=1").fetchall()
    }
    conn.close()


def get_settings_dict() -> Dict[str, str]:
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def set_setting(key: str, value: str) -> None:
    conn = get_db()
    with conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )
    conn.close()


def get_existing_categories() -> List[str]:
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT category FROM repositories WHERE category IS NOT NULL AND category != '' ORDER BY category ASC"
    ).fetchall()
    conn.close()
    cats = [r["category"] for r in rows]
    for default_cat in ["Giochi", "Emulatore", "MOD VR"]:
        if default_cat not in cats:
            cats.append(default_cat)
    return cats


def nexus_bbcode_to_markdown(raw: str) -> str:
    if not raw:
        return ""
    s = raw
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"\[b\](.*?)\[/b\]", r"**\1**", s, flags=re.I | re.S)
    s = re.sub(r"\[i\](.*?)\[/i\]", r"*\1*", s, flags=re.I | re.S)
    s = re.sub(r"\[u\](.*?)\[/u\]", r"__\1__", s, flags=re.I | re.S)
    s = re.sub(r"\[h1\](.*?)\[/h1\]", r"\n# \1\n", s, flags=re.I | re.S)
    s = re.sub(r"\[h2\](.*?)\[/h2\]", r"\n## \1\n", s, flags=re.I | re.S)
    s = re.sub(r"\[h3\](.*?)\[/h3\]", r"\n### \1\n", s, flags=re.I | re.S)
    s = re.sub(r"\[url=([^\]]+)\](.*?)\[/url\]", r"[\2](\1)", s, flags=re.I | re.S)
    s = re.sub(r"\[url\](.*?)\[/url\]", r"<\1>", s, flags=re.I | re.S)
    s = re.sub(r"\[\*\]", "\n- ", s)
    s = re.sub(r"\[/?(?:list|size|color|font|center|quote|spoiler|img)[^\]]*\]", "", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return html_lib.unescape(s).strip()


def auto_classify_repo(
    owner: str,
    name: str,
    description: str = "",
    topics: Optional[List[str]] = None,
    language: Optional[str] = None,
    existing_categories: Optional[List[str]] = None,
    provider: str = "github",
    game_name: str = "",
) -> Dict[str, str]:
    """Automatically generate smart tags and suggest the best matching category based on GitHub or Nexus Mods info."""
    if existing_categories is None:
        existing_categories = get_existing_categories()

    text = f"{owner} {name} {description or ''} {game_name or ''} {' '.join(topics or [])}".lower()
    tags_list: List[str] = []

    def add_tag(t: str):
        t_clean = re.sub(r"[^a-z0-9-_+#.]", "-", t.strip().lower()).strip("-")
        if t_clean and t_clean not in tags_list and len(tags_list) < 8:
            tags_list.append(t_clean)

    if provider == "nexusmods":
        add_tag("nexusmods")
        if owner:
            add_tag(owner)  # game domain e.g. cyberpunk2077, skyrimspecialedition

    for t in (topics or [])[:5]:
        add_tag(t)

    if language:
        add_tag(language)

    keyword_map = [
        (["vr", "openxr", "openvr", "steamvr", "quest", "oculus", "headset", "6dof"], "vr"),
        (["mod", "mods", "modding", "patch", "hook", "injector", "installer", "bettervr"], "mod"),
        (["ps5", "anyps5", "kyty", "playstation 5", "playstation5"], "ps5"),
        (["ps4", "shadps4", "fpps4", "playstation 4", "orbis"], "ps4"),
        (["ps3", "rpcs3", "playstation 3"], "ps3"),
        (["emu", "emulator", "emulation", "emulatore"], "emulatore"),
        (["pc", "windows", "win64", "directx", "d3d11", "d3d12", "vulkan"], "pc"),
        (["linux", "steamdeck", "proton", "wine"], "linux"),
        (["decomp", "decompilation", "recomp", "port", "remastered"], "port-pc"),
        (["botw", "zelda", "cemu", "wiiu", "switch"], "nintendo"),
        (["halo", "mcc", "mccvr"], "halo"),
        (["bioshock"], "bioshock"),
        (["bloodborne"], "bloodborne"),
        (["ctr", "crash", "nitro"], "crash-team-racing"),
        (["fear"], "fear"),
        (["max-payne", "maxpayne"], "max-payne"),
    ]
    for kw_group, tag_val in keyword_map:
        if any(kw in text for kw in kw_group):
            add_tag(tag_val)

    if len(tags_list) < 2:
        for part in re.split(r"[-_.\s]+", name.lower()):
            if len(part) >= 3 and part not in ("the", "for", "and", "build"):
                add_tag(part)

    suggested_category = "Generale"

    def find_existing_cat(candidates: List[str], fallback: str) -> str:
        for ex in existing_categories:
            if ex.lower() in [c.lower() for c in candidates]:
                return ex
        return fallback

    if any(k in text for k in ["vr", "openxr", "openvr", "steamvr", "mccvr", "bettervr", "biovr", "alyx"]):
        suggested_category = find_existing_cat(["MOD VR", "VR", "Mod VR"], "MOD VR")
    elif any(k in text for k in ["emu", "emulator", "emulation", "anyps5", "kyty", "shadps4", "rpcs3", "cemu", "yuzu", "ryujinx"]):
        suggested_category = find_existing_cat(["Emulatore", "Emulatori", "Emulator"], "Emulatore")
    elif provider == "nexusmods":
        suggested_category = find_existing_cat(["Giochi", "MOD VR", "Mod"], "Giochi")
    elif any(k in text for k in ["pc", "game", "bloodborne", "ctr", "nitro", "port", "decomp", "recomp", "remastered", "play"]):
        suggested_category = find_existing_cat(["Giochi", "Games", "Gaming"], "Giochi")
    elif existing_categories:
        suggested_category = existing_categories[0]

    return {
        "category": suggested_category,
        "tags": ", ".join(tags_list),
    }


def log_activity(message: str, repo_name: str = "", level: str = "info") -> None:
    now = datetime.now(timezone.utc).isoformat()
    logger.info(f"[{repo_name or 'SYSTEM'}] {message}")
    try:
        conn = get_db()
        with conn:
            conn.execute(
                "INSERT INTO activity_log (created_at, level, repo_name, message) VALUES (?, ?, ?, ?)",
                (now, level, repo_name, message),
            )
            conn.execute(
                "DELETE FROM activity_log WHERE id NOT IN (SELECT id FROM activity_log ORDER BY id DESC LIMIT 500)"
            )
        conn.close()
    except Exception as e:
        logger.error(f"Failed to write activity log: {e}")


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name.strip())
    return cleaned or "unnamed"


def github_headers(token: Optional[str] = None) -> Dict[str, str]:
    if token is None:
        token = get_settings_dict().get("github_token", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "GitHub-Release-Vault/1.2",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def parse_source_input(raw: str) -> Dict[str, Any]:
    """Parse either a Nexus Mods URL/slug or a GitHub URL/slug."""
    s = raw.strip()
    # 1. Check Nexus Mods URL: https://www.nexusmods.com/<domain>/mods/<mod_id>
    m_nx = re.search(r"nexusmods\.com/([a-z0-9_-]+)/mods/(\d+)", s, re.I)
    if m_nx:
        return {
            "provider": "nexusmods",
            "domain": m_nx.group(1).lower(),
            "mod_id": int(m_nx.group(2)),
        }
    m_nx_short = re.match(r"^nexus:([a-z0-9_-]+)/(\d+)$", s, re.I)
    if m_nx_short:
        return {
            "provider": "nexusmods",
            "domain": m_nx_short.group(1).lower(),
            "mod_id": int(m_nx_short.group(2)),
        }

    # 2. Check GitHub URL or owner/repo
    s_clean = re.sub(r"\.git$", "", s.rstrip("/"))
    m_gh = re.search(r"github\.com[:/]([^/]+)/([^/\s#?]+)", s_clean, re.I)
    if m_gh:
        return {"provider": "github", "owner": m_gh.group(1), "name": m_gh.group(2)}

    parts = s_clean.split("/")
    if len(parts) == 2 and parts[0] and parts[1]:
        return {"provider": "github", "owner": parts[0].strip(), "name": parts[1].strip()}

    raise ValueError(
        "Formato link non valido. Inserisci un link GitHub (es. https://github.com/owner/repo) "
        "oppure un link Nexus Mods (es. https://www.nexusmods.com/gioco/mods/12345)."
    )


async def fetch_nexus_mod_info(domain: str, mod_id: int) -> Dict[str, Any]:
    """Fetch complete Nexus Mods metadata, game info, files, and changelogs using API v1 + GraphQL v2."""
    cfg = get_settings_dict()
    api_key = cfg.get("nexus_api_key", "").strip()

    def _sync_fetch():
        # 1. Query GraphQL v2 for game name, tags, category, and modFiles
        q_game = """
        query($domain: String!) {
          game(domainName: $domain) {
            id
            name
            domainName
          }
        }
        """
        r_g = cffi_requests.post(
            "https://api.nexusmods.com/v2/graphql",
            json={"query": q_game, "variables": {"domain": domain}},
            impersonate="chrome",
            timeout=20,
        ).json()
        game_obj = (r_g.get("data") or {}).get("game")
        if not game_obj:
            raise RuntimeError(f"Gioco '{domain}' non trovato su Nexus Mods.")
        game_id = int(game_obj["id"])
        game_name = game_obj["name"]

        q_mod = """
        query($gameId: ID!, $modId: ID!) {
          mod(gameId: $gameId, modId: $modId) {
            modId
            gameId
            name
            summary
            description
            author
            version
            pictureUrl
            endorsements
            category
            modCategory { name }
            tags { name }
          }
          modFiles(gameId: $gameId, modId: $modId) {
            fileId
            name
            version
            category
            categoryId
            changelogText
            description
            date
            sizeInBytes
            uri
            primary
          }
        }
        """
        r_m = cffi_requests.post(
            "https://api.nexusmods.com/v2/graphql",
            json={"query": q_mod, "variables": {"gameId": str(game_id), "modId": str(mod_id)}},
            impersonate="chrome",
            timeout=25,
        ).json()
        mod_obj = (r_m.get("data") or {}).get("mod")
        if not mod_obj:
            raise RuntimeError(f"Mod #{mod_id} per '{game_name}' non trovata su Nexus Mods.")

        gql_files = (r_m.get("data") or {}).get("modFiles") or []

        # 2. Also fetch changelogs.json via v1 API if api_key is configured
        v1_changelogs: Dict[str, List[str]] = {}
        if api_key:
            try:
                r_chg = cffi_requests.get(
                    f"https://api.nexusmods.com/v1/games/{domain}/mods/{mod_id}/changelogs.json",
                    headers={"apikey": api_key, "Accept": "application/json"},
                    impersonate="chrome",
                    timeout=15,
                )
                if r_chg.status_code == 200 and isinstance(r_chg.json(), dict):
                    v1_changelogs = r_chg.json()
            except Exception:
                pass

        return {
            "game_id": game_id,
            "game_name": game_name,
            "domain": domain,
            "mod_id": mod_id,
            "mod": mod_obj,
            "files": gql_files,
            "changelogs": v1_changelogs,
        }

    return await asyncio.to_thread(_sync_fetch)


async def resolve_nexus_download_url(game_id: int, file_id: int, domain: str, mod_id: int) -> str:
    """Resolve direct CDN download URL for a Nexus Mods file (works with Free Account session + Premium API)."""
    cfg = get_settings_dict()
    sess = cfg.get("nexus_session_cookie", "").strip()
    api_key = cfg.get("nexus_api_key", "").strip()

    def _sync_resolve() -> str:
        # 1. Try GenerateDownloadUrl with Free/Member Session Cookie
        if sess:
            r = cffi_requests.post(
                "https://www.nexusmods.com/Core/Libs/Common/Managers/Downloads?GenerateDownloadUrl",
                data={"fid": str(file_id), "game_id": str(game_id)},
                cookies={"nexusmods_session": sess},
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": "https://www.nexusmods.com",
                    "Referer": f"https://www.nexusmods.com/{domain}/mods/{mod_id}?tab=files&file_id={file_id}",
                },
                impersonate="chrome",
                timeout=20,
            )
            # Update session cookie if rotated by Nexus Mods
            new_sess = r.cookies.get("nexusmods_session")
            if new_sess and new_sess != sess:
                set_setting("nexus_session_cookie", new_sess)

            if r.status_code == 200:
                try:
                    data = r.json()
                    if isinstance(data, dict) and data.get("url"):
                        return data["url"]
                except Exception:
                    pass

        # 2. Fallback: Try official API v1 download_link.json (if account is Premium)
        if api_key:
            r_api = cffi_requests.get(
                f"https://api.nexusmods.com/v1/games/{domain}/mods/{mod_id}/files/{file_id}/download_link.json",
                headers={"apikey": api_key, "Accept": "application/json"},
                impersonate="chrome",
                timeout=15,
            )
            if r_api.status_code == 200:
                links = r_api.json()
                if isinstance(links, list) and len(links) > 0 and links[0].get("URI"):
                    return links[0]["URI"]

        raise RuntimeError(
            "Impossibile generare il link di download da Nexus Mods. Verifica che il cookie 'nexusmods_session' nelle Impostazioni sia valido."
        )

    # Polite 1.5s delay to respect Nexus Mods Free tier
    await asyncio.sleep(1.5)
    return await asyncio.to_thread(_sync_resolve)


async def send_notifications(
    repo_full_name: str,
    release_tag: str,
    release_name: str,
    prerelease: bool,
    body: str,
    html_url: str,
    files_count: int,
    total_size: int,
    provider: str = "github",
) -> None:
    cfg = get_settings_dict()
    source_label = "NEXUS MODS" if provider == "nexusmods" else "GITHUB"
    badge = "🧪 Pre-Release / Update" if prerelease else "✅ Main / Stable Release"
    size_mb = f"{total_size / (1024 * 1024):.2f} MB"
    short_body = (body or "Nessuna patch note fornita.").strip()
    if len(short_body) > 900:
        short_body = short_body[:900] + "\n... [Troncato]"

    # 1. Discord Webhook
    discord_url = cfg.get("discord_webhook_url", "").strip()
    if discord_url:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                payload = {
                    "username": "Release Vault",
                    "embeds": [
                        {
                            "title": f"📦 [{source_label}] Nuova Release: {repo_full_name} ({release_tag})",
                            "url": html_url,
                            "color": 14250283 if provider == "nexusmods" else (16753920 if prerelease else 3066993),
                            "fields": [
                                {"name": "Versione", "value": f"`{release_tag}` ({release_name or release_tag})", "inline": True},
                                {"name": "Canale", "value": badge, "inline": True},
                                {"name": "File Salvati", "value": f"{files_count} file ({size_mb})", "inline": True},
                            ],
                            "description": f"**Patch Notes:**\n```\n{short_body[:700]}\n```",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    ],
                }
                await client.post(discord_url, json=payload)
        except Exception as e:
            log_activity(f"Errore invio notifica Discord: {e}", repo_full_name, "error")

    # 2. Telegram Bot Notification
    tg_token = cfg.get("telegram_bot_token", "").strip()
    tg_chat = cfg.get("telegram_chat_id", "").strip()
    if tg_token and tg_chat:
        try:
            safe_repo = html_lib.escape(repo_full_name)
            safe_tag = html_lib.escape(release_tag)
            safe_name = html_lib.escape(release_name or release_tag)
            safe_body = html_lib.escape(short_body[:700])
            text = (
                f"📦 <b>[{source_label}] Nuova Release Archiviata</b>\n\n"
                f"🔹 <b>Progetto:</b> <code>{safe_repo}</code>\n"
                f"🏷 <b>Versione:</b> <code>{safe_tag}</code> ({safe_name})\n"
                f"📡 <b>Canale:</b> {badge}\n"
                f"💾 <b>Archivio:</b> {files_count} file ({size_mb})\n\n"
                f"📝 <b>Patch Notes / Changelog:</b>\n<pre>{safe_body}</pre>\n\n"
                f"🔗 <a href=\"{html_url}\">Pagina Originale</a>"
            )
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(
                    f"https://api.telegram.org/bot{tg_token}/sendMessage",
                    json={
                        "chat_id": tg_chat,
                        "text": text,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
        except Exception as e:
            log_activity(f"Errore invio notifica Telegram: {e}", repo_full_name, "error")

    # 3. Email SMTP
    smtp_host = cfg.get("smtp_host", "").strip()
    smtp_to = cfg.get("smtp_to", "").strip()
    if smtp_host and smtp_to:
        try:
            def _send_mail():
                msg = MIMEMultipart()
                msg["From"] = cfg.get("smtp_from") or cfg.get("smtp_user") or "vault@localhost"
                msg["To"] = smtp_to
                msg["Subject"] = f"[Vault {source_label}] Nuova release salvata: {repo_full_name} {release_tag}"
                mail_text = (
                    f"Nuova Release Archiviata nel tuo Vault!\n\n"
                    f"Sorgente: {source_label}\n"
                    f"Progetto: {repo_full_name}\n"
                    f"Versione: {release_tag} ({badge})\n"
                    f"File scaricati: {files_count} ({size_mb})\n"
                    f"URL: {html_url}\n\n"
                    f"--- PATCH NOTES ---\n{body or 'Nessuna nota.'}\n"
                )
                msg.attach(MIMEText(mail_text, "plain", "utf-8"))
                port = int(cfg.get("smtp_port", "587") or 587)
                with smtplib.SMTP(smtp_host, port, timeout=15) as server:
                    server.ehlo()
                    if port in (587, 25):
                        try:
                            server.starttls()
                        except Exception:
                            pass
                    if cfg.get("smtp_user") and cfg.get("smtp_password"):
                        server.login(cfg["smtp_user"], cfg["smtp_password"])
                    server.send_message(msg)

            await asyncio.to_thread(_send_mail)
        except Exception as e:
            log_activity(f"Errore invio Email SMTP: {e}", repo_full_name, "error")


def write_release_disk_metadata(release_row: sqlite3.Row, repo_row: sqlite3.Row, assets_list: List[sqlite3.Row]) -> None:
    folder = Path(release_row["folder_path"])
    folder.mkdir(parents=True, exist_ok=True)

    md_path = folder / "PATCH_NOTES.md"
    badge = "PRE-RELEASE / UPDATE / OLD" if release_row["prerelease"] else "MAIN / STABLE RELEASE"
    md_content = (
        f"# {repo_row['full_name']} — {release_row['name'] or release_row['tag_name']}\n\n"
        f"- **Sorgente:** `{repo_row['provider'].upper()}`\n"
        f"- **Tag Versione:** `{release_row['tag_name']}`\n"
        f"- **Categoria:** `{repo_row['category']}`\n"
        f"- **Tag:** `{repo_row['tags']}`\n"
        f"- **Canale:** {badge}\n"
        f"- **Data Pubblicazione:** {release_row['published_at']}\n"
        f"- **Autore:** {release_row['author'] or 'N/A'}\n"
        f"- **URL Originale:** {release_row['html_url']}\n\n"
        f"---\n\n"
        f"## Patch Notes / Changelog\n\n"
        f"{release_row['body'] or '*Nessuna patch note specificata per questa release.*'}\n\n"
        f"---\n\n"
        f"## File Archiviati & Checksum SHA256\n\n"
    )
    for a in assets_list:
        size_mb = f"{(a['size'] or 0) / (1024 * 1024):.2f} MB"
        md_content += f"- **{a['name']}** ({size_mb}) — SHA256: `{a['sha256'] or 'in calcolo...'}`\n"

    md_path.write_text(md_content, encoding="utf-8")

    meta_path = folder / "release-metadata.json"
    meta_data = {
        "provider": repo_row["provider"],
        "repository": repo_row["full_name"],
        "category": repo_row["category"],
        "tags": repo_row["tags"],
        "tag_name": release_row["tag_name"],
        "release_name": release_row["name"],
        "prerelease": bool(release_row["prerelease"]),
        "published_at": release_row["published_at"],
        "downloaded_at": release_row["downloaded_at"],
        "author": release_row["author"],
        "html_url": release_row["html_url"],
        "patch_notes": release_row["body"],
        "assets": [
            {
                "name": a["name"],
                "type": a["asset_type"],
                "size": a["size"],
                "sha256": a["sha256"],
                "status": a["status"],
            }
            for a in assets_list
        ],
    }
    meta_path.write_text(json.dumps(meta_data, indent=2, ensure_ascii=False), encoding="utf-8")


async def enqueue_unpaused_releases(repo_id: Optional[int] = None) -> int:
    if GLOBAL_PAUSED:
        return 0
    conn = get_db()
    sql = """
        SELECT rel.id
        FROM releases rel
        JOIN repositories r ON r.id = rel.repo_id
        WHERE rel.status IN ('pending', 'downloading', 'partial')
          AND COALESCE(r.paused, 0) = 0
    """
    params: List[Any] = []
    if repo_id is not None:
        sql += " AND r.id = ?"
        params.append(repo_id)
    sql += " ORDER BY rel.published_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    added = 0
    for r in rows:
        rid = r["id"]
        if rid not in QUEUED_RELEASES and rid not in ACTIVE_DOWNLOADS:
            QUEUED_RELEASES.add(rid)
            await DOWNLOAD_QUEUE.put({"release_id": rid, "notify": False})
            added += 1
    return added


async def download_single_asset(client: httpx.AsyncClient, asset_row: sqlite3.Row, release_id: int, repo_id: int, token: str) -> bool:
    if GLOBAL_PAUSED or (repo_id in PAUSED_REPOS):
        raise DownloadPausedException()

    asset_id = asset_row["id"]
    local_path = Path(asset_row["local_path"])
    local_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = local_path.with_suffix(local_path.suffix + ".part")

    if asset_row["status"] == "completed" and local_path.exists() and local_path.stat().st_size > 0:
        return True

    conn = get_db()
    with conn:
        conn.execute("UPDATE assets SET status='downloading' WHERE id=?", (asset_id,))
    conn.close()

    url = asset_row["download_url"]
    headers: Dict[str, str] = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        if url.startswith("nexus://"):
            # Format: nexus://{game_id}/{file_id}/{domain}/{mod_id}
            parts = url.replace("nexus://", "").split("/")
            game_id, file_id, domain, mod_id = int(parts[0]), int(parts[1]), parts[2], int(parts[3])
            url = await resolve_nexus_download_url(game_id, file_id, domain, mod_id)
        else:
            # Rewrite api.github.com zipball/tarball URLs when no token is used so they go to codeload.github.com (0 API rate limit!)
            if not token and "api.github.com/repos/" in url:
                m_src = re.match(r"https://api\.github\.com/repos/([^/]+/[^/]+)/(zipball|tarball)/(.+)$", url)
                if m_src:
                    r_slug, archive_kind, ref_name = m_src.group(1), m_src.group(2), m_src.group(3)
                    ext = "zip" if archive_kind == "zipball" else "tar.gz"
                    url = f"https://github.com/{r_slug}/archive/refs/tags/{ref_name}.{ext}"
            elif "github.com/" in url and "/archive/" in url and "/refs/" not in url:
                # Avoid HTTP 300 Multiple Choices when a repo has both a branch and a tag with the same name (e.g. v0.4)
                m_arch = re.match(r"https://github\.com/([^/]+/[^/]+)/archive/(.+)\.(zip|tar\.gz)$", url)
                if m_arch:
                    r_slug, ref_name, ext = m_arch.group(1), m_arch.group(2), m_arch.group(3)
                    if not re.fullmatch(r"[0-9a-f]{7,40}", ref_name):
                        url = f"https://github.com/{r_slug}/archive/refs/tags/{ref_name}.{ext}"
            headers = github_headers(token)
            if "api.github.com/repos/" in url and "/releases/assets/" in url:
                headers["Accept"] = "application/octet-stream"

        sha256_hash = hashlib.sha256()
        bytes_downloaded = 0

        async with client.stream("GET", url, headers=headers, follow_redirects=True, timeout=600.0) as resp:
            if resp.status_code in (300, 404) and "/archive/refs/tags/" in url:
                alt_url = url.replace("/archive/refs/tags/", "/archive/refs/heads/")
            else:
                alt_url = None
            if not alt_url:
                resp.raise_for_status()
                with open(temp_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        if GLOBAL_PAUSED or (repo_id in PAUSED_REPOS):
                            raise DownloadPausedException()
                        if chunk:
                            f.write(chunk)
                            sha256_hash.update(chunk)
                            bytes_downloaded += len(chunk)
                            if release_id in ACTIVE_DOWNLOADS:
                                ACTIVE_DOWNLOADS[release_id]["current_file"] = asset_row["name"]
                                ACTIVE_DOWNLOADS[release_id]["bytes_downloaded"] = bytes_downloaded
        if alt_url:
            async with client.stream("GET", alt_url, headers=headers, follow_redirects=True, timeout=600.0) as resp:
                resp.raise_for_status()
                with open(temp_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        if GLOBAL_PAUSED or (repo_id in PAUSED_REPOS):
                            raise DownloadPausedException()
                        if chunk:
                            f.write(chunk)
                            sha256_hash.update(chunk)
                            bytes_downloaded += len(chunk)
                            if release_id in ACTIVE_DOWNLOADS:
                                ACTIVE_DOWNLOADS[release_id]["current_file"] = asset_row["name"]
                                ACTIVE_DOWNLOADS[release_id]["bytes_downloaded"] = bytes_downloaded

        shutil.move(str(temp_path), str(local_path))
        digest = sha256_hash.hexdigest()
        now = datetime.now(timezone.utc).isoformat()

        conn = get_db()
        with conn:
            conn.execute(
                """
                UPDATE assets
                SET status='completed', size=?, sha256=?, downloaded_at=?
                WHERE id=?
                """,
                (bytes_downloaded, digest, now, asset_id),
            )
        conn.close()
        return True
    except DownloadPausedException:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        conn = get_db()
        with conn:
            conn.execute("UPDATE assets SET status='pending' WHERE id=?", (asset_id,))
        conn.close()
        raise
    except Exception as e:
        logger.error(f"Error downloading asset {asset_row['name']} from {url}: {e}")
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        conn = get_db()
        with conn:
            conn.execute("UPDATE assets SET status='error' WHERE id=?", (asset_id,))
        conn.close()
        return False


async def process_release_download(release_id: int, notify: bool = False) -> None:
    QUEUED_RELEASES.discard(release_id)
    if GLOBAL_PAUSED:
        return

    conn = get_db()
    release_row = conn.execute("SELECT * FROM releases WHERE id=?", (release_id,)).fetchone()
    if not release_row:
        conn.close()
        return
    repo_row = conn.execute("SELECT * FROM repositories WHERE id=?", (release_row["repo_id"],)).fetchone()
    assets_rows = conn.execute("SELECT * FROM assets WHERE release_id=? ORDER BY id ASC", (release_id,)).fetchall()
    conn.close()

    if not repo_row:
        return

    repo_id = repo_row["id"]
    if (repo_id in PAUSED_REPOS) or repo_row["paused"]:
        conn = get_db()
        with conn:
            conn.execute("UPDATE repositories SET status='paused' WHERE id=?", (repo_id,))
        conn.close()
        return

    ACTIVE_DOWNLOADS[release_id] = {
        "release_id": release_id,
        "repo_id": repo_id,
        "repo_full_name": repo_row["full_name"],
        "tag_name": release_row["tag_name"],
        "total_files": len(assets_rows),
        "completed_files": 0,
        "current_file": "",
        "bytes_downloaded": 0,
    }

    conn = get_db()
    with conn:
        conn.execute("UPDATE releases SET status='downloading', error_message='' WHERE id=?", (release_id,))
        conn.execute("UPDATE repositories SET status='downloading' WHERE id=?", (repo_id,))
    conn.close()

    token = get_settings_dict().get("github_token", "").strip()
    all_ok = True

    try:
        async with httpx.AsyncClient() as client:
            for idx, asset in enumerate(assets_rows):
                ACTIVE_DOWNLOADS[release_id]["completed_files"] = idx
                ACTIVE_DOWNLOADS[release_id]["current_file"] = asset["name"]
                ok = await download_single_asset(client, asset, release_id, repo_id, token)
                if not ok:
                    all_ok = False
    except DownloadPausedException:
        ACTIVE_DOWNLOADS.pop(release_id, None)
        conn = get_db()
        with conn:
            conn.execute("UPDATE releases SET status='pending' WHERE id=?", (release_id,))
            conn.execute(
                "UPDATE repositories SET status=? WHERE id=?",
                ("paused" if (repo_id in PAUSED_REPOS) else "idle", repo_id),
            )
        conn.close()
        return

    ACTIVE_DOWNLOADS.pop(release_id, None)

    conn = get_db()
    updated_assets = conn.execute("SELECT * FROM assets WHERE release_id=?", (release_id,)).fetchall()
    total_size = sum((a["size"] or 0) for a in updated_assets if a["status"] == "completed")
    now = datetime.now(timezone.utc).isoformat()
    final_status = "completed" if all_ok else "partial"

    with conn:
        conn.execute(
            "UPDATE releases SET status=?, total_size=?, downloaded_at=? WHERE id=?",
            (final_status, total_size, now, release_id),
        )
        rem = conn.execute(
            "SELECT COUNT(*) as c FROM releases WHERE repo_id=? AND status IN ('pending', 'downloading')",
            (repo_row["id"],),
        ).fetchone()["c"]
        if rem == 0:
            conn.execute("UPDATE repositories SET status='idle' WHERE id=?", (repo_row["id"],))

    updated_release = conn.execute("SELECT * FROM releases WHERE id=?", (release_id,)).fetchone()
    conn.close()

    try:
        write_release_disk_metadata(updated_release, repo_row, updated_assets)
    except Exception as e:
        logger.error(f"Failed writing disk metadata for {release_row['tag_name']}: {e}")

    log_activity(
        f"Release {release_row['tag_name']} archiviata ({len(updated_assets)} file, {total_size / (1024*1024):.2f} MB)",
        repo_row["full_name"],
        "success" if all_ok else "warning",
    )

    if notify and all_ok:
        await send_notifications(
            repo_full_name=repo_row["full_name"],
            release_tag=release_row["tag_name"],
            release_name=release_row["name"],
            prerelease=bool(release_row["prerelease"]),
            body=release_row["body"],
            html_url=release_row["html_url"],
            files_count=len(updated_assets),
            total_size=total_size,
            provider=repo_row["provider"] or "github",
        )


async def download_worker() -> None:
    while True:
        item = await DOWNLOAD_QUEUE.get()
        try:
            release_id = item["release_id"]
            notify = item.get("notify", False)
            await process_release_download(release_id, notify=notify)
        except Exception as e:
            logger.error(f"Worker error processing item {item}: {e}")
        finally:
            DOWNLOAD_QUEUE.task_done()


async def sync_nexus_mod_releases(repo_id: int, is_initial: bool = False) -> Dict[str, Any]:
    conn = get_db()
    repo = conn.execute("SELECT * FROM repositories WHERE id=?", (repo_id,)).fetchone()
    conn.close()
    if not repo:
        raise ValueError("Repository Nexus Mods non trovato")

    domain = repo["nexus_domain"] or repo["owner"]
    mod_id = int(repo["nexus_mod_id"] or 0)
    full_name = repo["full_name"]

    conn = get_db()
    with conn:
        conn.execute("UPDATE repositories SET status='checking', error_message='' WHERE id=?", (repo_id,))
    conn.close()

    try:
        nx_info = await fetch_nexus_mod_info(domain, mod_id)
    except Exception as e:
        err_msg = str(e)
        conn = get_db()
        with conn:
            conn.execute(
                "UPDATE repositories SET status='error', error_message=?, last_checked_at=? WHERE id=?",
                (err_msg, datetime.now(timezone.utc).isoformat(), repo_id),
            )
        conn.close()
        log_activity(f"Errore controllo Nexus Mods {full_name}: {err_msg}", full_name, "error")
        raise

    game_id = nx_info["game_id"]
    game_name = nx_info["game_name"]
    mod_obj = nx_info["mod"]
    all_files = nx_info["files"]
    v1_changelogs = nx_info["changelogs"]

    # Filter files: MAIN, UPDATE, OLD_VERSION (or fallback to all non-archived if empty)
    target_categories = {"MAIN", "UPDATE", "OLD_VERSION"}
    selected_files = [f for f in all_files if (f.get("category") or "").upper() in target_categories]
    if not selected_files:
        selected_files = [f for f in all_files if (f.get("category") or "").upper() in {"OPTIONAL", "MISCELLANEOUS"}]
    if not selected_files:
        selected_files = all_files

    # Sort files newest first by date
    selected_files.sort(key=lambda x: int(x.get("date") or 0), reverse=True)

    # Group files by version string so each version is a clean Release entry
    versions_map: Dict[str, List[Dict[str, Any]]] = {}
    for f in selected_files:
        ver_raw = str(f.get("version") or f.get("fileId") or "1.0").strip()
        tag_name = ver_raw if ver_raw.lower().startswith("v") else f"v{ver_raw}"
        versions_map.setdefault(tag_name, []).append(f)

    conn = get_db()
    existing_tags = {
        r["tag_name"]: r
        for r in conn.execute("SELECT id, tag_name, status FROM releases WHERE repo_id=?", (repo_id,)).fetchall()
    }

    repo_folder_name = f"nexus__{sanitize_filename(domain)}__{mod_id}"
    cfg = get_settings_dict()
    notify_initial = cfg.get("notify_on_initial_sync", "0") == "1"
    releases_to_queue: List[Dict[str, Any]] = []
    new_releases_queued = 0

    mod_desc_md = nexus_bbcode_to_markdown(mod_obj.get("description") or mod_obj.get("summary") or "")

    with conn:
        # Update repo metadata
        conn.execute(
            """
            UPDATE repositories
            SET name=?, description=?, avatar_url=?, stars=?, nexus_game_id=?, nexus_game_name=?
            WHERE id=?
            """,
            (
                mod_obj.get("name") or repo["name"],
                mod_obj.get("summary") or repo["description"] or "",
                mod_obj.get("pictureUrl") or repo["avatar_url"] or "",
                int(mod_obj.get("endorsements") or 0),
                game_id,
                game_name,
                repo_id,
            ),
        )

        versions_items = list(versions_map.items())
        if repo["only_latest"]:
            if not existing_tags:
                versions_items = versions_items[:1]
            else:
                filtered_items = []
                for t_name, f_list in versions_items:
                    if t_name in existing_tags:
                        if existing_tags[t_name]["status"] != "completed":
                            filtered_items.append((t_name, f_list))
                        break
                    filtered_items.append((t_name, f_list))
                versions_items = filtered_items

        for tag_name, files_in_ver in versions_items:
            if tag_name in existing_tags and existing_tags[tag_name]["status"] == "completed":
                continue

            primary_f = files_in_ver[0]
            raw_ver = str(primary_f.get("version") or "").strip()
            has_main = any((f.get("category") or "").upper() == "MAIN" for f in files_in_ver)
            is_prerelease = 0 if has_main else 1

            ts = int(primary_f.get("date") or time.time())
            published_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            author_name = mod_obj.get("author") or ""

            # Build comprehensive Markdown Patch Notes for this version
            body_parts: List[str] = [
                f"### 🎮 Gioco: **{game_name}** (`{domain}`)",
            ]
            # Changelogs from v1 API or GraphQL changelogText
            ver_changes: List[str] = []
            if raw_ver and raw_ver in v1_changelogs and v1_changelogs[raw_ver]:
                ver_changes.extend(v1_changelogs[raw_ver])
            for f in files_in_ver:
                for ct in f.get("changelogText") or []:
                    if ct and ct not in ver_changes:
                        ver_changes.append(ct)

            if ver_changes:
                body_parts.append("### 📋 Changelog di questa versione")
                for c_line in ver_changes:
                    body_parts.append(f"- {nexus_bbcode_to_markdown(c_line)}")

            body_parts.append("### 📁 File inclusi in questa versione")
            for f in files_in_ver:
                f_cat = f.get("category") or "MAIN"
                f_desc = nexus_bbcode_to_markdown(f.get("description") or "")
                body_parts.append(
                    f"- **[{f_cat}] {f.get('name')}** (`{f.get('uri') or f.get('name')}`)"
                    + (f"\n  > {f_desc}" if f_desc else "")
                )

            if mod_desc_md:
                body_parts.append("---\n### 📖 Descrizione Mod (Nexus Mods)\n" + mod_desc_md[:3000])

            full_body = "\n\n".join(body_parts)
            safe_tag = sanitize_filename(tag_name)
            rel_folder = ARCHIVE_DIR / repo_folder_name / safe_tag
            rel_folder.mkdir(parents=True, exist_ok=True)
            rel_html_url = f"https://www.nexusmods.com/{domain}/mods/{mod_id}?tab=files"

            if tag_name in existing_tags:
                release_id = existing_tags[tag_name]["id"]
            else:
                cur = conn.execute(
                    """
                    INSERT INTO releases (
                        repo_id, github_release_id, tag_name, name, body, prerelease, draft,
                        published_at, author, html_url, tarball_url, zipball_url, folder_path, status
                    ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, '', '', ?, 'pending')
                    """,
                    (
                        repo_id,
                        int(primary_f.get("fileId") or 0),
                        tag_name,
                        f"{primary_f.get('name')} ({tag_name})",
                        full_body,
                        is_prerelease,
                        published_at,
                        author_name,
                        rel_html_url,
                        str(rel_folder),
                    ),
                )
                release_id = cur.lastrowid

            assets_dir = rel_folder / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            for f in files_in_ver:
                fid = int(f.get("fileId") or 0)
                fname = sanitize_filename(f.get("uri") or f"{f.get('name')}-{fid}.zip")
                fsize = int(f.get("sizeInBytes") or 0)
                dl_url = f"nexus://{game_id}/{fid}/{domain}/{mod_id}"
                conn.execute(
                    """
                    INSERT OR IGNORE INTO assets (
                        release_id, github_asset_id, name, asset_type, size, download_url, local_path, status
                    ) VALUES (?, ?, ?, 'binary', ?, ?, ?, 'pending')
                    """,
                    (release_id, fid, fname, fsize, dl_url, str(assets_dir / fname)),
                )

            releases_to_queue.append(
                {
                    "release_id": release_id,
                    "notify": (not is_initial) or notify_initial,
                }
            )
            new_releases_queued += 1

        now_iso = datetime.now(timezone.utc).isoformat()
        is_paused = (repo_id in PAUSED_REPOS) or bool(repo["paused"])
        new_status = "paused" if is_paused else ("downloading" if (releases_to_queue and not GLOBAL_PAUSED) else "idle")
        conn.execute(
            "UPDATE repositories SET last_checked_at=?, status=?, error_message='' WHERE id=?",
            (now_iso, new_status, repo_id),
        )
    conn.close()

    if not GLOBAL_PAUSED and (repo_id not in PAUSED_REPOS):
        for item in releases_to_queue:
            rid = item["release_id"]
            if rid not in QUEUED_RELEASES and rid not in ACTIVE_DOWNLOADS:
                QUEUED_RELEASES.add(rid)
                await DOWNLOAD_QUEUE.put(item)

    if new_releases_queued > 0:
        log_activity(
            f"[Nexus Mods] Trovate {new_releases_queued} versioni per {full_name}",
            full_name,
            "info",
        )
    else:
        log_activity(f"[Nexus Mods] Nessuna nuova versione per {full_name}", full_name, "info")

    return {"queued_releases": new_releases_queued, "total_remote_releases": len(versions_map)}


async def fetch_github_web_fallback(client: httpx.AsyncClient, full_name: str, owner: str, only_latest: bool = False) -> List[Dict[str, Any]]:
    """Fallback that reads GitHub's public Atom feeds (releases.atom or commits/main.atom) + expanded_assets without using any API rate limit."""
    import urllib.parse
    import xml.etree.ElementTree as ET
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    results: List[Dict[str, Any]] = []

    # 1. Try releases.atom (public, unlimited)
    try:
        r_atom = await client.get(f"https://github.com/{full_name}/releases.atom", timeout=20.0)
        if r_atom.status_code == 200 and "<entry>" in r_atom.text:
            root = ET.fromstring(r_atom.text)
            entries = root.findall("atom:entry", ns)
            if only_latest:
                entries = entries[:1]
            for idx, entry in enumerate(entries):
                link_el = entry.find("atom:link", ns)
                href = link_el.attrib.get("href", "") if link_el is not None else ""
                tag_name = urllib.parse.unquote(href.split("/releases/tag/")[-1]) if "/releases/tag/" in href else f"v-{idx}"
                title = (entry.findtext("atom:title", default=tag_name, namespaces=ns) or tag_name).strip()
                updated = (entry.findtext("atom:updated", default="", namespaces=ns) or datetime.now(timezone.utc).isoformat()).strip()
                content_html = entry.findtext("atom:content", default="", namespaces=ns) or ""
                body_md = re.sub(r"<[^>]+>", "", html_lib.unescape(content_html)).strip()

                # Fetch binary release assets from expanded_assets/{tag_name} (also 0 API rate limit!)
                assets_list: List[Dict[str, Any]] = []
                try:
                    exp_resp = await client.get(
                        f"https://github.com/{full_name}/releases/expanded_assets/{urllib.parse.quote(tag_name)}",
                        timeout=15.0,
                    )
                    if exp_resp.status_code == 200:
                        for a_idx, m_dl in enumerate(re.finditer(r'href="(/[^"]+/releases/download/[^"]+)"', exp_resp.text)):
                            rel_dl = m_dl.group(1)
                            fname = urllib.parse.unquote(rel_dl.split("/")[-1])
                            assets_list.append(
                                {
                                    "id": 700000000 + (idx * 100) + a_idx,
                                    "name": fname,
                                    "size": 0,
                                    "browser_download_url": f"https://github.com{rel_dl}",
                                    "url": f"https://github.com{rel_dl}",
                                }
                            )
                except Exception:
                    pass

                results.append(
                    {
                        "id": 800000000 + idx,
                        "tag_name": tag_name,
                        "name": title,
                        "body": body_md,
                        "prerelease": False,
                        "draft": False,
                        "published_at": updated,
                        "author": {"login": owner},
                        "html_url": href or f"https://github.com/{full_name}/releases/tag/{tag_name}",
                        "tarball_url": f"https://github.com/{full_name}/archive/{tag_name}.tar.gz",
                        "zipball_url": f"https://github.com/{full_name}/archive/{tag_name}.zip",
                        "assets": assets_list,
                    }
                )
    except Exception as e:
        logger.warning(f"Atom releases fallback warning for {full_name}: {e}")

    if results:
        return results

    # 2. If repository has no releases/tags at all (only branch commits, e.g. Driveclub-Port), archive latest commit snapshot
    for branch in ("main", "master"):
        try:
            c_atom = await client.get(f"https://github.com/{full_name}/commits/{branch}.atom", timeout=20.0)
            if c_atom.status_code == 200 and "<entry>" in c_atom.text:
                root = ET.fromstring(c_atom.text)
                entries = root.findall("atom:entry", ns)
                if entries:
                    latest_e = entries[0]
                    link_el = latest_e.find("atom:link", ns)
                    href = link_el.attrib.get("href", "") if link_el is not None else ""
                    commit_sha = href.rstrip("/").split("/")[-1] if "/commit/" in href else branch
                    short_sha = commit_sha[:7]
                    tag_name = f"{branch}-{short_sha}"
                    updated = (latest_e.findtext("atom:updated", default="", namespaces=ns) or datetime.now(timezone.utc).isoformat()).strip()

                    commit_lines = [f"### 🌿 Snapshot Branch `{branch}` (Commit `{short_sha}`)\n"]
                    for e in entries[:10]:
                        c_title = (e.findtext("atom:title", default="", namespaces=ns) or "").strip()
                        c_date = (e.findtext("atom:updated", default="", namespaces=ns) or "")[:10]
                        if c_title:
                            commit_lines.append(f"- **[{c_date}]** {c_title}")

                    results.append(
                        {
                            "id": 850000000,
                            "tag_name": tag_name,
                            "name": f"Snapshot {branch} ({short_sha})",
                            "body": "\n".join(commit_lines),
                            "prerelease": False,
                            "draft": False,
                            "published_at": updated,
                            "author": {"login": owner},
                            "html_url": href or f"https://github.com/{full_name}/commits/{branch}",
                            "tarball_url": f"https://github.com/{full_name}/archive/{commit_sha}.tar.gz",
                            "zipball_url": f"https://github.com/{full_name}/archive/{commit_sha}.zip",
                            "assets": [],
                        }
                    )
                    break
        except Exception:
            pass

    return results


async def sync_repository_releases(repo_id: int, is_initial: bool = False) -> Dict[str, Any]:
    conn = get_db()
    repo = conn.execute("SELECT * FROM repositories WHERE id=?", (repo_id,)).fetchone()
    conn.close()
    if not repo:
        raise ValueError("Repository non trovato")

    if (repo_id in PAUSED_REPOS) or repo["paused"]:
        return {"queued_releases": 0, "status": "paused"}

    if (repo["provider"] or "github") == "nexusmods":
        return await sync_nexus_mod_releases(repo_id, is_initial=is_initial)

    cfg = get_settings_dict()
    token = cfg.get("github_token", "").strip()
    headers = github_headers(token)
    full_name = repo["full_name"]

    conn = get_db()
    existing_tags = {
        r["tag_name"]: r
        for r in conn.execute("SELECT id, tag_name, status FROM releases WHERE repo_id=?", (repo_id,)).fetchall()
    }
    with conn:
        conn.execute("UPDATE repositories SET status='checking', error_message='' WHERE id=?", (repo_id,))
    conn.close()

    all_gh_releases: List[Dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            if not repo["avatar_url"] or not repo["description"]:
                repo_resp = await client.get(f"https://api.github.com/repos/{full_name}", headers=headers)
                if repo_resp.status_code == 200:
                    rdata = repo_resp.json()
                    desc = rdata.get("description") or repo["description"] or ""
                    topics = rdata.get("topics") or []
                    lang = rdata.get("language") or ""
                    current_tags = (repo["tags"] or "").strip()
                    if not current_tags:
                        classified = auto_classify_repo(repo["owner"], repo["name"], desc, topics, lang)
                        current_tags = classified["tags"]

                    conn = get_db()
                    with conn:
                        conn.execute(
                            "UPDATE repositories SET description=?, stars=?, avatar_url=?, tags=? WHERE id=?",
                            (
                                desc,
                                rdata.get("stargazers_count", 0),
                                (rdata.get("owner") or {}).get("avatar_url", ""),
                                current_tags,
                                repo_id,
                            ),
                        )
                    conn.close()

            page = 1
            rate_limited = False
            while True:
                resp = await client.get(
                    f"https://api.github.com/repos/{full_name}/releases",
                    headers=headers,
                    params={"per_page": 100, "page": page},
                )
                if resp.status_code == 404:
                    raise RuntimeError(f"Repository {full_name} non trovato o privato (aggiungi un GitHub Token se privato).")
                if resp.status_code == 403 and "rate limit" in resp.text.lower():
                    rate_limited = True
                    break
                resp.raise_for_status()
                batch = resp.json()
                if not batch:
                    break
                all_gh_releases.extend(batch)
                if len(batch) < 100 or repo["only_latest"]:
                    break
                page += 1

            if not all_gh_releases and not rate_limited:
                tags_resp = await client.get(
                    f"https://api.github.com/repos/{full_name}/tags",
                    headers=headers,
                    params={"per_page": 100},
                )
                if tags_resp.status_code == 200:
                    tags_data = tags_resp.json()
                    for idx, t in enumerate(tags_data):
                        tag_name = t["name"]
                        all_gh_releases.append(
                            {
                                "id": 900000000 + idx,
                                "tag_name": tag_name,
                                "name": f"{tag_name}",
                                "body": f"Tag Git `{tag_name}` (Commit SHA: `{t.get('commit', {}).get('sha', '')}`).",
                                "prerelease": False,
                                "draft": False,
                                "published_at": datetime.now(timezone.utc).isoformat(),
                                "author": {"login": repo["owner"]},
                                "html_url": f"https://github.com/{full_name}/releases/tag/{tag_name}",
                                "tarball_url": f"https://github.com/{full_name}/archive/{tag_name}.tar.gz",
                                "zipball_url": f"https://github.com/{full_name}/archive/{tag_name}.zip",
                                "assets": [],
                            }
                        )

            if not all_gh_releases:
                # Use web/Atom fallback (either because API is rate-limited OR because repo has no releases/tags yet, only commits)
                if rate_limited and existing_tags:
                    # We already have releases in DB; restore normal status without overwriting with error
                    rem_count = sum(1 for r in existing_tags.values() if r["status"] in ("pending", "downloading"))
                    fallback_st = "downloading" if rem_count > 0 else "idle"
                    conn = get_db()
                    with conn:
                        conn.execute("UPDATE repositories SET status=?, error_message='' WHERE id=?", (fallback_st, repo_id))
                    conn.close()
                    return {"queued_releases": 0, "status": fallback_st}

                all_gh_releases = await fetch_github_web_fallback(
                    client, full_name, repo["owner"], only_latest=bool(repo["only_latest"])
                )
    except Exception as e:
        err_msg = str(e)
        conn = get_db()
        with conn:
            conn.execute(
                "UPDATE repositories SET status='error', error_message=?, last_checked_at=? WHERE id=?",
                (err_msg, datetime.now(timezone.utc).isoformat(), repo_id),
            )
        conn.close()
        log_activity(f"Errore controllo {full_name}: {err_msg}", full_name, "error")
        raise

    new_releases_queued = 0
    asset_regex = None
    if repo["asset_filter"] and repo["asset_filter"].strip():
        try:
            asset_regex = re.compile(repo["asset_filter"].strip(), re.IGNORECASE)
        except re.error:
            asset_regex = None

    conn = get_db()
    repo_folder_name = f"{sanitize_filename(repo['owner'])}__{sanitize_filename(repo['name'])}"
    notify_initial = cfg.get("notify_on_initial_sync", "0") == "1"

    releases_to_queue: List[Dict[str, Any]] = []

    valid_gh_releases = [
        rel
        for rel in all_gh_releases
        if not rel.get("draft") and (repo["include_prereleases"] or not rel.get("prerelease"))
    ]
    if repo["only_latest"]:
        if not existing_tags:
            valid_gh_releases = valid_gh_releases[:1]
        else:
            filtered_gh = []
            for rel in valid_gh_releases:
                t_name = rel.get("tag_name") or "untagged"
                if t_name in existing_tags:
                    if existing_tags[t_name]["status"] != "completed":
                        filtered_gh.append(rel)
                    break
                filtered_gh.append(rel)
            valid_gh_releases = filtered_gh

    with conn:
        for rel in valid_gh_releases:
            tag_name = rel.get("tag_name") or "untagged"
            if tag_name in existing_tags and existing_tags[tag_name]["status"] == "completed":
                continue

            safe_tag = sanitize_filename(tag_name)
            rel_folder = ARCHIVE_DIR / repo_folder_name / safe_tag
            rel_folder.mkdir(parents=True, exist_ok=True)

            published_at = rel.get("published_at") or rel.get("created_at") or datetime.now(timezone.utc).isoformat()
            author_login = (rel.get("author") or {}).get("login") or ""

            if tag_name in existing_tags:
                release_id = existing_tags[tag_name]["id"]
            else:
                cur = conn.execute(
                    """
                    INSERT INTO releases (
                        repo_id, github_release_id, tag_name, name, body, prerelease, draft,
                        published_at, author, html_url, tarball_url, zipball_url, folder_path, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                    """,
                    (
                        repo_id,
                        rel.get("id") or 0,
                        tag_name,
                        rel.get("name") or tag_name,
                        rel.get("body") or "",
                        1 if rel.get("prerelease") else 0,
                        0,
                        published_at,
                        author_login,
                        rel.get("html_url") or f"https://github.com/{full_name}/releases/tag/{tag_name}",
                        rel.get("tarball_url") or "",
                        rel.get("zipball_url") or "",
                        str(rel_folder),
                    ),
                )
                release_id = cur.lastrowid

            assets_dir = rel_folder / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            for a in rel.get("assets") or []:
                aname = sanitize_filename(a.get("name") or "asset.bin")
                if asset_regex and not asset_regex.search(aname):
                    continue
                dl_url = a.get("url") if token else (a.get("browser_download_url") or a.get("url"))
                if not dl_url:
                    continue
                conn.execute(
                    """
                    INSERT OR IGNORE INTO assets (
                        release_id, github_asset_id, name, asset_type, size, download_url, local_path, status
                    ) VALUES (?, ?, ?, 'binary', ?, ?, ?, 'pending')
                    """,
                    (
                        release_id,
                        a.get("id") or 0,
                        aname,
                        a.get("size") or 0,
                        dl_url,
                        str(assets_dir / aname),
                    ),
                )

            if repo["download_source"]:
                src_dir = rel_folder / "source"
                src_dir.mkdir(parents=True, exist_ok=True)
                if token:
                    zip_url = rel.get("zipball_url") or f"https://api.github.com/repos/{full_name}/zipball/{tag_name}"
                    tar_url = rel.get("tarball_url") or f"https://api.github.com/repos/{full_name}/tarball/{tag_name}"
                else:
                    zip_url = f"https://github.com/{full_name}/archive/{tag_name}.zip"
                    tar_url = f"https://github.com/{full_name}/archive/{tag_name}.tar.gz"
                    if rel.get("zipball_url") and "github.com/" in rel["zipball_url"] and "api.github.com" not in rel["zipball_url"]:
                        zip_url = rel["zipball_url"]
                    if rel.get("tarball_url") and "github.com/" in rel["tarball_url"] and "api.github.com" not in rel["tarball_url"]:
                        tar_url = rel["tarball_url"]
                zip_name = f"{sanitize_filename(repo['name'])}-{safe_tag}-source.zip"
                tar_name = f"{sanitize_filename(repo['name'])}-{safe_tag}-source.tar.gz"
                conn.execute(
                    """
                    INSERT OR IGNORE INTO assets (
                        release_id, github_asset_id, name, asset_type, size, download_url, local_path, status
                    ) VALUES (?, 0, ?, 'source_zip', 0, ?, ?, 'pending')
                    """,
                    (release_id, zip_name, zip_url, str(src_dir / zip_name)),
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO assets (
                        release_id, github_asset_id, name, asset_type, size, download_url, local_path, status
                    ) VALUES (?, 0, ?, 'source_tar', 0, ?, ?, 'pending')
                    """,
                    (release_id, tar_name, tar_url, str(src_dir / tar_name)),
                )

            releases_to_queue.append(
                {
                    "release_id": release_id,
                    "notify": (not is_initial) or notify_initial,
                }
            )
            new_releases_queued += 1

        now_iso = datetime.now(timezone.utc).isoformat()
        is_paused = (repo_id in PAUSED_REPOS) or bool(repo["paused"])
        new_status = "paused" if is_paused else ("downloading" if (releases_to_queue and not GLOBAL_PAUSED) else "idle")
        conn.execute(
            "UPDATE repositories SET last_checked_at=?, status=?, error_message='' WHERE id=?",
            (now_iso, new_status, repo_id),
        )
    conn.close()

    if not GLOBAL_PAUSED and (repo_id not in PAUSED_REPOS):
        for item in releases_to_queue:
            rid = item["release_id"]
            if rid not in QUEUED_RELEASES and rid not in ACTIVE_DOWNLOADS:
                QUEUED_RELEASES.add(rid)
                await DOWNLOAD_QUEUE.put(item)

    if new_releases_queued > 0:
        log_activity(
            f"Trovate e messe in coda {new_releases_queued} release per {full_name}",
            full_name,
            "info",
        )
    else:
        log_activity(f"Nessuna nuova release per {full_name} (già aggiornato)", full_name, "info")

    return {"queued_releases": new_releases_queued, "total_remote_releases": len(all_gh_releases)}


async def check_all_repositories() -> Dict[str, Any]:
    global LAST_CHECK_TIME
    if GLOBAL_PAUSED:
        return {"status": "global_paused"}
    if CHECK_LOCK.locked():
        return {"status": "already_running"}

    async with CHECK_LOCK:
        LAST_CHECK_TIME = datetime.now(timezone.utc).isoformat()
        conn = get_db()
        repos = conn.execute("SELECT id, full_name, COALESCE(paused, 0) as paused FROM repositories ORDER BY id ASC").fetchall()
        conn.close()

        total_queued = 0
        errors = 0
        for r in repos:
            if GLOBAL_PAUSED:
                break
            if r["paused"] or (r["id"] in PAUSED_REPOS):
                continue
            try:
                res = await sync_repository_releases(r["id"], is_initial=False)
                total_queued += res.get("queued_releases", 0)
            except Exception:
                errors += 1
        return {"checked_repos": len(repos), "queued_releases": total_queued, "errors": errors}


def backfill_empty_repo_tags() -> None:
    conn = get_db()
    existing_cats = get_existing_categories()
    rows = conn.execute("SELECT id, owner, name, description, tags, provider, nexus_game_name FROM repositories").fetchall()
    with conn:
        for r in rows:
            if not (r["tags"] or "").strip():
                classified = auto_classify_repo(
                    r["owner"],
                    r["name"],
                    r["description"] or "",
                    [],
                    "",
                    existing_cats,
                    provider=r["provider"] or "github",
                    game_name=r["nexus_game_name"] or "",
                )
                conn.execute("UPDATE repositories SET tags=? WHERE id=?", (classified["tags"], r["id"]))
    conn.close()


async def periodic_scheduler() -> None:
    global NEXT_CHECK_TIME
    conn = get_db()
    with conn:
        conn.execute("UPDATE assets SET status='pending' WHERE status='downloading'")
    conn.close()
    await enqueue_unpaused_releases()

    while True:
        cfg = get_settings_dict()
        try:
            interval_min = max(5, int(cfg.get("check_interval_minutes", "60") or 60))
        except ValueError:
            interval_min = 60

        next_ts = time.time() + (interval_min * 60)
        NEXT_CHECK_TIME = datetime.fromtimestamp(next_ts, tz=timezone.utc).isoformat()
        await asyncio.sleep(interval_min * 60)
        if not GLOBAL_PAUSED:
            try:
                await check_all_repositories()
            except Exception as e:
                logger.error(f"Periodic check error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    backfill_empty_repo_tags()
    workers = [asyncio.create_task(download_worker()) for _ in range(2)]
    scheduler_task = asyncio.create_task(periodic_scheduler())
    log_activity("Release Vault avviato e pronto.", "SYSTEM", "info")
    yield
    scheduler_task.cancel()
    for w in workers:
        w.cancel()


app = FastAPI(title="Release Vault", lifespan=lifespan)


# --- Auth Dependency (Allows localhost internal calls from Telegram Bot) ---
def require_auth(request: Request) -> str:
    if request.client and request.client.host in ("127.0.0.1", "::1"):
        internal_hdr = request.headers.get("X-Internal-Bot", "")
        if internal_hdr == "release-vault-bot":
            return "internal_bot"
    token = request.cookies.get("vault_session") or request.headers.get("X-Vault-Token", "")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non autenticato")
    if token not in SESSIONS:
        if re.fullmatch(r"[0-9a-f]{64}", token):
            SESSIONS[token] = time.time()
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non autenticato")
    return token


# --- Pydantic Schemas ---
class LoginRequest(BaseModel):
    username: str
    password: str


class AddRepoRequest(BaseModel):
    repo_input: str
    category: str = ""
    tags: str = ""
    include_prereleases: bool = True
    download_source: bool = True
    only_latest: bool = False
    asset_filter: str = ""


class UpdateRepoRequest(BaseModel):
    category: str = "Generale"
    tags: str = ""
    include_prereleases: bool = True
    download_source: bool = True
    only_latest: bool = False
    asset_filter: str = ""


class UpdateSettingsRequest(BaseModel):
    github_token: Optional[str] = None
    check_interval_minutes: Optional[str] = None
    notify_on_initial_sync: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    nexus_username: Optional[str] = None
    nexus_password: Optional[str] = None
    nexus_api_key: Optional[str] = None
    nexus_session_cookie: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[str] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_to: Optional[str] = None
    new_username: Optional[str] = None
    new_password: Optional[str] = None
    language: Optional[str] = None


class SetupWizardRequest(BaseModel):
    language: str = "it"
    admin_username: Optional[str] = None
    admin_password: Optional[str] = None
    github_token: Optional[str] = None
    check_interval_minutes: Optional[str] = None
    nexus_username: Optional[str] = None
    nexus_api_key: Optional[str] = None
    nexus_session_cookie: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_webhook_url: Optional[str] = None


# --- Auth & First-Run Setup Endpoints ---
@app.post("/api/setup/complete")
async def api_complete_setup(req: SetupWizardRequest, request: Request, response: Response):
    cfg = get_settings_dict()
    is_setup_done = cfg.get("setup_completed", "0") == "1"
    if is_setup_done:
        # Require auth if initial setup was already completed
        require_auth(request)

    if req.language:
        set_setting("language", req.language.strip())
    if req.admin_username and req.admin_username.strip():
        set_setting("auth_username", req.admin_username.strip())
    if req.admin_password and req.admin_password.strip():
        set_setting("auth_password_hash", hash_password(req.admin_password.strip()))
    if req.github_token is not None and req.github_token.strip() and req.github_token != "__KEEP__":
        set_setting("github_token", req.github_token.strip())
    if req.check_interval_minutes:
        set_setting("check_interval_minutes", str(max(5, int(req.check_interval_minutes or 60))))
    if req.nexus_username is not None and req.nexus_username.strip():
        set_setting("nexus_username", req.nexus_username.strip())
    if req.nexus_api_key is not None and req.nexus_api_key.strip() and req.nexus_api_key != "__KEEP__":
        set_setting("nexus_api_key", req.nexus_api_key.strip())
    if req.nexus_session_cookie is not None and req.nexus_session_cookie.strip() and req.nexus_session_cookie != "__KEEP__":
        set_setting("nexus_session_cookie", req.nexus_session_cookie.strip())
    if req.telegram_bot_token is not None and req.telegram_bot_token.strip():
        set_setting("telegram_bot_token", req.telegram_bot_token.strip())
    if req.telegram_chat_id is not None and req.telegram_chat_id.strip():
        set_setting("telegram_chat_id", req.telegram_chat_id.strip())
    if req.discord_webhook_url is not None and req.discord_webhook_url.strip():
        set_setting("discord_webhook_url", req.discord_webhook_url.strip())

    set_setting("setup_completed", "1")

    session_token = hashlib.sha256(f"{time.time()}:{os.urandom(16).hex()}".encode()).hexdigest()
    SESSIONS[session_token] = time.time()
    response.set_cookie(
        key="vault_session",
        value=session_token,
        httponly=True,
        max_age=86400 * 30,
        samesite="lax",
    )
    log_activity("Configurazione guidata (Setup Wizard) completata.", "SYSTEM", "success")
    return {"ok": True}


@app.post("/api/auth/login")
async def api_login(req: LoginRequest, response: Response):
    cfg = get_settings_dict()
    expected_user = cfg.get("auth_username", "admin")
    expected_hash = cfg.get("auth_password_hash", hash_password("admin"))

    if req.username.strip() == expected_user and hash_password(req.password) == expected_hash:
        session_token = hashlib.sha256(f"{time.time()}:{os.urandom(16).hex()}".encode()).hexdigest()
        SESSIONS[session_token] = time.time()
        response.set_cookie(
            key="vault_session",
            value=session_token,
            httponly=True,
            max_age=86400 * 30,
            samesite="lax",
        )
        return {"ok": True, "username": expected_user}
    raise HTTPException(status_code=401, detail="Credenziali non valide")


@app.post("/api/auth/logout")
async def api_logout(request: Request, response: Response):
    token = request.cookies.get("vault_session")
    if token and token in SESSIONS:
        SESSIONS.pop(token, None)
    response.delete_cookie("vault_session")
    return {"ok": True}


@app.get("/api/auth/me")
async def api_me(request: Request):
    cfg = get_settings_dict()
    setup_completed = cfg.get("setup_completed", "0") == "1"
    lang = cfg.get("language", "it")
    token = request.cookies.get("vault_session")
    if token and token not in SESSIONS and re.fullmatch(r"[0-9a-f]{64}", token):
        SESSIONS[token] = time.time()
    if not token or token not in SESSIONS:
        return {"authenticated": False, "setup_completed": setup_completed, "language": lang}
    return {
        "authenticated": True,
        "setup_completed": setup_completed,
        "language": lang,
        "username": cfg.get("auth_username", "admin"),
        "using_default_credentials": (
            cfg.get("auth_username") == "admin"
            and cfg.get("auth_password_hash") == hash_password("admin")
        ),
    }


# --- Smart Inspect Endpoint for Both GitHub and Nexus Mods ---
@app.get("/api/github/inspect", dependencies=[Depends(require_auth)])
async def api_inspect_source(repo: str = Query(...)):
    try:
        parsed = parse_source_input(repo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    existing_cats = get_existing_categories()

    if parsed["provider"] == "nexusmods":
        domain = parsed["domain"]
        mod_id = parsed["mod_id"]
        try:
            nx_info = await fetch_nexus_mod_info(domain, mod_id)
            mod_obj = nx_info["mod"]
            game_name = nx_info["game_name"]
            mod_name = mod_obj.get("name") or f"Mod #{mod_id}"
            summary = mod_obj.get("summary") or ""
            nx_tags = [t["name"] for t in (mod_obj.get("tags") or []) if t.get("name")]
            if mod_obj.get("category"):
                nx_tags.insert(0, mod_obj["category"])
            classified = auto_classify_repo(
                domain,
                mod_name,
                summary,
                nx_tags,
                "",
                existing_cats,
                provider="nexusmods",
                game_name=game_name,
            )
            return {
                "provider": "nexusmods",
                "owner": game_name,
                "name": mod_name,
                "full_name": f"{game_name} / {mod_name}",
                "description": summary,
                "stars": int(mod_obj.get("endorsements") or 0),
                "avatar_url": mod_obj.get("pictureUrl") or "",
                "suggested_category": classified["category"],
                "suggested_tags": classified["tags"],
                "existing_categories": existing_cats,
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # GitHub branch
    owner, name = parsed["owner"], parsed["name"]
    full_name = f"{owner}/{name}"
    cfg = get_settings_dict()
    headers = github_headers(cfg.get("github_token", ""))

    description = ""
    topics: List[str] = []
    language = ""
    stars = 0
    avatar_url = ""

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(f"https://api.github.com/repos/{full_name}", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                owner = data["owner"]["login"]
                name = data["name"]
                full_name = data["full_name"]
                description = data.get("description") or ""
                topics = data.get("topics") or []
                language = data.get("language") or ""
                stars = data.get("stargazers_count") or 0
                avatar_url = (data.get("owner") or {}).get("avatar_url") or ""
    except Exception:
        pass

    classified = auto_classify_repo(owner, name, description, topics, language, existing_cats, provider="github")
    return {
        "provider": "github",
        "owner": owner,
        "name": name,
        "full_name": full_name,
        "description": description,
        "stars": stars,
        "avatar_url": avatar_url,
        "suggested_category": classified["category"],
        "suggested_tags": classified["tags"],
        "existing_categories": existing_cats,
    }


# --- Dashboard & Overview ---
@app.get("/api/overview", dependencies=[Depends(require_auth)])
async def api_overview():
    conn = get_db()
    repos_count = conn.execute("SELECT COUNT(*) as c FROM repositories").fetchone()["c"]
    paused_repos_count = conn.execute("SELECT COUNT(*) as c FROM repositories WHERE COALESCE(paused, 0)=1").fetchone()["c"]
    releases_count = conn.execute("SELECT COUNT(*) as c FROM releases WHERE status='completed'").fetchone()["c"]
    total_releases = conn.execute("SELECT COUNT(*) as c FROM releases").fetchone()["c"]
    assets_count = conn.execute("SELECT COUNT(*) as c FROM assets WHERE status='completed'").fetchone()["c"]
    total_bytes = conn.execute("SELECT COALESCE(SUM(size), 0) as s FROM assets WHERE status='completed'").fetchone()["s"]
    recent_logs = [
        dict(r)
        for r in conn.execute("SELECT * FROM activity_log ORDER BY id DESC LIMIT 40").fetchall()
    ]
    conn.close()

    categories = get_existing_categories()
    disk_usage = shutil.disk_usage(ARCHIVE_DIR)

    return {
        "repositories_count": repos_count,
        "paused_repos_count": paused_repos_count,
        "global_paused": GLOBAL_PAUSED,
        "completed_releases": releases_count,
        "total_releases": total_releases,
        "completed_assets": assets_count,
        "archive_bytes": total_bytes,
        "disk_total": disk_usage.total,
        "disk_used": disk_usage.used,
        "disk_free": disk_usage.free,
        "categories": categories,
        "queue_size": DOWNLOAD_QUEUE.qsize(),
        "active_downloads": list(ACTIVE_DOWNLOADS.values()),
        "last_check_time": LAST_CHECK_TIME,
        "next_check_time": NEXT_CHECK_TIME,
        "recent_logs": recent_logs,
    }


@app.post("/api/pause-global", dependencies=[Depends(require_auth)])
async def api_toggle_global_pause(paused: Optional[bool] = Query(None)):
    global GLOBAL_PAUSED
    if paused is None:
        GLOBAL_PAUSED = not GLOBAL_PAUSED
    else:
        GLOBAL_PAUSED = bool(paused)

    set_setting("global_sync_paused", "1" if GLOBAL_PAUSED else "0")

    if GLOBAL_PAUSED:
        # Drain pending queue so workers stop immediately after current chunk aborts
        while not DOWNLOAD_QUEUE.empty():
            try:
                DOWNLOAD_QUEUE.get_nowait()
                DOWNLOAD_QUEUE.task_done()
            except Exception:
                break
        QUEUED_RELEASES.clear()
        log_activity("⏸ Sincronizzazione e download globali messi in PAUSA.", "SYSTEM", "warning")
    else:
        added = await enqueue_unpaused_releases()
        log_activity(f"▶️ Sincronizzazione globale RIPRESA ({added} release rimesse in coda).", "SYSTEM", "info")

    return {"ok": True, "global_paused": GLOBAL_PAUSED}


@app.post("/api/repos/{repo_id}/pause", dependencies=[Depends(require_auth)])
async def api_toggle_repo_pause(repo_id: int, paused: Optional[bool] = Query(None)):
    conn = get_db()
    repo = conn.execute("SELECT id, full_name, COALESCE(paused, 0) as paused FROM repositories WHERE id=?", (repo_id,)).fetchone()
    if not repo:
        conn.close()
        raise HTTPException(status_code=404, detail="Repository non trovato")

    new_paused = (not bool(repo["paused"])) if paused is None else bool(paused)
    with conn:
        conn.execute(
            "UPDATE repositories SET paused=?, status=? WHERE id=?",
            (1 if new_paused else 0, "paused" if new_paused else "idle", repo_id),
        )
    conn.close()

    if new_paused:
        PAUSED_REPOS.add(repo_id)
        log_activity(f"⏸ Repository {repo['full_name']} messo in PAUSA.", repo["full_name"], "warning")
    else:
        PAUSED_REPOS.discard(repo_id)
        added = await enqueue_unpaused_releases(repo_id)
        if added > 0:
            conn = get_db()
            with conn:
                conn.execute("UPDATE repositories SET status='downloading' WHERE id=?", (repo_id,))
            conn.close()
        else:
            asyncio.create_task(sync_repository_releases(repo_id, is_initial=False))
        log_activity(f"▶️ Sincronizzazione ripresa per {repo['full_name']} ({added} release in coda).", repo["full_name"], "info")

    return {"ok": True, "repo_id": repo_id, "paused": new_paused}


# --- Repositories Endpoints ---
@app.get("/api/repos", dependencies=[Depends(require_auth)])
async def api_list_repos():
    conn = get_db()
    repos = conn.execute(
        """
        SELECT r.*,
               COUNT(DISTINCT rel.id) as releases_count,
               SUM(CASE WHEN rel.status = 'completed' THEN 1 ELSE 0 END) as completed_releases_count,
               COALESCE(SUM(rel.total_size), 0) as repo_total_size,
               (SELECT tag_name FROM releases WHERE repo_id = r.id ORDER BY published_at DESC LIMIT 1) as latest_tag,
               (SELECT published_at FROM releases WHERE repo_id = r.id ORDER BY published_at DESC LIMIT 1) as latest_published_at
        FROM repositories r
        LEFT JOIN releases rel ON rel.repo_id = r.id
        GROUP BY r.id
        ORDER BY COALESCE(latest_published_at, r.created_at) DESC
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in repos]


@app.post("/api/repos", dependencies=[Depends(require_auth)])
async def api_add_repo(req: AddRepoRequest):
    try:
        parsed = parse_source_input(req.repo_input)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    now = datetime.now(timezone.utc).isoformat()

    # --- CASE 1: NEXUS MODS ---
    if parsed["provider"] == "nexusmods":
        domain = parsed["domain"]
        mod_id = parsed["mod_id"]
        try:
            nx_info = await fetch_nexus_mod_info(domain, mod_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

        game_id = nx_info["game_id"]
        game_name = nx_info["game_name"]
        mod_obj = nx_info["mod"]
        mod_name = mod_obj.get("name") or f"Mod #{mod_id}"
        full_name = f"{domain}/mods/{mod_id}"
        description = mod_obj.get("summary") or ""
        html_url = f"https://www.nexusmods.com/{domain}/mods/{mod_id}"
        avatar_url = mod_obj.get("pictureUrl") or ""
        stars = int(mod_obj.get("endorsements") or 0)
        nx_tags = [t["name"] for t in (mod_obj.get("tags") or []) if t.get("name")]
        if mod_obj.get("category"):
            nx_tags.insert(0, mod_obj["category"])

        conn = get_db()
        existing = conn.execute(
            "SELECT id FROM repositories WHERE (provider='nexusmods' AND nexus_domain=? AND nexus_mod_id=?) OR LOWER(full_name)=LOWER(?)",
            (domain, mod_id, full_name),
        ).fetchone()
        if existing:
            conn.close()
            raise HTTPException(status_code=409, detail=f"La mod '{mod_name}' ({full_name}) è già presente nel Vault.")
        conn.close()

        classified = auto_classify_repo(
            domain, mod_name, description, nx_tags, "", provider="nexusmods", game_name=game_name
        )
        final_category = req.category.strip()
        if not final_category or final_category.lower() == "auto":
            final_category = classified["category"]
        final_tags = req.tags.strip() or classified["tags"]

        conn = get_db()
        with conn:
            cur = conn.execute(
                """
                INSERT INTO repositories (
                    owner, name, full_name, description, html_url, avatar_url,
                    category, tags, include_prereleases, download_source, only_latest, asset_filter,
                    stars, created_at, status, provider, nexus_domain, nexus_mod_id, nexus_game_id, nexus_game_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 'checking', 'nexusmods', ?, ?, ?, ?)
                """,
                (
                    game_name,
                    mod_name,
                    full_name,
                    description,
                    html_url,
                    avatar_url,
                    final_category,
                    final_tags,
                    1 if req.include_prereleases else 0,
                    1 if req.only_latest else 0,
                    req.asset_filter.strip(),
                    stars,
                    now,
                    domain,
                    mod_id,
                    game_id,
                    game_name,
                ),
            )
            repo_id = cur.lastrowid
        conn.close()

        log_activity(
            f"[Nexus Mods] Aggiunta mod '{mod_name}' ({game_name}) [Categoria: {final_category}]. Avvio download versioni...",
            full_name,
            "info",
        )
        asyncio.create_task(sync_repository_releases(repo_id, is_initial=True))
        return {
            "ok": True,
            "repo_id": repo_id,
            "full_name": f"{game_name} — {mod_name}",
            "category": final_category,
            "tags": final_tags,
            "provider": "nexusmods",
        }

    # --- CASE 2: GITHUB ---
    owner, name = parsed["owner"], parsed["name"]
    full_name = f"{owner}/{name}"
    cfg = get_settings_dict()
    headers = github_headers(cfg.get("github_token", ""))

    description = ""
    html_url = f"https://github.com/{full_name}"
    avatar_url = ""
    stars = 0
    topics: List[str] = []
    language = ""

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(f"https://api.github.com/repos/{full_name}", headers=headers)
        if resp.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Repository '{full_name}' non trovato su GitHub (se è privato, configura il GitHub Token nelle Impostazioni).",
            )
        if resp.status_code == 200:
            gh_data = resp.json()
            owner = gh_data["owner"]["login"]
            name = gh_data["name"]
            full_name = gh_data["full_name"]
            description = gh_data.get("description") or ""
            html_url = gh_data.get("html_url") or f"https://github.com/{full_name}"
            avatar_url = (gh_data.get("owner") or {}).get("avatar_url") or ""
            stars = gh_data.get("stargazers_count") or 0
            topics = gh_data.get("topics") or []
            language = gh_data.get("language") or ""

    conn = get_db()
    existing = conn.execute("SELECT id FROM repositories WHERE LOWER(full_name)=LOWER(?)", (full_name,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail=f"Il repository '{full_name}' è già presente nel Vault.")
    conn.close()

    classified = auto_classify_repo(owner, name, description, topics, language, provider="github")
    final_category = req.category.strip()
    if not final_category or final_category.lower() == "auto":
        final_category = classified["category"]
    final_tags = req.tags.strip() or classified["tags"]

    conn = get_db()
    with conn:
        cur = conn.execute(
            """
            INSERT INTO repositories (
                owner, name, full_name, description, html_url, avatar_url,
                category, tags, include_prereleases, download_source, only_latest, asset_filter,
                stars, created_at, status, provider
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'checking', 'github')
            """,
            (
                owner,
                name,
                full_name,
                description,
                html_url,
                avatar_url,
                final_category,
                final_tags,
                1 if req.include_prereleases else 0,
                1 if req.download_source else 0,
                1 if req.only_latest else 0,
                req.asset_filter.strip(),
                stars,
                now,
            ),
        )
        repo_id = cur.lastrowid
    conn.close()

    log_activity(
        f"Aggiunto repository {full_name} [Categoria: {final_category} | Tag: {final_tags}]. Avvio sincronizzazione storico...",
        full_name,
        "info",
    )
    asyncio.create_task(sync_repository_releases(repo_id, is_initial=True))

    return {
        "ok": True,
        "repo_id": repo_id,
        "full_name": full_name,
        "category": final_category,
        "tags": final_tags,
        "provider": "github",
    }


@app.put("/api/repos/{repo_id}", dependencies=[Depends(require_auth)])
async def api_update_repo(repo_id: int, req: UpdateRepoRequest):
    conn = get_db()
    repo = conn.execute("SELECT * FROM repositories WHERE id=?", (repo_id,)).fetchone()
    if not repo:
        conn.close()
        raise HTTPException(status_code=404, detail="Repository non trovato")

    final_tags = req.tags.strip()
    if not final_tags:
        classified = auto_classify_repo(
            repo["owner"],
            repo["name"],
            repo["description"] or "",
            provider=repo["provider"] or "github",
            game_name=repo["nexus_game_name"] or "",
        )
        final_tags = classified["tags"]

    with conn:
        conn.execute(
            """
            UPDATE repositories
            SET category=?, tags=?, include_prereleases=?, download_source=?, only_latest=?, asset_filter=?
            WHERE id=?
            """,
            (
                req.category.strip() or "Generale",
                final_tags,
                1 if req.include_prereleases else 0,
                1 if req.download_source else 0,
                1 if req.only_latest else 0,
                req.asset_filter.strip(),
                repo_id,
            ),
        )
        if req.only_latest:
            # Keep completed releases and the single most recent release; remove older pending releases
            latest_row = conn.execute(
                "SELECT id FROM releases WHERE repo_id=? ORDER BY published_at DESC LIMIT 1",
                (repo_id,),
            ).fetchone()
            if latest_row:
                old_pending = conn.execute(
                    "SELECT id FROM releases WHERE repo_id=? AND status='pending' AND id != ?",
                    (repo_id, latest_row["id"]),
                ).fetchall()
                for op in old_pending:
                    QUEUED_RELEASES.discard(op["id"])
                    conn.execute("DELETE FROM releases WHERE id=?", (op["id"],))
    conn.close()
    return {"ok": True, "tags": final_tags}


def get_repo_folder_name(repo: sqlite3.Row | Dict[str, Any]) -> str:
    if (repo["provider"] or "github") == "nexusmods":
        return f"nexus__{sanitize_filename(repo['nexus_domain'])}__{repo['nexus_mod_id']}"
    return f"{sanitize_filename(repo['owner'])}__{sanitize_filename(repo['name'])}"


@app.post("/api/repos/{repo_id}/purge-data", dependencies=[Depends(require_auth)])
async def api_purge_repo_data(repo_id: int, resync: bool = Query(True)):
    conn = get_db()
    repo = conn.execute("SELECT * FROM repositories WHERE id=?", (repo_id,)).fetchone()
    if not repo:
        conn.close()
        raise HTTPException(status_code=404, detail="Repository non trovato")

    # 1. Pause repo immediately to interrupt any active chunk download
    PAUSED_REPOS.add(repo_id)
    rel_rows = conn.execute("SELECT id FROM releases WHERE repo_id=?", (repo_id,)).fetchall()
    conn.close()

    for r in rel_rows:
        QUEUED_RELEASES.discard(r["id"])

    # If a worker is actively downloading a release for this repo, give it a moment to abort
    if any(d.get("repo_id") == repo_id for d in ACTIVE_DOWNLOADS.values()):
        await asyncio.sleep(0.35)

    # 2. Delete all releases and assets from DB for this repository
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM releases WHERE repo_id=?", (repo_id,))
        if resync:
            conn.execute("UPDATE repositories SET paused=0, status='checking', error_message='' WHERE id=?", (repo_id,))
        else:
            conn.execute("UPDATE repositories SET paused=1, status='paused', error_message='' WHERE id=?", (repo_id,))
    conn.close()

    # 3. Delete repository archive directory on disk
    repo_folder = ARCHIVE_DIR / get_repo_folder_name(repo)
    if repo_folder.exists():
        shutil.rmtree(repo_folder, ignore_errors=True)

    if resync:
        PAUSED_REPOS.discard(repo_id)
        log_activity(
            f"🧹 Dati eliminati per {repo['full_name']}. Riavvio sincronizzazione con le nuove opzioni...",
            repo["full_name"],
            "warning",
        )
        asyncio.create_task(sync_repository_releases(repo_id, is_initial=True))
    else:
        log_activity(
            f"🧹 Tutti i dati scaricati per {repo['full_name']} sono stati eliminati (repository messa in pausa).",
            repo["full_name"],
            "warning",
        )

    return {"ok": True, "repo_id": repo_id, "resync": resync}


@app.delete("/api/repos/{repo_id}", dependencies=[Depends(require_auth)])
async def api_delete_repo(repo_id: int, delete_files: bool = Query(True)):
    conn = get_db()
    repo = conn.execute("SELECT * FROM repositories WHERE id=?", (repo_id,)).fetchone()
    if not repo:
        conn.close()
        raise HTTPException(status_code=404, detail="Repository non trovato")

    PAUSED_REPOS.add(repo_id)
    rel_rows = conn.execute("SELECT * FROM releases WHERE repo_id=?", (repo_id,)).fetchall()
    for r in rel_rows:
        QUEUED_RELEASES.discard(r["id"])

    if any(d.get("repo_id") == repo_id for d in ACTIVE_DOWNLOADS.values()):
        await asyncio.sleep(0.35)

    repo_folder_name = get_repo_folder_name(repo)
    repo_folder = ARCHIVE_DIR / repo_folder_name

    if not delete_files and repo_folder.exists():
        # Snapshot repository info and release metadata on disk before removing from DB
        try:
            for rel in rel_rows:
                assets_rows = conn.execute(
                    "SELECT * FROM assets WHERE release_id=? ORDER BY id ASC", (rel["id"],)
                ).fetchall()
                completed_assets = [a for a in assets_rows if a["status"] == "completed" and Path(a["local_path"]).exists()]
                rel_dir = Path(rel["folder_path"])
                if completed_assets:
                    write_release_disk_metadata(rel, repo, completed_assets)
                else:
                    # Clean up empty release directory that had no downloaded files
                    if rel_dir.exists():
                        shutil.rmtree(rel_dir, ignore_errors=True)

            repo_info_path = repo_folder / "vault-repo-info.json"
            repo_info_data = {
                "folder_name": repo_folder_name,
                "provider": repo["provider"] or "github",
                "owner": repo["owner"],
                "name": repo["name"],
                "full_name": repo["full_name"],
                "description": repo["description"] or "",
                "category": repo["category"] or "Generale",
                "tags": repo["tags"] or "",
                "html_url": repo["html_url"] or "",
                "avatar_url": repo["avatar_url"] or "",
                "deleted_at": datetime.now(timezone.utc).isoformat(),
            }
            repo_info_path.write_text(json.dumps(repo_info_data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Error writing snapshot metadata before repo deletion: {e}")

    with conn:
        conn.execute("DELETE FROM repositories WHERE id=?", (repo_id,))
    conn.close()
    PAUSED_REPOS.discard(repo_id)

    if delete_files and repo_folder.exists():
        shutil.rmtree(repo_folder, ignore_errors=True)

    log_activity(
        f"Rimosso progetto {repo['full_name']} ({'file eliminati dal disco' if delete_files else 'file conservati nell archivio locale'})",
        repo["full_name"],
        "warning",
    )
    return {"ok": True, "deleted_files": delete_files}


def scan_detached_archive_folder(repo_dir: Path) -> Optional[Dict[str, Any]]:
    if not repo_dir.is_dir():
        return None

    info_file = repo_dir / "vault-repo-info.json"
    info: Dict[str, Any] = {}
    if info_file.exists():
        try:
            info = json.loads(info_file.read_text(encoding="utf-8"))
        except Exception:
            info = {}

    releases_list: List[Dict[str, Any]] = []
    total_repo_size = 0

    for ver_dir in sorted(repo_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not ver_dir.is_dir():
            continue
        meta_file = ver_dir / "release-metadata.json"
        md_file = ver_dir / "PATCH_NOTES.md"
        meta: Dict[str, Any] = {}
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                meta = {}

        # Scan actual files on disk inside assets/ and source/
        disk_assets: List[Dict[str, Any]] = []
        sha_by_name = {a.get("name"): a.get("sha256", "") for a in (meta.get("assets") or []) if isinstance(a, dict)}

        for sub_name, a_type in [("assets", "binary"), ("source", "source_zip")]:
            sub_dir = ver_dir / sub_name
            if sub_dir.is_dir():
                for fpath in sorted(sub_dir.iterdir()):
                    if fpath.is_file() and not fpath.name.endswith(".part"):
                        fsize = fpath.stat().st_size
                        if fsize <= 0:
                            continue
                        rel_disk_path = str(fpath.relative_to(ARCHIVE_DIR))
                        disk_assets.append(
                            {
                                "name": fpath.name,
                                "asset_type": a_type,
                                "size": fsize,
                                "sha256": sha_by_name.get(fpath.name, ""),
                                "status": "completed",
                                "rel_path": rel_disk_path,
                            }
                        )

        if not disk_assets:
            continue

        ver_size = sum(a["size"] for a in disk_assets)
        total_repo_size += ver_size

        body_text = meta.get("patch_notes") or ""
        if not body_text and md_file.exists():
            try:
                body_text = md_file.read_text(encoding="utf-8")
            except Exception:
                body_text = ""

        if not info and meta:
            info = {
                "provider": meta.get("provider", "github"),
                "full_name": meta.get("repository", repo_dir.name),
                "category": meta.get("category", "Archivio Locale"),
                "tags": meta.get("tags", ""),
                "html_url": meta.get("html_url", ""),
            }

        releases_list.append(
            {
                "id": ver_dir.name,
                "tag_name": meta.get("tag_name") or ver_dir.name,
                "name": meta.get("release_name") or ver_dir.name,
                "prerelease": bool(meta.get("prerelease", False)),
                "published_at": meta.get("published_at") or datetime.fromtimestamp(ver_dir.stat().st_mtime, tz=timezone.utc).isoformat(),
                "folder_path": str(ver_dir),
                "version_folder": ver_dir.name,
                "body": body_text,
                "total_size": ver_size,
                "status": "completed",
                "assets": disk_assets,
            }
        )

    if not releases_list:
        return None

    parts = repo_dir.name.split("__", 1)
    fallback_owner = parts[0] if len(parts) > 1 else "Archivio"
    fallback_name = parts[1] if len(parts) > 1 else repo_dir.name

    return {
        "folder_name": repo_dir.name,
        "provider": info.get("provider") or ("nexusmods" if repo_dir.name.startswith("nexus__") else "github"),
        "owner": info.get("owner") or fallback_owner,
        "name": info.get("name") or fallback_name,
        "full_name": info.get("full_name") or f"{fallback_owner}/{fallback_name}",
        "description": info.get("description") or "Archivio locale conservato sul disco (repository rimossa dal monitoraggio attivo).",
        "category": info.get("category") or "Archivio Locale",
        "tags": info.get("tags") or "",
        "html_url": info.get("html_url") or "#",
        "avatar_url": info.get("avatar_url") or "",
        "deleted_at": info.get("deleted_at") or "",
        "releases_count": len(releases_list),
        "completed_releases_count": len(releases_list),
        "repo_total_size": total_repo_size,
        "latest_tag": releases_list[0]["tag_name"],
        "releases": releases_list,
    }


@app.get("/api/detached-archives", dependencies=[Depends(require_auth)])
async def api_list_detached_archives():
    conn = get_db()
    active_repos = conn.execute("SELECT owner, name, provider, nexus_domain, nexus_mod_id FROM repositories").fetchall()
    conn.close()
    active_folders = {get_repo_folder_name(r) for r in active_repos}

    detached: List[Dict[str, Any]] = []
    if ARCHIVE_DIR.exists():
        for d in sorted(ARCHIVE_DIR.iterdir()):
            if not d.is_dir() or d.name in active_folders:
                continue
            item = scan_detached_archive_folder(d)
            if item:
                detached.append(item)
    return detached


@app.get("/api/detached-archives/{folder_name}/releases", dependencies=[Depends(require_auth)])
async def api_get_detached_archive_detail(folder_name: str):
    safe_folder = sanitize_filename(folder_name)
    target = (ARCHIVE_DIR / safe_folder).resolve()
    if not str(target).startswith(str(ARCHIVE_DIR.resolve())) or not target.is_dir():
        raise HTTPException(status_code=404, detail="Archivio locale non trovato")
    item = scan_detached_archive_folder(target)
    if not item:
        raise HTTPException(status_code=404, detail="Archivio vuoto o non trovato")
    releases = item.pop("releases", [])
    return {"repository": item, "releases": releases}


@app.get("/api/detached-archives/download", dependencies=[Depends(require_auth)])
async def api_download_detached_file(path: str = Query(...)):
    target = (ARCHIVE_DIR / path).resolve()
    if not str(target).startswith(str(ARCHIVE_DIR.resolve())) or not target.is_file():
        raise HTTPException(status_code=404, detail="File non trovato sul disco")
    return FileResponse(path=target, filename=target.name, media_type="application/octet-stream")


@app.get("/api/detached-archives/bundle", dependencies=[Depends(require_auth)])
async def api_download_detached_bundle(folder: str = Query(...), version: str = Query(...)):
    target = (ARCHIVE_DIR / sanitize_filename(folder) / sanitize_filename(version)).resolve()
    if not str(target).startswith(str(ARCHIVE_DIR.resolve())) or not target.is_dir():
        raise HTTPException(status_code=404, detail="Cartella versione non trovata sul disco")

    zip_filename = f"{sanitize_filename(folder)}-{sanitize_filename(version)}-bundle.zip"

    def iter_zip():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
            for root, _, files in os.walk(target):
                for file in files:
                    if file.endswith(".part"):
                        continue
                    full_p = Path(root) / file
                    rel_p = full_p.relative_to(target)
                    zf.write(full_p, arcname=str(rel_p))
        buf.seek(0)
        yield from buf

    return StreamingResponse(
        iter_zip(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )


@app.delete("/api/detached-archives/{folder_name}", dependencies=[Depends(require_auth)])
async def api_delete_detached_archive(folder_name: str, version: Optional[str] = Query(None)):
    safe_folder = sanitize_filename(folder_name)
    repo_dir = (ARCHIVE_DIR / safe_folder).resolve()
    if not str(repo_dir).startswith(str(ARCHIVE_DIR.resolve())) or not repo_dir.is_dir():
        raise HTTPException(status_code=404, detail="Archivio non trovato")

    if version:
        ver_dir = (repo_dir / sanitize_filename(version)).resolve()
        if str(ver_dir).startswith(str(repo_dir)) and ver_dir.is_dir():
            shutil.rmtree(ver_dir, ignore_errors=True)
        # If no versions remain, clean up parent folder
        if not scan_detached_archive_folder(repo_dir):
            shutil.rmtree(repo_dir, ignore_errors=True)
        log_activity(f"Eliminata versione conservata {version} da {safe_folder}", safe_folder, "warning")
    else:
        shutil.rmtree(repo_dir, ignore_errors=True)
        log_activity(f"Eliminato definitivamente archivio locale {safe_folder} dal disco", safe_folder, "warning")
    return {"ok": True}


@app.post("/api/repos/{repo_id}/sync", dependencies=[Depends(require_auth)])
async def api_sync_single_repo(repo_id: int):
    asyncio.create_task(sync_repository_releases(repo_id, is_initial=False))
    return {"ok": True, "message": "Controllo release avviato"}


@app.post("/api/sync-all", dependencies=[Depends(require_auth)])
async def api_sync_all():
    asyncio.create_task(check_all_repositories())
    return {"ok": True, "message": "Controllo globale avviato"}


# --- Releases & Assets Endpoints ---
@app.get("/api/repos/{repo_id}/releases", dependencies=[Depends(require_auth)])
async def api_repo_releases(repo_id: int):
    conn = get_db()
    repo = conn.execute("SELECT * FROM repositories WHERE id=?", (repo_id,)).fetchone()
    if not repo:
        conn.close()
        raise HTTPException(status_code=404, detail="Repository non trovato")

    releases = conn.execute(
        "SELECT * FROM releases WHERE repo_id=? ORDER BY published_at DESC, id DESC", (repo_id,)
    ).fetchall()

    release_ids = [r["id"] for r in releases]
    assets_by_rel: Dict[int, List[Dict[str, Any]]] = {rid: [] for rid in release_ids}
    if release_ids:
        placeholders = ",".join("?" for _ in release_ids)
        assets = conn.execute(
            f"SELECT * FROM assets WHERE release_id IN ({placeholders}) ORDER BY asset_type ASC, name ASC",
            release_ids,
        ).fetchall()
        for a in assets:
            assets_by_rel[a["release_id"]].append(dict(a))

    conn.close()

    result_releases = []
    for r in releases:
        rd = dict(r)
        rd["assets"] = assets_by_rel.get(r["id"], [])
        rd["active_progress"] = ACTIVE_DOWNLOADS.get(r["id"])
        result_releases.append(rd)

    return {"repository": dict(repo), "releases": result_releases}


@app.get("/api/feed", dependencies=[Depends(require_auth)])
async def api_global_feed(q: str = Query(""), category: str = Query(""), prerelease: str = Query("")):
    conn = get_db()
    sql = """
        SELECT rel.*, r.full_name as repo_full_name, r.owner as repo_owner, r.name as repo_name,
               r.avatar_url as repo_avatar, r.category as repo_category, r.tags as repo_tags,
               r.provider as repo_provider, r.nexus_game_name as repo_game_name
        FROM releases rel
        JOIN repositories r ON r.id = rel.repo_id
        WHERE 1=1
    """
    params: List[Any] = []
    if category:
        sql += " AND r.category = ?"
        params.append(category)
    if prerelease == "stable":
        sql += " AND rel.prerelease = 0"
    elif prerelease == "prerelease":
        sql += " AND rel.prerelease = 1"
    if q.strip():
        like_q = f"%{q.strip()}%"
        sql += " AND (r.full_name LIKE ? OR r.name LIKE ? OR rel.tag_name LIKE ? OR rel.name LIKE ? OR rel.body LIKE ?)"
        params.extend([like_q, like_q, like_q, like_q, like_q])

    sql += " ORDER BY rel.published_at DESC LIMIT 150"
    rows = conn.execute(sql, params).fetchall()

    rel_ids = [r["id"] for r in rows]
    assets_by_rel: Dict[int, List[Dict[str, Any]]] = {rid: [] for rid in rel_ids}
    if rel_ids:
        placeholders = ",".join("?" for _ in rel_ids)
        assets = conn.execute(
            f"SELECT * FROM assets WHERE release_id IN ({placeholders}) ORDER BY asset_type ASC, name ASC",
            rel_ids,
        ).fetchall()
        for a in assets:
            assets_by_rel[a["release_id"]].append(dict(a))
    conn.close()

    out = []
    for r in rows:
        d = dict(r)
        d["assets"] = assets_by_rel.get(r["id"], [])
        out.append(d)
    return out


@app.post("/api/releases/{release_id}/retry", dependencies=[Depends(require_auth)])
async def api_retry_release(release_id: int):
    conn = get_db()
    rel = conn.execute("SELECT id FROM releases WHERE id=?", (release_id,)).fetchone()
    if not rel:
        conn.close()
        raise HTTPException(status_code=404, detail="Release non trovata")
    with conn:
        conn.execute("UPDATE releases SET status='pending' WHERE id=?", (release_id,))
        conn.execute("UPDATE assets SET status='pending' WHERE release_id=? AND status!='completed'", (release_id,))
    conn.close()
    await DOWNLOAD_QUEUE.put({"release_id": release_id, "notify": False})
    return {"ok": True}


@app.delete("/api/releases/{release_id}", dependencies=[Depends(require_auth)])
async def api_delete_release(release_id: int):
    conn = get_db()
    rel = conn.execute("SELECT * FROM releases WHERE id=?", (release_id,)).fetchone()
    if not rel:
        conn.close()
        raise HTTPException(status_code=404, detail="Release non trovata")
    folder = Path(rel["folder_path"])
    with conn:
        conn.execute("DELETE FROM releases WHERE id=?", (release_id,))
    conn.close()
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
    return {"ok": True}


@app.get("/api/assets/{asset_id}/download", dependencies=[Depends(require_auth)])
async def api_download_asset(asset_id: int):
    conn = get_db()
    asset = conn.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
    conn.close()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset non trovato")
    path = Path(asset["local_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File non ancora presente sul disco")
    return FileResponse(path=path, filename=asset["name"], media_type="application/octet-stream")


@app.get("/api/releases/{release_id}/bundle", dependencies=[Depends(require_auth)])
async def api_download_release_bundle(release_id: int):
    conn = get_db()
    rel = conn.execute(
        """
        SELECT rel.*, r.owner, r.name as repo_name
        FROM releases rel
        JOIN repositories r ON r.id = rel.repo_id
        WHERE rel.id=?
        """,
        (release_id,),
    ).fetchone()
    conn.close()
    if not rel:
        raise HTTPException(status_code=404, detail="Release non trovata")

    folder = Path(rel["folder_path"])
    if not folder.exists():
        raise HTTPException(status_code=404, detail="Cartella release non trovata sul disco")

    zip_filename = f"{sanitize_filename(rel['repo_name'])}-{sanitize_filename(rel['tag_name'])}-bundle.zip"

    def iter_zip():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
            for root, _, files in os.walk(folder):
                for file in files:
                    if file.endswith(".part"):
                        continue
                    full_p = Path(root) / file
                    rel_p = full_p.relative_to(folder)
                    zf.write(full_p, arcname=str(rel_p))
        buf.seek(0)
        yield from buf

    return StreamingResponse(
        iter_zip(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )


# --- Settings & Rate Limit Endpoints ---
@app.get("/api/settings", dependencies=[Depends(require_auth)])
async def api_get_settings():
    cfg = get_settings_dict()
    token = cfg.get("github_token", "").strip()
    nx_key = cfg.get("nexus_api_key", "").strip()
    nx_sess = cfg.get("nexus_session_cookie", "").strip()

    rate_limit = {"limit": 60, "remaining": None, "reset": None, "authenticated": bool(token)}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get("https://api.github.com/rate_limit", headers=github_headers(token))
            if resp.status_code == 200:
                core = resp.json().get("resources", {}).get("core", {})
                rate_limit = {
                    "limit": core.get("limit", 60),
                    "remaining": core.get("remaining", 0),
                    "reset": core.get("reset"),
                    "authenticated": bool(token),
                }
    except Exception:
        pass

    return {
        "auth_username": cfg.get("auth_username", "admin"),
        "has_github_token": bool(token),
        "github_token_masked": (token[:6] + "..." + token[-4:]) if len(token) > 12 else ("Configurato" if token else ""),
        "check_interval_minutes": cfg.get("check_interval_minutes", "60"),
        "notify_on_initial_sync": cfg.get("notify_on_initial_sync", "0"),
        "discord_webhook_url": cfg.get("discord_webhook_url", ""),
        "telegram_bot_token": cfg.get("telegram_bot_token", ""),
        "telegram_chat_id": cfg.get("telegram_chat_id", ""),
        "nexus_username": cfg.get("nexus_username", ""),
        "has_nexus_api_key": bool(nx_key),
        "has_nexus_session": bool(nx_sess),
        "smtp_host": cfg.get("smtp_host", ""),
        "smtp_port": cfg.get("smtp_port", "587"),
        "smtp_user": cfg.get("smtp_user", ""),
        "smtp_from": cfg.get("smtp_from", ""),
        "smtp_to": cfg.get("smtp_to", ""),
        "has_smtp_password": bool(cfg.get("smtp_password", "")),
        "language": cfg.get("language", "it"),
        "rate_limit": rate_limit,
    }


@app.put("/api/settings", dependencies=[Depends(require_auth)])
async def api_update_settings(req: UpdateSettingsRequest):
    if req.github_token is not None and req.github_token != "__KEEP__":
        set_setting("github_token", req.github_token.strip())
    if req.check_interval_minutes is not None:
        set_setting("check_interval_minutes", str(max(5, int(req.check_interval_minutes or 60))))
    if req.notify_on_initial_sync is not None:
        set_setting("notify_on_initial_sync", req.notify_on_initial_sync)
    if req.discord_webhook_url is not None:
        set_setting("discord_webhook_url", req.discord_webhook_url.strip())
    if req.telegram_bot_token is not None:
        set_setting("telegram_bot_token", req.telegram_bot_token.strip())
    if req.telegram_chat_id is not None:
        set_setting("telegram_chat_id", req.telegram_chat_id.strip())
    if req.nexus_username is not None:
        set_setting("nexus_username", req.nexus_username.strip())
    if req.nexus_password is not None and req.nexus_password != "__KEEP__":
        set_setting("nexus_password", req.nexus_password)
    if req.nexus_api_key is not None and req.nexus_api_key != "__KEEP__":
        set_setting("nexus_api_key", req.nexus_api_key.strip())
    if req.nexus_session_cookie is not None and req.nexus_session_cookie != "__KEEP__":
        set_setting("nexus_session_cookie", req.nexus_session_cookie.strip())
    if req.smtp_host is not None:
        set_setting("smtp_host", req.smtp_host.strip())
    if req.smtp_port is not None:
        set_setting("smtp_port", req.smtp_port.strip())
    if req.smtp_user is not None:
        set_setting("smtp_user", req.smtp_user.strip())
    if req.smtp_password is not None and req.smtp_password != "__KEEP__":
        set_setting("smtp_password", req.smtp_password)
    if req.smtp_from is not None:
        set_setting("smtp_from", req.smtp_from.strip())
    if req.smtp_to is not None:
        set_setting("smtp_to", req.smtp_to.strip())
    if req.language is not None and req.language.strip():
        set_setting("language", req.language.strip())

    if req.new_username and req.new_username.strip():
        set_setting("auth_username", req.new_username.strip())
    if req.new_password and req.new_password.strip():
        set_setting("auth_password_hash", hash_password(req.new_password.strip()))

    if req.github_token is not None or req.check_interval_minutes is not None or req.new_username is not None or req.new_password is not None:
        log_activity("Impostazioni della piattaforma aggiornate.", "SYSTEM", "info")
    return {"ok": True}


@app.post("/api/settings/test-notification", dependencies=[Depends(require_auth)])
async def api_test_notification():
    await send_notifications(
        repo_full_name="release-vault/test-repository",
        release_tag="v1.0.0-test",
        release_name="Release di Test Notifiche (Release Vault)",
        prerelease=False,
        body="### Novità\n- Notifiche Release Vault configurate correttamente.\n- Supporto GitHub + Nexus Mods attivo 24/7.",
        html_url="https://github.com",
        files_count=3,
        total_size=42 * 1024 * 1024,
    )
    return {"ok": True, "message": "Notifica di test inviata ai canali configurati"}


# --- Serve SPA Frontend ---
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = BASE_DIR / "static" / "index.html"
    return HTMLResponse(index_file.read_text(encoding="utf-8"))
