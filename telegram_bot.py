import asyncio
import html
import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

# --- Dynamic Bot Configuration (loaded from SQLite settings or environment) ---
VAULT_API_BASE = os.environ.get("VAULT_API_BASE", "http://127.0.0.1:80")
INTERNAL_HEADERS = {"X-Internal-Bot": "release-vault-bot"}
DB_PATH = Path(os.environ.get("VAULT_DB_PATH", "/srv/github-vault/vault.db"))

BOT_TOKEN: str = ""
AUTHORIZED_USER_ID: int = 0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [release-vault-bot] %(message)s",
)
logger = logging.getLogger("telegram-bot")

# Store pending repo additions by short key -> {full_name, suggested_category, suggested_tags}
PENDING_ADDS: Dict[str, Dict[str, Any]] = {}
PENDING_COUNTER = 0


def load_bot_credentials() -> tuple[str, int]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    uid_str = os.environ.get("TELEGRAM_AUTHORIZED_USER_ID", "").strip()
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            rows = dict(conn.execute("SELECT key, value FROM settings WHERE key IN ('telegram_bot_token', 'telegram_chat_id')").fetchall())
            conn.close()
            if rows.get("telegram_bot_token", "").strip():
                token = rows["telegram_bot_token"].strip()
            if rows.get("telegram_chat_id", "").strip():
                uid_str = rows["telegram_chat_id"].strip()
        except Exception:
            pass
    try:
        uid = int(uid_str) if uid_str else 0
    except ValueError:
        uid = 0
    return token, uid


def format_bytes(b: int) -> str:
    if not b or b <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    val = float(b)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024.0
        i += 1
    return f"{val:.2f} {units[i]}" if i > 1 else f"{int(val)} {units[i]}"


async def tg_call(client: httpx.AsyncClient, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    resp = await client.post(url, json=payload, timeout=35.0)
    return resp.json()


async def send_msg(
    client: httpx.AsyncClient,
    chat_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await tg_call(client, "sendMessage", payload)


async def edit_msg(
    client: httpx.AsyncClient,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await tg_call(client, "editMessageText", payload)


async def build_dashboard_message(client: httpx.AsyncClient) -> tuple[str, Dict[str, Any]]:
    ov_resp = await client.get(f"{VAULT_API_BASE}/api/overview", headers=INTERNAL_HEADERS, timeout=10.0)
    ov = ov_resp.json()

    active_list = ov.get("active_downloads") or []
    queue_size = ov.get("queue_size", 0) + len(active_list)
    global_paused = bool(ov.get("global_paused"))

    dl_line = "✅ Nessun download in coda (tutto sincronizzato)"
    if global_paused:
        dl_line = f"⏸ <b>PAUSA GLOBALE ATTIVA</b> ({queue_size} in coda sospesi)"
    elif active_list:
        cur = active_list[0]
        dl_line = (
            f"⚡ In download: <code>{html.escape(cur['repo_full_name'])}</code> "
            f"[{html.escape(cur['tag_name'])}] — <code>{html.escape(cur.get('current_file') or '...')}</code> "
            f"({queue_size} in coda)"
        )
    elif queue_size > 0:
        dl_line = f"⏳ {queue_size} release in coda di download"

    cats = ov.get("categories") or ["Giochi", "Emulatore", "MOD VR"]

    text = (
        f"🛡 <b>Release Vault - Bot Privato</b>\n"
        f"👤 <i>Accesso esclusivo autorizzato (ID: {AUTHORIZED_USER_ID})</i>\n\n"
        f"📦 <b>Repository monitorati:</b> {ov.get('repositories_count', 0)}\n"
        f"🏷 <b>Release archiviate:</b> {ov.get('completed_releases', 0)} / {ov.get('total_releases', 0)}\n"
        f"📁 <b>File salvati:</b> {ov.get('completed_assets', 0)} ({format_bytes(ov.get('archive_bytes', 0))})\n"
        f"💾 <b>Spazio Disco LXC:</b> {format_bytes(ov.get('disk_used', 0))} usati / "
        f"<b>{format_bytes(ov.get('disk_free', 0))} liberi</b> (su {format_bytes(ov.get('disk_total', 0))})\n\n"
        f"🔄 <b>Stato Coda:</b>\n{dl_line}\n\n"
        f"💡 <i>Inviami in qualsiasi momento un link GitHub o Nexus Mods qui in chat per aggiungerlo al Vault!</i>"
    )

    cat_buttons = [
        {"text": f"📁 {c}", "callback_data": f"cat:{c[:24]}"}
        for c in cats[:6]
    ]
    rows: List[List[Dict[str, str]]] = []
    for i in range(0, len(cat_buttons), 2):
        rows.append(cat_buttons[i : i + 2])

    pause_btn_label = "▶️ Riprendi Tutto" if global_paused else "⏸ Pausa Tutto"
    rows.append(
        [
            {"text": pause_btn_label, "callback_data": "action:pause_global"},
            {"text": "🔄 Controlla Release Ora", "callback_data": "action:sync_all"},
        ]
    )
    rows.append(
        [
            {"text": "📊 Aggiorna Stato", "callback_data": "action:dashboard"},
        ]
    )

    return text, {"inline_keyboard": rows}


def extract_github_repos_from_text(text: str) -> List[str]:
    found: List[str] = []
    # 1. Nexus Mods URLs
    for m_nx in re.finditer(r"https?://(?:www\.)?nexusmods\.com/[a-zA-Z0-9_-]+/mods/\d+", text):
        val = m_nx.group(0)
        if val not in found:
            found.append(val)
    # 2. GitHub URLs
    for m in re.finditer(r"https?://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", text):
        val = re.sub(r"\.git$", "", m.group(1).rstrip("/"))
        if val not in found:
            found.append(val)
    if not found:
        stripped = text.strip()
        if re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", stripped):
            found.append(stripped)
    return found


def build_pending_add_view(key: str, item: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    provider_label = item.get("provider_label", "GITHUB")
    full_name = item["full_name"]
    desc = html.escape(item.get("description") or "Nessuna descrizione.")
    sug_cat = item["suggested_category"]
    sug_tags = item["suggested_tags"]
    existing_cats = item.get("existing_categories") or ["Giochi", "Emulatore", "MOD VR"]
    only_latest = bool(item.get("only_latest", False))

    mode_text = "⚡ Solo l'ULTIMA release + successive" if only_latest else "📚 Tutte le release (Storico completo)"
    btn_all_label = ("⬜ 📚 Tutte le Release" if only_latest else "✅ 📚 Tutte le Release")
    btn_lat_label = ("✅ ⚡ Solo Ultima + Successive" if only_latest else "⬜ ⚡ Solo Ultima + Successive")

    text = (
        f"🔍 <b>[{provider_label}] Rilevato:</b> <code>{html.escape(full_name)}</code>\n"
        f"📝 <i>{desc}</i>\n\n"
        f"✨ <b>Categoria consigliata:</b> <code>{html.escape(sug_cat)}</code>\n"
        f"🏷 <b>Tag auto-generati:</b> <code>{html.escape(sug_tags)}</code>\n"
        f"📦 <b>Modalità selezionata:</b> <b>{mode_text}</b>\n\n"
        f"👇 <b>1) Seleziona se scaricare tutte o solo l'ultima + successive:\n2) Clicca sulla categoria per confermare e avviare:</b>"
    )

    keyboard: List[List[Dict[str, str]]] = [
        [
            {"text": btn_all_label, "callback_data": f"setmode:{key}:0"},
            {"text": btn_lat_label, "callback_data": f"setmode:{key}:1"},
        ],
        [{"text": f"✅ Conferma in: {sug_cat} (Consigliata)", "callback_data": f"add:{key}:{sug_cat[:20]}"}],
    ]
    other_Btns = []
    for c in existing_cats:
        if c.lower() != sug_cat.lower():
            other_Btns.append({"text": f"📁 {c}", "callback_data": f"add:{key}:{c[:20]}"})
    for i in range(0, len(other_Btns), 2):
        keyboard.append(other_Btns[i : i + 2])

    keyboard.append([{"text": "❌ Annulla", "callback_data": f"cancel:{key}"}])
    return text, {"inline_keyboard": keyboard}


async def handle_github_link_submission(client: httpx.AsyncClient, chat_id: int, repo_slug: str) -> None:
    global PENDING_COUNTER
    try:
        resp = await client.get(
            f"{VAULT_API_BASE}/api/github/inspect",
            params={"repo": repo_slug},
            headers=INTERNAL_HEADERS,
            timeout=25.0,
        )
        if resp.status_code != 200:
            await send_msg(client, chat_id, f"❌ Impossibile analizzare <code>{html.escape(repo_slug)}</code>.")
            return
        info = resp.json()
    except Exception as e:
        await send_msg(client, chat_id, f"❌ Errore durante l'analisi di <code>{html.escape(repo_slug)}</code>: {e}")
        return

    PENDING_COUNTER += 1
    key = str(PENDING_COUNTER)
    full_name = info["full_name"]
    sug_cat = info.get("suggested_category") or "Giochi"
    sug_tags = info.get("suggested_tags") or ""
    existing_cats = info.get("existing_categories") or ["Giochi", "Emulatore", "MOD VR"]
    provider_label = "NEXUS MODS" if info.get("provider") == "nexusmods" else "GITHUB"

    PENDING_ADDS[key] = {
        "repo_input": repo_slug,
        "full_name": full_name,
        "description": info.get("description") or "",
        "suggested_category": sug_cat,
        "suggested_tags": sug_tags,
        "existing_categories": existing_cats,
        "provider_label": provider_label,
        "only_latest": False,
    }

    text, markup = build_pending_add_view(key, PENDING_ADDS[key])
    await send_msg(client, chat_id, text, markup)


async def handle_callback_query(client: httpx.AsyncClient, cb: Dict[str, Any]) -> None:
    cb_id = cb["id"]
    from_user = cb.get("from") or {}
    user_id = from_user.get("id")
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    message_id = msg.get("message_id")
    data = cb.get("data") or ""

    if user_id != AUTHORIZED_USER_ID:
        await tg_call(client, "answerCallbackQuery", {"callback_query_id": cb_id, "text": "⛔ Non autorizzato", "show_alert": True})
        return

    await tg_call(client, "answerCallbackQuery", {"callback_query_id": cb_id})

    if data == "action:dashboard":
        text, markup = await build_dashboard_message(client)
        await edit_msg(client, chat_id, message_id, text, markup)

    elif data == "action:pause_global":
        p_resp = await client.post(f"{VAULT_API_BASE}/api/pause-global", json={}, headers=INTERNAL_HEADERS, timeout=10.0)
        p_data = p_resp.json()
        text, markup = await build_dashboard_message(client)
        prefix = "⏸ <b>Pausa Globale attivata!</b>\n\n" if p_data.get("global_paused") else "▶️ <b>Sincronizzazione Globale ripresa!</b>\n\n"
        await edit_msg(client, chat_id, message_id, prefix + text, markup)

    elif data == "action:sync_all":
        await client.post(f"{VAULT_API_BASE}/api/sync-all", headers=INTERNAL_HEADERS, timeout=10.0)
        text, markup = await build_dashboard_message(client)
        text = "🔄 <b>Controllo globale di tutti i repository avviato!</b>\n\n" + text
        await edit_msg(client, chat_id, message_id, text, markup)

    elif data.startswith("cat:"):
        cat_name = data.split(":", 1)[1]
        repos_resp = await client.get(f"{VAULT_API_BASE}/api/repos", headers=INTERNAL_HEADERS, timeout=10.0)
        repos = [r for r in repos_resp.json() if (r.get("category") or "").startswith(cat_name)]
        if not repos:
            await edit_msg(
                client,
                chat_id,
                message_id,
                f"📁 Nessun repository nella categoria <b>{html.escape(cat_name)}</b>.",
                {"inline_keyboard": [[{"text": "⬅️ Torna al Menu", "callback_data": "action:dashboard"}]]},
            )
            return

        lines = [f"📁 <b>Categoria: {html.escape(cat_name)}</b> ({len(repos)} repository)\n"]
        kb: List[List[Dict[str, str]]] = []
        for r in repos[:15]:
            if r.get("paused") or r.get("status") == "paused":
                st = "⏸"
            elif r["status"] in ("downloading", "checking"):
                st = "⚡"
            else:
                st = "✅"
            lines.append(
                f"{st} <code>{html.escape(r['full_name'])}</code> — "
                f"<b>{r.get('completed_releases_count') or 0}/{r.get('releases_count') or 0}</b> rel. "
                f"({format_bytes(r.get('repo_total_size') or 0)})"
            )
            if r.get("tags"):
                lines.append(f"   🏷 <i>{html.escape(r['tags'])}</i>")
            kb.append([{"text": f"{st} {r['full_name']} ({r.get('latest_tag') or '...'})", "callback_data": f"repo:{r['id']}"}])

        kb.append([{"text": "⬅️ Torna al Menu", "callback_data": "action:dashboard"}])
        await edit_msg(client, chat_id, message_id, "\n".join(lines), {"inline_keyboard": kb})

    elif data.startswith("repo:"):
        repo_id = int(data.split(":", 1)[1])
        rel_resp = await client.get(f"{VAULT_API_BASE}/api/repos/{repo_id}/releases", headers=INTERNAL_HEADERS, timeout=10.0)
        if rel_resp.status_code != 200:
            return
        rdata = rel_resp.json()
        repo = rdata["repository"]
        releases = rdata["releases"]
        latest = releases[0] if releases else None
        is_paused = bool(repo.get("paused")) or repo.get("status") == "paused"
        only_latest = bool(repo.get("only_latest"))

        status_str = "⏸ IN PAUSA" if is_paused else "✅ ATTIVO"
        mode_str = "⚡ Solo Ultima + Successive" if only_latest else "📚 Tutte le Release (Storico)"
        text = (
            f"📦 <b>{html.escape(repo['full_name'])}</b> [{status_str}]\n"
            f"📁 Categoria: <code>{html.escape(repo.get('category') or 'Generale')}</code>\n"
            f"🏷 Tag: <code>{html.escape(repo.get('tags') or 'Nessuno')}</code>\n"
            f"⚙️ Modalità: <b>{mode_str}</b>\n"
            f"📚 Release in archivio: <b>{len(releases)}</b>\n\n"
        )
        if latest:
            body_preview = html.escape((latest.get("body") or "Nessuna patch note.")[:500])
            text += (
                f"🆕 <b>Ultima versione:</b> <code>{html.escape(latest['tag_name'])}</code>\n"
                f"📅 Data: {html.escape(latest.get('published_at', '')[:10])}\n"
                f"💾 Dimensione: {format_bytes(latest.get('total_size') or 0)}\n\n"
                f"📝 <b>Patch Notes:</b>\n<pre>{body_preview}</pre>"
            )

        pause_label = "▶️ Riprendi Sincronizzazione" if is_paused else "⏸ Metti in Pausa Repo"
        btn_all_repo = "⬜ 📚 Tutte le Release" if only_latest else "✅ 📚 Tutte le Release"
        btn_lat_repo = "✅ ⚡ Solo Ultima + Succ." if only_latest else "⬜ ⚡ Solo Ultima + Succ."
        kb = [
            [
                {"text": btn_all_repo, "callback_data": f"repomode:{repo_id}:0"},
                {"text": btn_lat_repo, "callback_data": f"repomode:{repo_id}:1"},
            ],
            [
                {"text": pause_label, "callback_data": f"pauserepo:{repo_id}"},
                {"text": "🔄 Controlla Ora", "callback_data": f"syncrepo:{repo_id}"},
            ],
            [
                {"text": "🧹 Pulisci Dati & Riscarica", "callback_data": f"repopurge:{repo_id}"},
            ],
            [{"text": f"⬅️ Torna a {repo.get('category')}", "callback_data": f"cat:{(repo.get('category') or 'Generale')[:24]}"}],
        ]
        await edit_msg(client, chat_id, message_id, text, {"inline_keyboard": kb})

    elif data.startswith("repomode:"):
        parts = data.split(":")
        repo_id = int(parts[1])
        target_only_latest = parts[2] == "1" if len(parts) > 2 else True
        rel_resp = await client.get(f"{VAULT_API_BASE}/api/repos/{repo_id}/releases", headers=INTERNAL_HEADERS, timeout=10.0)
        if rel_resp.status_code == 200:
            repo = rel_resp.json()["repository"]
            update_payload = {
                "category": repo.get("category") or "Generale",
                "tags": repo.get("tags") or "",
                "include_prereleases": bool(repo.get("include_prereleases", 1)),
                "download_source": bool(repo.get("download_source", 1)),
                "only_latest": target_only_latest,
                "asset_filter": repo.get("asset_filter") or "",
            }
            await client.put(f"{VAULT_API_BASE}/api/repos/{repo_id}", json=update_payload, headers=INTERNAL_HEADERS, timeout=10.0)
        cb["data"] = f"repo:{repo_id}"
        await handle_callback_query(client, cb)

    elif data.startswith("repopurge:"):
        repo_id = int(data.split(":", 1)[1])
        await edit_msg(
            client,
            chat_id,
            message_id,
            "🧹 <b>Confermi la pulizia dei file scaricati per questa repository?</b>\n\n"
            "Verranno eliminati i vecchi file dal disco e verrà riavviato subito il download in base alla modalità scelta (es. <i>Solo Ultima + Successive</i>).",
            {
                "inline_keyboard": [
                    [{"text": "✅ Sì, Pulisci e Riscarica Ora", "callback_data": f"repopurge_ok:{repo_id}"}],
                    [{"text": "❌ Annulla", "callback_data": f"repo:{repo_id}"}],
                ]
            },
        )

    elif data.startswith("repopurge_ok:"):
        repo_id = int(data.split(":", 1)[1])
        await client.post(f"{VAULT_API_BASE}/api/repos/{repo_id}/purge-data?resync=true", headers=INTERNAL_HEADERS, timeout=20.0)
        await edit_msg(
            client,
            chat_id,
            message_id,
            "✅ <b>Pulizia completata!</b> Riavviato il download con le nuove impostazioni.",
            {"inline_keyboard": [[{"text": "⬅️ Torna al Repository", "callback_data": f"repo:{repo_id}"}]]},
        )

    elif data.startswith("pauserepo:"):
        repo_id = int(data.split(":", 1)[1])
        await client.post(f"{VAULT_API_BASE}/api/repos/{repo_id}/pause", json={}, headers=INTERNAL_HEADERS, timeout=10.0)
        cb["data"] = f"repo:{repo_id}"
        await handle_callback_query(client, cb)

    elif data.startswith("syncrepo:"):
        repo_id = int(data.split(":", 1)[1])
        await client.post(f"{VAULT_API_BASE}/api/repos/{repo_id}/sync", headers=INTERNAL_HEADERS, timeout=10.0)
        await edit_msg(
            client,
            chat_id,
            message_id,
            "🔄 <b>Controllo nuove release avviato per questo repository!</b>",
            {"inline_keyboard": [[{"text": "⬅️ Torna al Repository", "callback_data": f"repo:{repo_id}"}]]},
        )

    elif data.startswith("setmode:"):
        parts = data.split(":")
        key = parts[1]
        val = parts[2] == "1" if len(parts) > 2 else False
        item = PENDING_ADDS.get(key)
        if not item:
            await edit_msg(client, chat_id, message_id, "⚠️ Richiesta scaduta o già elaborata.")
            return
        item["only_latest"] = val
        text, markup = build_pending_add_view(key, item)
        await edit_msg(client, chat_id, message_id, text, markup)

    elif data.startswith("togmode:"):
        key = data.split(":", 1)[1]
        item = PENDING_ADDS.get(key)
        if not item:
            await edit_msg(client, chat_id, message_id, "⚠️ Richiesta scaduta o già elaborata.")
            return
        item["only_latest"] = not bool(item.get("only_latest", False))
        text, markup = build_pending_add_view(key, item)
        await edit_msg(client, chat_id, message_id, text, markup)

    elif data.startswith("add:"):
        parts = data.split(":", 2)
        if len(parts) < 3:
            return
        key, chosen_cat = parts[1], parts[2]
        item = PENDING_ADDS.pop(key, None)
        if not item:
            await edit_msg(client, chat_id, message_id, "⚠️ Richiesta scaduta o già elaborata.")
            return

        only_latest = bool(item.get("only_latest", False))
        payload = {
            "repo_input": item.get("repo_input") or item["full_name"],
            "category": chosen_cat,
            "tags": item["suggested_tags"],
            "include_prereleases": True,
            "download_source": True,
            "only_latest": only_latest,
            "asset_filter": "",
        }
        resp = await client.post(f"{VAULT_API_BASE}/api/repos", json=payload, headers=INTERNAL_HEADERS, timeout=20.0)
        if resp.status_code == 200:
            res = resp.json()
            mode_desc = (
                "⬇️ <i>Avviato il download SOLO dell'ultima release (e verranno scaricate le future).</i>"
                if only_latest
                else "⬇️ <i>Il download di tutte le release passate e presenti è stato avviato nel Vault.</i>"
            )
            await edit_msg(
                client,
                chat_id,
                message_id,
                f"✅ <b>Repository aggiunto con successo!</b>\n\n"
                f"🔹 <b>Repo:</b> <code>{html.escape(res['full_name'])}</code>\n"
                f"📁 <b>Categoria:</b> <code>{html.escape(res['category'])}</code>\n"
                f"🏷 <b>Tag:</b> <code>{html.escape(res['tags'])}</code>\n\n"
                f"{mode_desc}",
                {"inline_keyboard": [[{"text": "📊 Vai alla Dashboard", "callback_data": "action:dashboard"}]]},
            )
        else:
            err_detail = resp.json().get("detail", "Errore")
            await edit_msg(client, chat_id, message_id, f"⚠️ Impossibile aggiungere: <b>{html.escape(str(err_detail))}</b>")

    elif data.startswith("cancel:"):
        key = data.split(":", 1)[1]
        PENDING_ADDS.pop(key, None)
        await edit_msg(client, chat_id, message_id, "❌ Aggiunta repository annullata.")


async def handle_message(client: httpx.AsyncClient, msg: Dict[str, Any]) -> None:
    from_user = msg.get("from") or {}
    user_id = from_user.get("id")
    chat_id = (msg.get("chat") or {}).get("id")
    text = (msg.get("text") or "").strip()

    # STRICT SECURITY GATE: Only the configured AUTHORIZED_USER_ID is allowed
    if not AUTHORIZED_USER_ID or user_id != AUTHORIZED_USER_ID or chat_id != AUTHORIZED_USER_ID:
        logger.warning(f"Unauthorized access attempt blocked from user_id={user_id}, username={from_user.get('username')}")
        if chat_id:
            await send_msg(client, chat_id, "⛔ <b>Accesso negato.</b>\nQuesto bot è privato e riservato esclusivamente al proprietario.")
        return

    if not text:
        return

    if text.startswith("/start") or text.startswith("/menu") or text.startswith("/status") or text.startswith("/repos"):
        dash_text, markup = await build_dashboard_message(client)
        await send_msg(client, chat_id, dash_text, markup)
        return

    if text.startswith("/sync"):
        await client.post(f"{VAULT_API_BASE}/api/sync-all", headers=INTERNAL_HEADERS, timeout=10.0)
        await send_msg(client, chat_id, "🔄 <b>Controllo globale di tutte le release avviato!</b>")
        return

    # Check if the message contains one or more GitHub links or owner/repo
    repos = extract_github_repos_from_text(text)
    if repos:
        for r_slug in repos:
            await handle_github_link_submission(client, chat_id, r_slug)
        return

    # Default help message
    dash_text, markup = await build_dashboard_message(client)
    await send_msg(client, chat_id, dash_text, markup)


async def bot_loop() -> None:
    global BOT_TOKEN, AUTHORIZED_USER_ID
    offset = 0
    active_token = ""

    async with httpx.AsyncClient() as client:
        while True:
            try:
                BOT_TOKEN, AUTHORIZED_USER_ID = load_bot_credentials()
                if not BOT_TOKEN or not AUTHORIZED_USER_ID:
                    logger.info("Telegram Bot non ancora configurato (in attesa di Token e User ID dal Setup Wizard / Impostazioni)...")
                    await asyncio.sleep(10)
                    continue

                if BOT_TOKEN != active_token:
                    active_token = BOT_TOKEN
                    logger.info(f"Starting Telegram Bot polling (strictly locked to user ID {AUTHORIZED_USER_ID})...")
                    try:
                        await tg_call(
                            client,
                            "setMyCommands",
                            {
                                "commands": [
                                    {"command": "menu", "description": "Apri la Dashboard del Release Vault"},
                                    {"command": "status", "description": "Controlla download in coda e spazio disco"},
                                    {"command": "sync", "description": "Controlla subito nuove release"},
                                ]
                            },
                        )
                    except Exception as e:
                        logger.warning(f"Startup setMyCommands note: {e}")

                resp = await client.get(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                    params={"offset": offset, "timeout": 25},
                    timeout=35.0,
                )
                data = resp.json()
                if not data.get("ok"):
                    await asyncio.sleep(5)
                    continue

                for upd in data.get("result") or []:
                    offset = upd["update_id"] + 1
                    if "message" in upd:
                        await handle_message(client, upd["message"])
                    elif "callback_query" in upd:
                        await handle_callback_query(client, upd["callback_query"])
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling loop error: {e}")
                await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(bot_loop())
