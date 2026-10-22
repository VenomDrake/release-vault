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
VAULT_API_BASE = os.environ.get("VAULT_API_BASE") or os.environ.get("VAULT_API_URL") or "http://127.0.0.1:80"
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

BOT_LANGS = [
    ("it", "🇮🇹 Italiano"),
    ("en", "🇬🇧 English"),
    ("es", "🇪🇸 Español"),
    ("fr", "🇫🇷 Français"),
    ("de", "🇩🇪 Deutsch"),
    ("pt", "🇧🇷 Português"),
    ("ru", "🇷🇺 Русский"),
    ("zh", "🇨🇳 中文"),
    ("ja", "🇯🇵 日本語"),
    ("ko", "🇰🇷 한국어"),
]

I18N: Dict[str, Dict[str, str]] = {
    "it": {
        "bot_title": "Release Vault - Bot Privato",
        "auth_line": "Accesso esclusivo autorizzato",
        "monitored_repos": "Repository monitorati",
        "archived_releases": "Release archiviate",
        "saved_files": "File salvati",
        "disk_space": "Spazio Disco Server",
        "used": "usati",
        "free": "liberi",
        "queue_status": "Stato Coda",
        "queue_empty": "✅ Nessun download in coda (tutto sincronizzato)",
        "queue_paused": "⏸ PAUSA GLOBALE ATTIVA",
        "queue_suspended": "in coda sospesi",
        "downloading": "⚡ In download",
        "in_queue": "in coda",
        "releases_in_queue": "release in coda di download",
        "send_link_hint": "💡 <i>Inviami in qualsiasi momento un link GitHub o Nexus Mods qui in chat per aggiungerlo al Vault!</i>",
        "btn_pause_all": "⏸ Pausa Tutto",
        "btn_resume_all": "▶️ Riprendi Tutto",
        "btn_check_now": "🔄 Controlla Release Ora",
        "btn_refresh": "📊 Aggiorna Stato",
        "btn_language": "🌐 Lingua / Language",
        "btn_back_menu": "⬅️ Torna al Menu",
        "select_lang_title": "🌐 <b>Seleziona la lingua per il Bot:</b>",
        "lang_changed": "✅ Lingua aggiornata in: ",
        "detected": "Rilevato",
        "no_desc": "Nessuna descrizione.",
        "sug_cat": "Categoria consigliata",
        "gen_tags": "Tag auto-generati",
        "selected_mode": "Modalità selezionata",
        "mode_all": "📚 Tutte le release (Storico completo)",
        "mode_latest": "⚡ Solo l'ULTIMA release + successive",
        "btn_mode_all": "Tutte le Release",
        "btn_mode_latest": "Solo Ultima + Succ.",
        "add_prompt": "👇 <b>1) Seleziona se scaricare tutte o solo l'ultima + successive:\n2) Clicca sulla categoria per confermare e avviare:</b>",
        "confirm_in": "✅ Conferma in",
        "recommended": "Consigliata",
        "btn_cancel": "❌ Annulla",
        "cancelled": "❌ Aggiunta repository annullata.",
        "added_success": "✅ <b>Repository aggiunto con successo!</b>",
        "desc_latest_only": "⬇️ <i>Avviato il download SOLO dell'ultima release (e verranno scaricate le future).</i>",
        "desc_all_history": "⬇️ <i>Il download di tutte le release passate e presenti è stato avviato nel Vault.</i>",
        "btn_go_dashboard": "📊 Vai alla Dashboard",
        "cat_title": "Categoria",
        "no_repos_cat": "Nessun repository nella categoria",
        "status_paused": "⏸ IN PAUSA",
        "status_active": "✅ ATTIVO",
        "mode_label": "Modalità",
        "releases_in_archive": "Release in archivio",
        "latest_version": "Ultima versione",
        "date": "Data",
        "size": "Dimensione",
        "no_patch_notes": "Nessuna patch note.",
        "btn_pause_repo": "⏸ Metti in Pausa Repo",
        "btn_resume_repo": "▶️ Riprendi Sincronizzazione",
        "btn_purge_data": "🧹 Pulisci Dati & Riscarica",
        "purge_confirm": "🧹 <b>Confermi la pulizia dei file scaricati per questa repository?</b>\n\nVerranno eliminati i vecchi file dal disco e verrà riavviato subito il download in base alla modalità scelta (es. <i>Solo Ultima + Successive</i>).",
        "btn_purge_confirm": "✅ Sì, Pulisci e Riscarica Ora",
        "purge_done": "✅ <b>Pulizia completata!</b> Riavviato il download con le nuove impostazioni.",
        "btn_back_repo": "⬅️ Torna al Repository",
        "btn_back_cat": "⬅️ Torna a",
        "check_started_repo": "🔄 <b>Controllo nuove release avviato per questo repository!</b>",
        "check_started_all": "🔄 <b>Controllo globale di tutti i repository avviato!</b>",
        "access_denied": "⛔ <b>Accesso negato.</b>\nQuesto bot è privato e riservato esclusivamente al proprietario.",
        "unauthorized_cb": "⛔ Non autorizzato",
        "expired_req": "⚠️ Richiesta scaduta o già elaborata.",
        "inspect_error": "❌ Impossibile analizzare",
        "btn_patch_notes": "📝 Patch Notes",
        "btn_releases_history": "📚 Storico Release",
        "view_patch_notes_hint": "Seleziona una release per visualizzare le sue Patch Notes complete:",
        "patch_notes_truncated": "Note troncate per limiti di Telegram. File completo archiviato su disco in PATCH_NOTES.md",
        "reply_btn_status": "📊 Status",
        "reply_btn_menu": "📁 Categorie",
        "reply_btn_sync": "🔄 Check Release",
        "reply_btn_lang": "🌐 Lingua",
    },
    "en": {
        "bot_title": "Release Vault - Private Bot",
        "auth_line": "Exclusive authorized access",
        "monitored_repos": "Monitored repositories",
        "archived_releases": "Archived releases",
        "saved_files": "Saved files",
        "disk_space": "Server Disk Space",
        "used": "used",
        "free": "free",
        "queue_status": "Queue Status",
        "queue_empty": "✅ No downloads in queue (all synchronized)",
        "queue_paused": "⏸ GLOBAL PAUSE ACTIVE",
        "queue_suspended": "in queue suspended",
        "downloading": "⚡ Downloading",
        "in_queue": "in queue",
        "releases_in_queue": "releases in download queue",
        "send_link_hint": "💡 <i>Send me any GitHub or Nexus Mods link here in chat anytime to add it to the Vault!</i>",
        "btn_pause_all": "⏸ Pause All",
        "btn_resume_all": "▶️ Resume All",
        "btn_check_now": "🔄 Check Releases Now",
        "btn_refresh": "📊 Refresh Status",
        "btn_language": "🌐 Language / Lingua",
        "btn_back_menu": "⬅️ Back to Menu",
        "select_lang_title": "🌐 <b>Select Bot Language:</b>",
        "lang_changed": "✅ Language updated to: ",
        "detected": "Detected",
        "no_desc": "No description.",
        "sug_cat": "Suggested category",
        "gen_tags": "Auto-generated tags",
        "selected_mode": "Selected mode",
        "mode_all": "📚 All releases (Full history)",
        "mode_latest": "⚡ Latest release ONLY + future",
        "btn_mode_all": "All Releases",
        "btn_mode_latest": "Latest Only + Future",
        "add_prompt": "👇 <b>1) Choose whether to download all or only latest + future:\n2) Tap a category to confirm and start:</b>",
        "confirm_in": "✅ Confirm in",
        "recommended": "Recommended",
        "btn_cancel": "❌ Cancel",
        "cancelled": "❌ Repository addition cancelled.",
        "added_success": "✅ <b>Repository added successfully!</b>",
        "desc_latest_only": "⬇️ <i>Downloading ONLY the latest release (future updates will be archived).</i>",
        "desc_all_history": "⬇️ <i>Archiving of all past and present releases has been started.</i>",
        "btn_go_dashboard": "📊 Go to Dashboard",
        "cat_title": "Category",
        "no_repos_cat": "No repositories in category",
        "status_paused": "⏸ PAUSED",
        "status_active": "✅ ACTIVE",
        "mode_label": "Mode",
        "releases_in_archive": "Archived releases",
        "latest_version": "Latest version",
        "date": "Date",
        "size": "Size",
        "no_patch_notes": "No patch notes.",
        "btn_pause_repo": "⏸ Pause Repo",
        "btn_resume_repo": "▶️ Resume Sync",
        "btn_purge_data": "🧹 Clean Data & Re-download",
        "purge_confirm": "🧹 <b>Confirm data wipe for this repository?</b>\n\nOld files will be removed from disk and download will restart according to the selected mode (e.g. <i>Latest Only + Future</i>).",
        "btn_purge_confirm": "✅ Yes, Clean & Re-download Now",
        "purge_done": "✅ <b>Clean completed!</b> Re-download started with new settings.",
        "btn_back_repo": "⬅️ Back to Repository",
        "btn_back_cat": "⬅️ Back to",
        "check_started_repo": "🔄 <b>New release check started for this repository!</b>",
        "check_started_all": "🔄 <b>Global release check started for all repositories!</b>",
        "access_denied": "⛔ <b>Access denied.</b>\nThis bot is private and restricted to the owner.",
        "unauthorized_cb": "⛔ Unauthorized",
        "expired_req": "⚠️ Request expired or already processed.",
        "inspect_error": "❌ Unable to inspect",
        "btn_patch_notes": "📝 Patch Notes",
        "btn_releases_history": "📚 Release History",
        "view_patch_notes_hint": "Select a release to view its complete Patch Notes:",
        "patch_notes_truncated": "Notes truncated due to Telegram length limit. Full file archived on disk in PATCH_NOTES.md",
        "reply_btn_status": "📊 Status",
        "reply_btn_menu": "📁 Categories",
        "reply_btn_sync": "🔄 Check Releases",
        "reply_btn_lang": "🌐 Language",
    },
    "es": {
        "bot_title": "Release Vault - Bot Privado",
        "auth_line": "Acceso exclusivo autorizado",
        "monitored_repos": "Repositorios monitoreados",
        "archived_releases": "Releases archivadas",
        "saved_files": "Archivos guardados",
        "disk_space": "Espacio Disco Servidor",
        "used": "usados",
        "free": "libres",
        "queue_status": "Estado de la Cola",
        "queue_empty": "✅ Sin descargas en cola (todo sincronizado)",
        "queue_paused": "⏸ PAUSA GLOBAL ACTIVA",
        "queue_suspended": "en cola suspendidos",
        "downloading": "⚡ Descargando",
        "in_queue": "en cola",
        "releases_in_queue": "releases en cola de descarga",
        "send_link_hint": "💡 <i>¡Envíame un enlace de GitHub o Nexus Mods aquí para agregarlo al Vault!</i>",
        "btn_pause_all": "⏸ Pausar Todo",
        "btn_resume_all": "▶️ Reanudar Todo",
        "btn_check_now": "🔄 Comprobar Releases Ahora",
        "btn_refresh": "📊 Actualizar Estado",
        "btn_language": "🌐 Idioma / Language",
        "btn_back_menu": "⬅️ Volver al Menú",
        "select_lang_title": "🌐 <b>Selecciona el idioma del Bot:</b>",
        "lang_changed": "✅ Idioma actualizado a: ",
        "detected": "Detectado",
        "no_desc": "Sin descripción.",
        "sug_cat": "Categoría sugerida",
        "gen_tags": "Etiquetas automáticas",
        "selected_mode": "Modo seleccionado",
        "mode_all": "📚 Todas las releases (Historial completo)",
        "mode_latest": "⚡ Solo ÚLTIMA release + futuras",
        "btn_mode_all": "Todas las Releases",
        "btn_mode_latest": "Solo Última + Futuras",
        "add_prompt": "👇 <b>1) Selecciona si descargar todas o solo la última + futuras:\n2) Toca una categoría para confirmar e iniciar:</b>",
        "confirm_in": "✅ Confirmar en",
        "recommended": "Recomendada",
        "btn_cancel": "❌ Cancelar",
        "cancelled": "❌ Adición de repositorio cancelada.",
        "added_success": "✅ <b>¡Repositorio agregado con éxito!</b>",
        "desc_latest_only": "⬇️ <i>Descargando SOLO la última release (las futuras se archivarán).</i>",
        "desc_all_history": "⬇️ <i>Se inició el archivado de todas las releases pasadas y presentes.</i>",
        "btn_go_dashboard": "📊 Ir al Panel",
        "cat_title": "Categoría",
        "no_repos_cat": "No hay repositorios en la categoría",
        "status_paused": "⏸ EN PAUSA",
        "status_active": "✅ ACTIVO",
        "mode_label": "Modo",
        "releases_in_archive": "Releases en archivo",
        "latest_version": "Última versión",
        "date": "Fecha",
        "size": "Tamaño",
        "no_patch_notes": "Sin notas de parche.",
        "btn_pause_repo": "⏸ Pausar Repo",
        "btn_resume_repo": "▶️ Reanudar Sync",
        "btn_purge_data": "🧹 Limpiar Datos y Redescargar",
        "purge_confirm": "🧹 <b>¿Confirmas borrar los archivos de este repositorio?</b>\n\nSe eliminarán los archivos del disco y se reiniciará la descarga según el modo elegido.",
        "btn_purge_confirm": "✅ Sí, Limpiar y Redescargar",
        "purge_done": "✅ <b>¡Limpieza completada!</b> Descarga reiniciada con las nuevas opciones.",
        "btn_back_repo": "⬅️ Volver al Repositorio",
        "btn_back_cat": "⬅️ Volver a",
        "check_started_repo": "🔄 <b>¡Comprobación de releases iniciada para este repositorio!</b>",
        "check_started_all": "🔄 <b>¡Comprobación global iniciada para todos los repositorios!</b>",
        "access_denied": "⛔ <b>Acceso denegado.</b>\nEste bot es privado y exclusivo del propietario.",
        "unauthorized_cb": "⛔ No autorizado",
        "expired_req": "⚠️ Solicitud expirada o ya procesada.",
        "inspect_error": "❌ Imposible analizar",
        "btn_patch_notes": "📝 Notas del Parche",
        "btn_releases_history": "📚 Historial de Versiones",
        "view_patch_notes_hint": "Selecciona una versión para ver sus Notas de parche completas:",
        "patch_notes_truncated": "Notas truncadas por límites de Telegram. Archivo completo guardado en disco en PATCH_NOTES.md",
        "reply_btn_status": "📊 Estado",
        "reply_btn_menu": "📁 Categorías",
        "reply_btn_sync": "🔄 Verificar Versiones",
        "reply_btn_lang": "🌐 Idioma",
    },
    "fr": {
        "bot_title": "Release Vault - Bot Privé",
        "auth_line": "Accès exclusif autorisé",
        "monitored_repos": "Dépôts surveillés",
        "archived_releases": "Releases archivées",
        "saved_files": "Fichiers enregistrés",
        "disk_space": "Espace Disque Serveur",
        "used": "utilisés",
        "free": "libres",
        "queue_status": "État de la File",
        "queue_empty": "✅ Aucun téléchargement en attente (tout est synchronisé)",
        "queue_paused": "⏸ PAUSE GLOBALE ACTIVE",
        "queue_suspended": "en file suspendus",
        "downloading": "⚡ En téléchargement",
        "in_queue": "en attente",
        "releases_in_queue": "releases dans la file d'attente",
        "send_link_hint": "💡 <i>Envoyez un lien GitHub ou Nexus Mods dans le chat pour l'ajouter au Vault !</i>",
        "btn_pause_all": "⏸ Mettre en pause",
        "btn_resume_all": "▶️ Reprendre tout",
        "btn_check_now": "🔄 Vérifier les releases",
        "btn_refresh": "📊 Actualiser l'état",
        "btn_language": "🌐 Langue / Language",
        "btn_back_menu": "⬅️ Retour au Menu",
        "select_lang_title": "🌐 <b>Sélectionnez la langue du Bot :</b>",
        "lang_changed": "✅ Langue mise à jour en : ",
        "detected": "Détecté",
        "no_desc": "Aucune description.",
        "sug_cat": "Catégorie suggérée",
        "gen_tags": "Tags générés",
        "selected_mode": "Mode sélectionné",
        "mode_all": "📚 Toutes les releases (Historique complet)",
        "mode_latest": "⚡ Dernière release UNIQUEMENT + futures",
        "btn_mode_all": "Toutes les releases",
        "btn_mode_latest": "Dernière + Futures",
        "add_prompt": "👇 <b>1) Choisissez si vous voulez tout télécharger ou seulement la dernière :\n2) Cliquez sur la catégorie pour valider :</b>",
        "confirm_in": "✅ Confirmer dans",
        "recommended": "Recommandée",
        "btn_cancel": "❌ Annuler",
        "cancelled": "❌ Ajout du dépôt annulé.",
        "added_success": "✅ <b>Dépôt ajouté avec succès !</b>",
        "desc_latest_only": "⬇️ <i>Téléchargement de la DERNIÈRE release uniquement (les futures seront archivées).</i>",
        "desc_all_history": "⬇️ <i>Archivage de toutes les releases passées et présentes démarré.</i>",
        "btn_go_dashboard": "📊 Aller au Tableau de bord",
        "cat_title": "Catégorie",
        "no_repos_cat": "Aucun dépôt dans la catégorie",
        "status_paused": "⏸ EN PAUSE",
        "status_active": "✅ ACTIF",
        "mode_label": "Mode",
        "releases_in_archive": "Releases archivées",
        "latest_version": "Dernière version",
        "date": "Date",
        "size": "Taille",
        "no_patch_notes": "Aucune note de version.",
        "btn_pause_repo": "⏸ Mettre en pause",
        "btn_resume_repo": "▶️ Reprendre la synchro",
        "btn_purge_data": "🧹 Nettoyer et retélécharger",
        "purge_confirm": "🧹 <b>Confirmer la suppression des fichiers de ce dépôt ?</b>\n\nLes fichiers seront effacés du disque et le téléchargement redémarrera selon le mode sélectionné.",
        "btn_purge_confirm": "✅ Oui, Nettoyer et Retélécharger",
        "purge_done": "✅ <b>Nettoyage terminé !</b> Téléchargement relancé.",
        "btn_back_repo": "⬅️ Retour au Dépôt",
        "btn_back_cat": "⬅️ Retour à",
        "check_started_repo": "🔄 <b>Vérification des nouvelles releases lancée pour ce dépôt !</b>",
        "check_started_all": "🔄 <b>Vérification globale lancée pour tous les dépôts !</b>",
        "access_denied": "⛔ <b>Accès refusé.</b>\nCe bot est privé et réservé exclusivement à son propriétaire.",
        "unauthorized_cb": "⛔ Non autorisé",
        "expired_req": "⚠️ Demande expirée ou déjà traitée.",
        "inspect_error": "❌ Impossible d'analyser",
        "btn_patch_notes": "📝 Notes de Version",
        "btn_releases_history": "📚 Historique des Versions",
        "view_patch_notes_hint": "Sélectionnez une version pour afficher ses Notes de version complètes :",
        "patch_notes_truncated": "Notes tronquées en raison de la limite de Telegram. Fichier complet sur disque dans PATCH_NOTES.md",
        "reply_btn_status": "📊 Statut",
        "reply_btn_menu": "📁 Catégories",
        "reply_btn_sync": "🔄 Vérifier Mises à jour",
        "reply_btn_lang": "🌐 Langue",
    },
    "de": {
        "bot_title": "Release Vault - Privater Bot",
        "auth_line": "Exklusiver autorisierter Zugriff",
        "monitored_repos": "Überwachte Repositories",
        "archived_releases": "Archivierte Releases",
        "saved_files": "Gespeicherte Dateien",
        "disk_space": "Server-Festplattenspeicher",
        "used": "belegt",
        "free": "frei",
        "queue_status": "Warteschlangen-Status",
        "queue_empty": "✅ Keine Downloads in der Warteschlange (alles synchronisiert)",
        "queue_paused": "⏸ GLOBALE PAUSE AKTIV",
        "queue_suspended": "in Warteschlange pausiert",
        "downloading": "⚡ Lädt herunter",
        "in_queue": "in Warteschlange",
        "releases_in_queue": "Releases in der Download-Warteschlange",
        "send_link_hint": "💡 <i>Sende mir jederzeit einen GitHub- oder Nexus-Mods-Link im Chat, um ihn zum Vault hinzuzufügen!</i>",
        "btn_pause_all": "⏸ Alles pausieren",
        "btn_resume_all": "▶️ Alles fortsetzen",
        "btn_check_now": "🔄 Jetzt auf Releases prüfen",
        "btn_refresh": "📊 Status aktualisieren",
        "btn_language": "🌐 Sprache / Language",
        "btn_back_menu": "⬅️ Zurück zum Menü",
        "select_lang_title": "🌐 <b>Wähle die Sprache für den Bot:</b>",
        "lang_changed": "✅ Sprache geändert auf: ",
        "detected": "Erkannt",
        "no_desc": "Keine Beschreibung.",
        "sug_cat": "Empfohlene Kategorie",
        "gen_tags": "Automatische Tags",
        "selected_mode": "Ausgewählter Modus",
        "mode_all": "📚 Alle Releases (Kompletter Verlauf)",
        "mode_latest": "⚡ NUR neueste Release + zukünftige",
        "btn_mode_all": "Alle Releases",
        "btn_mode_latest": "Nur Neueste + Zukünftige",
        "add_prompt": "👇 <b>1) Wähle, ob alle oder nur die neueste heruntergeladen werden soll:\n2) Klicke auf die Kategorie zur Bestätigung:</b>",
        "confirm_in": "✅ Bestätigen in",
        "recommended": "Empfohlen",
        "btn_cancel": "❌ Abbrechen",
        "cancelled": "❌ Hinzufügen abgebrochen.",
        "added_success": "✅ <b>Repository erfolgreich hinzugefügt!</b>",
        "desc_latest_only": "⬇️ <i>Download NUR der neuesten Release gestartet (zukünftige werden archiviert).</i>",
        "desc_all_history": "⬇️ <i>Archivierung aller bisherigen und aktuellen Releases wurde gestartet.</i>",
        "btn_go_dashboard": "📊 Zum Dashboard",
        "cat_title": "Kategorie",
        "no_repos_cat": "Keine Repositories in dieser Kategorie",
        "status_paused": "⏸ PAUSIERT",
        "status_active": "✅ AKTIV",
        "mode_label": "Modus",
        "releases_in_archive": "Releases im Archiv",
        "latest_version": "Neueste Version",
        "date": "Datum",
        "size": "Größe",
        "no_patch_notes": "Keine Patchnotizen.",
        "btn_pause_repo": "⏸ Repo pausieren",
        "btn_resume_repo": "▶️ Sync fortsetzen",
        "btn_purge_data": "🧹 Daten bereinigen & neu laden",
        "purge_confirm": "🧹 <b>Möchtest du die heruntergeladenen Dateien dieses Repositories wirklich löschen?</b>\n\nAlte Dateien werden gelöscht und der Download startet nach dem gewählten Modus neu.",
        "btn_purge_confirm": "✅ Ja, Bereinigen & Neu laden",
        "purge_done": "✅ <b>Bereinigung abgeschlossen!</b> Download neu gestartet.",
        "btn_back_repo": "⬅️ Zurück zum Repository",
        "btn_back_cat": "⬅️ Zurück zu",
        "check_started_repo": "🔄 <b>Prüfung auf neue Releases für dieses Repository gestartet!</b>",
        "check_started_all": "🔄 <b>Globale Prüfung für alle Repositories gestartet!</b>",
        "access_denied": "⛔ <b>Zugriff verweigert.</b>\nDieser Bot ist privat und nur für den Besitzer zugänglich.",
        "unauthorized_cb": "⛔ Nicht autorisiert",
        "expired_req": "⚠️ Anfrage abgelaufen oder bereits verarbeitet.",
        "inspect_error": "❌ Analyse nicht möglich",
        "btn_patch_notes": "📝 Patch-Hinweise",
        "btn_releases_history": "📚 Versionsverlauf",
        "view_patch_notes_hint": "Wähle eine Version, um vollständige Patch-Hinweise anzuzeigen:",
        "patch_notes_truncated": "Hinweise wegen Telegram-Längenbegrenzung gekürzt. Vollständige Datei auf Festplatte in PATCH_NOTES.md",
        "reply_btn_status": "📊 Status",
        "reply_btn_menu": "📁 Kategorien",
        "reply_btn_sync": "🔄 Releases prüfen",
        "reply_btn_lang": "🌐 Sprache",
    },
    "pt": {
        "bot_title": "Release Vault - Bot Privado",
        "auth_line": "Acesso exclusivo autorizado",
        "monitored_repos": "Repositórios monitorados",
        "archived_releases": "Releases arquivadas",
        "saved_files": "Arquivos salvos",
        "disk_space": "Espaço em Disco do Servidor",
        "used": "usados",
        "free": "livres",
        "queue_status": "Status da Fila",
        "queue_empty": "✅ Nenhum download na fila (tudo sincronizado)",
        "queue_paused": "⏸ PAUSA GLOBAL ATIVA",
        "queue_suspended": "na fila suspensos",
        "downloading": "⚡ Baixando",
        "in_queue": "na fila",
        "releases_in_queue": "releases na fila de download",
        "send_link_hint": "💡 <i>Envie um link do GitHub ou Nexus Mods aqui no chat para adicioná-lo ao Vault!</i>",
        "btn_pause_all": "⏸ Pausar Tudo",
        "btn_resume_all": "▶️ Retomar Tudo",
        "btn_check_now": "🔄 Verificar Releases Agora",
        "btn_refresh": "📊 Atualizar Status",
        "btn_language": "🌐 Idioma / Language",
        "btn_back_menu": "⬅️ Voltar ao Menu",
        "select_lang_title": "🌐 <b>Selecione o idioma do Bot:</b>",
        "lang_changed": "✅ Idioma atualizado para: ",
        "detected": "Detectado",
        "no_desc": "Sem descrição.",
        "sug_cat": "Categoria sugerida",
        "gen_tags": "Tags geradas",
        "selected_mode": "Modo selecionado",
        "mode_all": "📚 Todas as releases (Histórico completo)",
        "mode_latest": "⚡ Apenas a ÚLTIMA release + futuras",
        "btn_mode_all": "Todas as Releases",
        "btn_mode_latest": "Apenas Última + Futuras",
        "add_prompt": "👇 <b>1) Escolha se quer baixar todas ou apenas a última:\n2) Toque em uma categoria para confirmar:</b>",
        "confirm_in": "✅ Confirmar em",
        "recommended": "Recomendada",
        "btn_cancel": "❌ Cancelar",
        "cancelled": "❌ Adição cancelada.",
        "added_success": "✅ <b>Repositório adicionado com sucesso!</b>",
        "desc_latest_only": "⬇️ <i>Baixando APENAS a última release (as futuras serão arquivadas).</i>",
        "desc_all_history": "⬇️ <i>Arquivamento de todas as releases iniciado no Vault.</i>",
        "btn_go_dashboard": "📊 Ir para o Painel",
        "cat_title": "Categoria",
        "no_repos_cat": "Nenhum repositório nesta categoria",
        "status_paused": "⏸ EM PAUSA",
        "status_active": "✅ ATIVO",
        "mode_label": "Modo",
        "releases_in_archive": "Releases no arquivo",
        "latest_version": "Última versão",
        "date": "Data",
        "size": "Tamanho",
        "no_patch_notes": "Sem notas de lançamento.",
        "btn_pause_repo": "⏸ Pausar Repo",
        "btn_resume_repo": "▶️ Retomar Sync",
        "btn_purge_data": "🧹 Limpar Dados e Rebaixar",
        "purge_confirm": "🧹 <b>Confirma a limpeza dos arquivos deste repositório?</b>\n\nOs arquivos serão apagados do disco e o download recomeçará segundo o modo escolhido.",
        "btn_purge_confirm": "✅ Sim, Limpar e Rebaixar",
        "purge_done": "✅ <b>Limpeza concluída!</b> Download reiniciado.",
        "btn_back_repo": "⬅️ Voltar ao Repositório",
        "btn_back_cat": "⬅️ Voltar para",
        "check_started_repo": "🔄 <b>Verificação de novas releases iniciada para este repositório!</b>",
        "check_started_all": "🔄 <b>Verificação global iniciada para todos os repositórios!</b>",
        "access_denied": "⛔ <b>Acesso negado.</b>\nEste bot é privado e restrito ao proprietário.",
        "unauthorized_cb": "⛔ Não autorizado",
        "expired_req": "⚠️ Pedido expirado ou já processado.",
        "inspect_error": "❌ Não foi possível inspecionar",
        "btn_patch_notes": "📝 Notas da Versão",
        "btn_releases_history": "📚 Histórico de Versões",
        "view_patch_notes_hint": "Selecione uma versão para visualizar as Notas completas:",
        "patch_notes_truncated": "Notas truncadas pelo limite do Telegram. Arquivo completo no disco em PATCH_NOTES.md",
        "reply_btn_status": "📊 Status",
        "reply_btn_menu": "📁 Categorias",
        "reply_btn_sync": "🔄 Verificar Versões",
        "reply_btn_lang": "🌐 Idioma",
    },
    "ru": {
        "bot_title": "Release Vault - Приватный Бот",
        "auth_line": "Эксклюзивный авторизованный доступ",
        "monitored_repos": "Отслеживаемые репозитории",
        "archived_releases": "Архивированные релизы",
        "saved_files": "Сохранённые файлы",
        "disk_space": "Дисковое пространство сервера",
        "used": "занято",
        "free": "свободно",
        "queue_status": "Статус очереди",
        "queue_empty": "✅ В очереди нет загрузок (всё синхронизировано)",
        "queue_paused": "⏸ ГЛОБАЛЬНАЯ ПАУЗА АКТИВНА",
        "queue_suspended": "в очереди приостановлено",
        "downloading": "⚡ Загрузка",
        "in_queue": "в очереди",
        "releases_in_queue": "релизов в очереди на скачивание",
        "send_link_hint": "💡 <i>Отправьте ссылку на GitHub или Nexus Mods сюда в чат, чтобы добавить в Vault!</i>",
        "btn_pause_all": "⏸ Поставить всё на паузу",
        "btn_resume_all": "▶️ Возобновить всё",
        "btn_check_now": "🔄 Проверить релизы сейчас",
        "btn_refresh": "📊 Обновить статус",
        "btn_language": "🌐 Язык / Language",
        "btn_back_menu": "⬅️ Назад в меню",
        "select_lang_title": "🌐 <b>Выберите язык для бота:</b>",
        "lang_changed": "✅ Язык изменён на: ",
        "detected": "Обнаружено",
        "no_desc": "Нет описания.",
        "sug_cat": "Рекомендуемая категория",
        "gen_tags": "Теги",
        "selected_mode": "Выбранный режим",
        "mode_all": "📚 Все релизы (Полная история)",
        "mode_latest": "⚡ Только ПОСЛЕДНИЙ релиз + будущие",
        "btn_mode_all": "Все релизы",
        "btn_mode_latest": "Только последний + буд.",
        "add_prompt": "👇 <b>1) Выберите режим скачивания:\n2) Нажмите на категорию для подтверждения:</b>",
        "confirm_in": "✅ Подтвердить в",
        "recommended": "Рекомендуется",
        "btn_cancel": "❌ Отмена",
        "cancelled": "❌ Добавление отменено.",
        "added_success": "✅ <b>Репозиторий успешно добавлен!</b>",
        "desc_latest_only": "⬇️ <i>Скачивается ТОЛЬКО последний релиз (будущие будут архивироваться).</i>",
        "desc_all_history": "⬇️ <i>Запущена архивация всех прошлых и текущих релизов.</i>",
        "btn_go_dashboard": "📊 Перейти в панель",
        "cat_title": "Категория",
        "no_repos_cat": "В этой категории нет репозиториев",
        "status_paused": "⏸ НА ПАУЗЕ",
        "status_active": "✅ АКТИВЕН",
        "mode_label": "Режим",
        "releases_in_archive": "Релизов в архиве",
        "latest_version": "Последняя версия",
        "date": "Дата",
        "size": "Размер",
        "no_patch_notes": "Нет описания релиза.",
        "btn_pause_repo": "⏸ Приостановить репо",
        "btn_resume_repo": "▶️ Возобновить синхронизацию",
        "btn_purge_data": "🧹 Очистить данные и перекачать",
        "purge_confirm": "🧹 <b>Подтверждаете удаление скачанных файлов этого репозитория?</b>\n\nФайлы будут удалены с диска, и загрузка начнётся заново в соответствии с выбранным режимом.",
        "btn_purge_confirm": "✅ Да, Очистить и Перекачать",
        "purge_done": "✅ <b>Очистка завершена!</b> Загрузка перезапущена.",
        "btn_back_repo": "⬅️ Назад к репозиторию",
        "btn_back_cat": "⬅️ Назад в",
        "check_started_repo": "🔄 <b>Проверка новых релизов запущена для этого репозитория!</b>",
        "check_started_all": "🔄 <b>Глобальная проверка запущена для всех репозиториев!</b>",
        "access_denied": "⛔ <b>Доступ запрещён.</b>\nЭтот бот приватный и доступен только владельцу.",
        "unauthorized_cb": "⛔ Не авторизован",
        "expired_req": "⚠️ Запрос устарел или уже обработан.",
        "inspect_error": "❌ Не удалось проанализировать",
        "btn_patch_notes": "📝 Список изменений",
        "btn_releases_history": "📚 История релизов",
        "view_patch_notes_hint": "Выберите релиз для просмотра полного списка изменений:",
        "patch_notes_truncated": "Заметки сокращены из-за лимита длины Telegram. Полный файл на диске в PATCH_NOTES.md",
        "reply_btn_status": "📊 Статус",
        "reply_btn_menu": "📁 Категории",
        "reply_btn_sync": "🔄 Проверить релизы",
        "reply_btn_lang": "🌐 Язык",
    },
    "zh": {
        "bot_title": "Release Vault - 私人机器人",
        "auth_line": "独家授权访问",
        "monitored_repos": "监控中的仓库",
        "archived_releases": "已归档版本",
        "saved_files": "已保存文件",
        "disk_space": "服务器磁盘空间",
        "used": "已用",
        "free": "可用",
        "queue_status": "队列状态",
        "queue_empty": "✅ 队列中无下载任务（全部已同步）",
        "queue_paused": "⏸ 全局暂停已开启",
        "queue_suspended": "个任务已暂停",
        "downloading": "⚡ 正在下载",
        "in_queue": "排队中",
        "releases_in_queue": "个版本等待下载",
        "send_link_hint": "💡 <i>随时将 GitHub 或 Nexus Mods 链接发送到此处即可加入 Vault！</i>",
        "btn_pause_all": "⏸ 全部暂停",
        "btn_resume_all": "▶️ 全部恢复",
        "btn_check_now": "🔄 立即检查更新",
        "btn_refresh": "📊 刷新状态",
        "btn_language": "🌐 语言 / Language",
        "btn_back_menu": "⬅️ 返回菜单",
        "select_lang_title": "🌐 <b>选择机器人语言：</b>",
        "lang_changed": "✅ 语言已更新为：",
        "detected": "已识别",
        "no_desc": "暂无描述。",
        "sug_cat": "建议分类",
        "gen_tags": "自动标签",
        "selected_mode": "选择的模式",
        "mode_all": "📚 全部版本（完整历史）",
        "mode_latest": "⚡ 仅最新版本 + 后续更新",
        "btn_mode_all": "全部版本",
        "btn_mode_latest": "仅最新 + 后续",
        "add_prompt": "👇 <b>1) 选择下载全部历史还是仅最新版本：\n2) 点击分类以确认并开始：</b>",
        "confirm_in": "✅ 确认加入",
        "recommended": "推荐",
        "btn_cancel": "❌ 取消",
        "cancelled": "❌ 已取消添加仓库。",
        "added_success": "✅ <b>仓库添加成功！</b>",
        "desc_latest_only": "⬇️ <i>仅下载最新版本（未来新版本将自动归档）。</i>",
        "desc_all_history": "⬇️ <i>已开始在 Vault 中归档历史及当前所有版本。</i>",
        "btn_go_dashboard": "📊 前往仪表盘",
        "cat_title": "分类",
        "no_repos_cat": "该分类下暂无仓库",
        "status_paused": "⏸ 已暂停",
        "status_active": "✅ 运行中",
        "mode_label": "模式",
        "releases_in_archive": "归档版本数",
        "latest_version": "最新版本",
        "date": "日期",
        "size": "大小",
        "no_patch_notes": "暂无更新说明。",
        "btn_pause_repo": "⏸ 暂停此仓库",
        "btn_resume_repo": "▶️ 恢复同步",
        "btn_purge_data": "🧹 清除数据并重新下载",
        "purge_confirm": "🧹 <b>确认清空此仓库已下载的文件？</b>\n\n旧文件将被删除，系统将按照设定的模式重新开始下载。",
        "btn_purge_confirm": "✅ 确认清理并重新下载",
        "purge_done": "✅ <b>清理完成！</b> 已重新开始下载。",
        "btn_back_repo": "⬅️ 返回仓库详情",
        "btn_back_cat": "⬅️ 返回到",
        "check_started_repo": "🔄 <b>已开始检查此仓库的最新版本！</b>",
        "check_started_all": "🔄 <b>已开始对所有仓库进行全局版本检查！</b>",
        "access_denied": "⛔ <b>访问被拒绝。</b>\n此机器人为私人专享，仅限所有者使用。",
        "unauthorized_cb": "⛔ 未经授权",
        "expired_req": "⚠️ 请求已过期或已处理。",
        "inspect_error": "❌ 无法解析",
        "btn_patch_notes": "📝 更新日志",
        "btn_releases_history": "📚 版本历史",
        "view_patch_notes_hint": "选择一个版本以查看其完整的更新日志：",
        "patch_notes_truncated": "因 Telegram 长度限制内容已截断。完整文件保存在磁盘 PATCH_NOTES.md 中",
        "reply_btn_status": "📊 状态",
        "reply_btn_menu": "📁 分类",
        "reply_btn_sync": "🔄 检查更新",
        "reply_btn_lang": "🌐 语言",
    },
    "ja": {
        "bot_title": "Release Vault - プライベートボット",
        "auth_line": "専用の承認済みアクセス",
        "monitored_repos": "監視中のリポジトリ",
        "archived_releases": "アーカイブ済みリリース",
        "saved_files": "保存済みファイル",
        "disk_space": "サーバーディスク容量",
        "used": "使用中",
        "free": "空き",
        "queue_status": "キューの状態",
        "queue_empty": "✅ ダウンロードキューはありません（すべて同期済み）",
        "queue_paused": "⏸ 全体一時停止中",
        "queue_suspended": "件のキューが停止中",
        "downloading": "⚡ ダウンロード中",
        "in_queue": "キュー内",
        "releases_in_queue": "件のリリースが待機中",
        "send_link_hint": "💡 <i>GitHubまたはNexus Modsのリンクをチャットに送信するとVaultに追加されます！</i>",
        "btn_pause_all": "⏸ 全て一時停止",
        "btn_resume_all": "▶️ 全て再開",
        "btn_check_now": "🔄 今すぐリリースを確認",
        "btn_refresh": "📊 状態を更新",
        "btn_language": "🌐 言語 / Language",
        "btn_back_menu": "⬅️ メニューに戻る",
        "select_lang_title": "🌐 <b>ボットの言語を選択してください:</b>",
        "lang_changed": "✅ 言語が変更されました: ",
        "detected": "検出済み",
        "no_desc": "説明がありません。",
        "sug_cat": "おすすめカテゴリ",
        "gen_tags": "自動生成タグ",
        "selected_mode": "選択中のモード",
        "mode_all": "📚 全リリース（完全な履歴）",
        "mode_latest": "⚡ 最新リリースのみ＋今後の更新",
        "btn_mode_all": "全リリース",
        "btn_mode_latest": "最新のみ＋今後",
        "add_prompt": "👇 <b>1) 全てダウンロードするか最新のみにするかを選択:\n2) カテゴリをタップして確定:</b>",
        "confirm_in": "✅ 追加先",
        "recommended": "推奨",
        "btn_cancel": "❌ キャンセル",
        "cancelled": "❌ 追加をキャンセルしました。",
        "added_success": "✅ <b>リポジトリが正常に追加されました！</b>",
        "desc_latest_only": "⬇️ <i>最新リリースのみダウンロードを開始しました（今後の更新も保存されます）。</i>",
        "desc_all_history": "⬇️ <i>過去および現在のすべてのリリースのアーカイブを開始しました。</i>",
        "btn_go_dashboard": "📊 ダッシュボードへ",
        "cat_title": "カテゴリ",
        "no_repos_cat": "このカテゴリにリポジトリはありません",
        "status_paused": "⏸ 一時停止中",
        "status_active": "✅ 稼働中",
        "mode_label": "モード",
        "releases_in_archive": "保存済みリリース数",
        "latest_version": "最新バージョン",
        "date": "日付",
        "size": "サイズ",
        "no_patch_notes": "パッチノートはありません。",
        "btn_pause_repo": "⏸ リポジトリを一時停止",
        "btn_resume_repo": "▶️ 同期を再開",
        "btn_purge_data": "🧹 データを消去して再取得",
        "purge_confirm": "🧹 <b>このリポジトリの保存済みファイルを削除しますか？</b>\n\n古いファイルは削除され、選択したモードに基づいて再ダウンロードされます。",
        "btn_purge_confirm": "✅ はい、消去して再取得",
        "purge_done": "✅ <b>消去完了！</b> 新しい設定でダウンロードを再開しました。",
        "btn_back_repo": "⬅️ リポジトリに戻る",
        "btn_back_cat": "⬅️ 戻る: ",
        "check_started_repo": "🔄 <b>このリポジトリの新規リリース確認を開始しました！</b>",
        "check_started_all": "🔄 <b>全リポジトリの全体リリース確認を開始しました！</b>",
        "access_denied": "⛔ <b>アクセスが拒否されました。</b>\nこのボットはプライベートであり、所有者専用です。",
        "unauthorized_cb": "⛔ 権限がありません",
        "expired_req": "⚠️ リクエストの期限が切れているか、すでに処理されています。",
        "inspect_error": "❌ 解析できませんでした",
        "btn_patch_notes": "📝 パッチノート",
        "btn_releases_history": "📚 リリース履歴",
        "view_patch_notes_hint": "完全なパッチノートを表示するリリースを選択してください：",
        "patch_notes_truncated": "Telegramの文字制限のため短縮されました。完全なファイルはディスクの PATCH_NOTES.md にあります",
        "reply_btn_status": "📊 ステータス",
        "reply_btn_menu": "📁 カテゴリ",
        "reply_btn_sync": "🔄 リリース確認",
        "reply_btn_lang": "🌐 言語",
    },
    "ko": {
        "bot_title": "Release Vault - 전용 봇",
        "auth_line": "승인된 단독 액세스 권한",
        "monitored_repos": "모니터링 중인 저장소",
        "archived_releases": "아카이브된 릴리스",
        "saved_files": "저장된 파일",
        "disk_space": "서버 디스크 공간",
        "used": "사용 중",
        "free": "여유",
        "queue_status": "대기열 상태",
        "queue_empty": "✅ 대기열에 다운로드 작업이 없습니다 (모두 동기화됨)",
        "queue_paused": "⏸ 전체 일시 중지 활성화됨",
        "queue_suspended": "개 대기 작업 일시 중지됨",
        "downloading": "⚡ 다운로드 중",
        "in_queue": "대기 중",
        "releases_in_queue": "개 릴리스가 다운로드 대기 중",
        "send_link_hint": "💡 <i>채팅창에 GitHub 또는 Nexus Mods 링크를 보내면 Vault에 추가됩니다!</i>",
        "btn_pause_all": "⏸ 전체 일시 중지",
        "btn_resume_all": "▶️ 전체 재개",
        "btn_check_now": "🔄 지금 릴리스 확인",
        "btn_refresh": "📊 상태 새로고침",
        "btn_language": "🌐 언어 / Language",
        "btn_back_menu": "⬅️ 메뉴로 돌아가기",
        "select_lang_title": "🌐 <b>봇의 언어를 선택하세요:</b>",
        "lang_changed": "✅ 언어가 변경되었습니다: ",
        "detected": "감지됨",
        "no_desc": "설명이 없습니다.",
        "sug_cat": "추천 카테고리",
        "gen_tags": "자동 생성된 태그",
        "selected_mode": "선택된 모드",
        "mode_all": "📚 모든 릴리스 (전체 기록)",
        "mode_latest": "⚡ 최신 릴리스만 + 향후 업데이트",
        "btn_mode_all": "모든 릴리스",
        "btn_mode_latest": "최신만 + 향후",
        "add_prompt": "👇 <b>1) 전체 다운로드 또는 최신만 다운로드 선택:\n2) 카테고리를 눌러 확인 및 시작:</b>",
        "confirm_in": "✅ 추가 확인:",
        "recommended": "추천",
        "btn_cancel": "❌ 취소",
        "cancelled": "❌ 저장소 추가가 취소되었습니다.",
        "added_success": "✅ <b>저장소가 성공적으로 추가되었습니다!</b>",
        "desc_latest_only": "⬇️ <i>최신 릴리스만 다운로드를 시작했습니다 (향후 버전도 자동 아카이브됩니다).</i>",
        "desc_all_history": "⬇️ <i>과거 및 현재의 모든 릴리스 아카이빙을 시작했습니다.</i>",
        "btn_go_dashboard": "📊 대시보드로 이동",
        "cat_title": "카테고리",
        "no_repos_cat": "이 카테고리에 저장소가 없습니다",
        "status_paused": "⏸ 일시 중지됨",
        "status_active": "✅ 활성",
        "mode_label": "모드",
        "releases_in_archive": "아카이브된 릴리스 수",
        "latest_version": "최신 버전",
        "date": "날짜",
        "size": "크기",
        "no_patch_notes": "패치 노트가 없습니다.",
        "btn_pause_repo": "⏸ 저장소 일시 중지",
        "btn_resume_repo": "▶️ 동기화 재개",
        "btn_purge_data": "🧹 데이터 삭제 및 재다운로드",
        "purge_confirm": "🧹 <b>이 저장소의 다운로드된 파일을 삭제하시겠습니까?</b>\n\n기존 파일이 삭제되고 선택된 모드에 따라 다시 다운로드됩니다.",
        "btn_purge_confirm": "✅ 네, 삭제 후 재다운로드",
        "purge_done": "✅ <b>삭제 완료!</b> 새 설정으로 다운로드를 재개했습니다.",
        "btn_back_repo": "⬅️ 저장소로 돌아가기",
        "btn_back_cat": "⬅️ 돌아가기: ",
        "check_started_repo": "🔄 <b>이 저장소의 새 릴리스 확인을 시작했습니다!</b>",
        "check_started_all": "🔄 <b>모든 저장소에 대한 전체 릴리스 확인을 시작했습니다!</b>",
        "access_denied": "⛔ <b>액세스가 거부되었습니다.</b>\n이 봇은 비공개이며 소유자 전용입니다.",
        "unauthorized_cb": "⛔ 승인되지 않음",
        "expired_req": "⚠️ 만료되었거나 이미 처리된 요청입니다.",
        "inspect_error": "❌ 분석할 수 없습니다",
        "btn_patch_notes": "📝 패치 노트",
        "btn_releases_history": "📚 릴리즈 기록",
        "view_patch_notes_hint": "전체 패치 노트를 보려면 릴리즈를 선택하세요:",
        "patch_notes_truncated": "Telegram 길이 제한으로 인해 잘렸습니다. 전체 파일은 디스크의 PATCH_NOTES.md에 있습니다",
        "reply_btn_status": "📊 상태",
        "reply_btn_menu": "📁 카테고리",
        "reply_btn_sync": "🔄 릴리즈 확인",
        "reply_btn_lang": "🌐 언어",
    },
}


def get_bot_language() -> str:
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            row = conn.execute("SELECT value FROM settings WHERE key='telegram_language'").fetchone()
            if not row or not row[0]:
                row = conn.execute("SELECT value FROM settings WHERE key='language'").fetchone()
            conn.close()
            if row and row[0]:
                code = row[0].strip().lower()
                if code in I18N:
                    return code
        except Exception:
            pass
    return "it"


def set_bot_language(lang_code: str) -> None:
    code = lang_code.strip().lower()
    if code not in I18N:
        code = "it"
    if DB_PATH.exists():
        try:
            conn = sqlite3.connect(str(DB_PATH))
            with conn:
                conn.execute(
                    "INSERT INTO settings(key, value) VALUES('telegram_language', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (code,),
                )
                conn.execute(
                    "INSERT INTO settings(key, value) VALUES('language', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (code,),
                )
            conn.close()
        except Exception:
            pass


def tr(key: str, lang: Optional[str] = None) -> str:
    l = lang or get_bot_language()
    d = I18N.get(l, I18N["it"])
    return d.get(key, I18N["it"].get(key, key))


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


def build_main_reply_keyboard(lang: str) -> Dict[str, Any]:
    return {
        "keyboard": [
            [
                {"text": tr("reply_btn_status", lang)},
                {"text": tr("reply_btn_menu", lang)},
            ],
            [
                {"text": tr("reply_btn_sync", lang)},
                {"text": tr("reply_btn_lang", lang)},
            ],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def format_patch_notes(body: str, lang: str, max_chars: int = 3400) -> str:
    if not body or not body.strip():
        return f"<i>{tr('no_patch_notes', lang)}</i>"
    clean_body = body.strip()
    if len(clean_body) > max_chars:
        cut_point = clean_body[:max_chars].rfind("\n")
        if cut_point < max_chars // 2:
            cut_point = max_chars
        truncated = clean_body[:cut_point].strip()
        return (
            f"{html.escape(truncated)}\n\n"
            f"<i>[... {tr('patch_notes_truncated', lang)}]</i>"
        )
    return html.escape(clean_body)


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
    lang = get_bot_language()
    ov_resp = await client.get(f"{VAULT_API_BASE}/api/overview", headers=INTERNAL_HEADERS, timeout=10.0)
    ov = ov_resp.json()

    active_list = ov.get("active_downloads") or []
    queue_size = ov.get("queue_size", 0) + len(active_list)
    global_paused = bool(ov.get("global_paused"))

    dl_line = tr("queue_empty", lang)
    if global_paused:
        dl_line = f"{tr('queue_paused', lang)} ({queue_size} {tr('queue_suspended', lang)})"
    elif active_list:
        cur = active_list[0]
        dl_line = (
            f"{tr('downloading', lang)}: <code>{html.escape(cur['repo_full_name'])}</code> "
            f"[{html.escape(cur['tag_name'])}] — <code>{html.escape(cur.get('current_file') or '...')}</code> "
            f"({queue_size} {tr('in_queue', lang)})"
        )
    elif queue_size > 0:
        dl_line = f"⏳ {queue_size} {tr('releases_in_queue', lang)}"

    cats = ov.get("categories") or ["Giochi", "Emulatore", "MOD VR"]

    text = (
        f"🛡 <b>{tr('bot_title', lang)}</b>\n"
        f"👤 <i>{tr('auth_line', lang)} (ID: {AUTHORIZED_USER_ID})</i>\n\n"
        f"📦 <b>{tr('monitored_repos', lang)}:</b> {ov.get('repositories_count', 0)}\n"
        f"🏷 <b>{tr('archived_releases', lang)}:</b> {ov.get('completed_releases', 0)} / {ov.get('total_releases', 0)}\n"
        f"📁 <b>{tr('saved_files', lang)}:</b> {ov.get('completed_assets', 0)} ({format_bytes(ov.get('archive_bytes', 0))})\n"
        f"💾 <b>{tr('disk_space', lang)}:</b> {format_bytes(ov.get('disk_used', 0))} {tr('used', lang)} / "
        f"<b>{format_bytes(ov.get('disk_free', 0))} {tr('free', lang)}</b> (su {format_bytes(ov.get('disk_total', 0))})\n\n"
        f"🔄 <b>{tr('queue_status', lang)}:</b>\n{dl_line}\n\n"
        f"{tr('send_link_hint', lang)}"
    )

    cat_buttons = [
        {"text": f"📁 {c}", "callback_data": f"cat:{c[:24]}"}
        for c in cats[:10]
    ]
    rows: List[List[Dict[str, str]]] = []
    for i in range(0, len(cat_buttons), 2):
        rows.append(cat_buttons[i : i + 2])

    pause_btn_label = tr("btn_resume_all", lang) if global_paused else tr("btn_pause_all", lang)
    rows.append(
        [
            {"text": pause_btn_label, "callback_data": "action:pause_global"},
            {"text": tr("btn_check_now", lang), "callback_data": "action:sync_all"},
        ]
    )
    rows.append(
        [
            {"text": tr("btn_refresh", lang), "callback_data": "action:dashboard"},
            {"text": tr("btn_language", lang), "callback_data": "action:language"},
        ]
    )

    return text, {"inline_keyboard": rows}


def build_language_picker_view() -> tuple[str, Dict[str, Any]]:
    cur_lang = get_bot_language()
    text = tr("select_lang_title", cur_lang)
    rows: List[List[Dict[str, str]]] = []
    btn_list = []
    for code, label in BOT_LANGS:
        check = "✅ " if code == cur_lang else ""
        btn_list.append({"text": f"{check}{label}", "callback_data": f"setlang:{code}"})
    for i in range(0, len(btn_list), 2):
        rows.append(btn_list[i : i + 2])
    rows.append([{"text": tr("btn_back_menu", cur_lang), "callback_data": "action:dashboard"}])
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
    lang = get_bot_language()
    provider_label = item.get("provider_label", "GITHUB")
    full_name = item["full_name"]
    desc = html.escape(item.get("description") or tr("no_desc", lang))
    sug_cat = item["suggested_category"]
    sug_tags = item["suggested_tags"]
    existing_cats = item.get("existing_categories") or ["Giochi", "Emulatore", "MOD VR"]
    only_latest = bool(item.get("only_latest", False))

    mode_text = tr("mode_latest", lang) if only_latest else tr("mode_all", lang)
    btn_all_label = ("⬜ 📚 " + tr("btn_mode_all", lang)) if only_latest else ("✅ 📚 " + tr("btn_mode_all", lang))
    btn_lat_label = ("✅ ⚡ " + tr("btn_mode_latest", lang)) if only_latest else ("⬜ ⚡ " + tr("btn_mode_latest", lang))

    text = (
        f"🔍 <b>[{provider_label}] {tr('detected', lang)}:</b> <code>{html.escape(full_name)}</code>\n"
        f"📝 <i>{desc}</i>\n\n"
        f"✨ <b>{tr('sug_cat', lang)}:</b> <code>{html.escape(sug_cat)}</code>\n"
        f"🏷 <b>{tr('gen_tags', lang)}:</b> <code>{html.escape(sug_tags)}</code>\n"
        f"📦 <b>{tr('selected_mode', lang)}:</b> <b>{mode_text}</b>\n\n"
        f"{tr('add_prompt', lang)}"
    )

    keyboard: List[List[Dict[str, str]]] = [
        [
            {"text": btn_all_label, "callback_data": f"setmode:{key}:0"},
            {"text": btn_lat_label, "callback_data": f"setmode:{key}:1"},
        ],
        [{"text": f"{tr('confirm_in', lang)}: {sug_cat} ({tr('recommended', lang)})", "callback_data": f"add:{key}:{sug_cat[:20]}"}],
    ]
    other_Btns = []
    for c in existing_cats:
        if c.lower() != sug_cat.lower():
            other_Btns.append({"text": f"📁 {c}", "callback_data": f"add:{key}:{c[:20]}"})
    for i in range(0, len(other_Btns), 2):
        keyboard.append(other_Btns[i : i + 2])

    keyboard.append([{"text": tr("btn_cancel", lang), "callback_data": f"cancel:{key}"}])
    return text, {"inline_keyboard": keyboard}


async def handle_github_link_submission(client: httpx.AsyncClient, chat_id: int, repo_slug: str) -> None:
    global PENDING_COUNTER
    lang = get_bot_language()
    try:
        resp = await client.get(
            f"{VAULT_API_BASE}/api/github/inspect",
            params={"repo": repo_slug},
            headers=INTERNAL_HEADERS,
            timeout=25.0,
        )
        if resp.status_code != 200:
            await send_msg(client, chat_id, f"{tr('inspect_error', lang)} <code>{html.escape(repo_slug)}</code>.")
            return
        info = resp.json()
    except Exception as e:
        await send_msg(client, chat_id, f"{tr('inspect_error', lang)} <code>{html.escape(repo_slug)}</code>: {e}")
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
    lang = get_bot_language()

    if user_id != AUTHORIZED_USER_ID:
        await tg_call(client, "answerCallbackQuery", {"callback_query_id": cb_id, "text": tr("unauthorized_cb", lang), "show_alert": True})
        return

    await tg_call(client, "answerCallbackQuery", {"callback_query_id": cb_id})

    if data == "action:dashboard":
        text, markup = await build_dashboard_message(client)
        await edit_msg(client, chat_id, message_id, text, markup)

    elif data == "action:language":
        text, markup = build_language_picker_view()
        await edit_msg(client, chat_id, message_id, text, markup)

    elif data.startswith("setlang:"):
        new_lang = data.split(":", 1)[1]
        set_bot_language(new_lang)
        lang_name = dict(BOT_LANGS).get(new_lang, new_lang)
        await tg_call(client, "answerCallbackQuery", {"callback_query_id": cb_id, "text": f"{tr('lang_changed', new_lang)}{lang_name}"})
        if chat_id:
            await send_msg(
                client,
                chat_id,
                f"🌐 {tr('lang_changed', new_lang)}<b>{lang_name}</b>",
                reply_markup=build_main_reply_keyboard(new_lang),
            )
        text, markup = await build_dashboard_message(client)
        await edit_msg(client, chat_id, message_id, text, markup)

    elif data == "action:pause_global":
        p_resp = await client.post(f"{VAULT_API_BASE}/api/pause-global", json={}, headers=INTERNAL_HEADERS, timeout=10.0)
        p_data = p_resp.json()
        text, markup = await build_dashboard_message(client)
        prefix = f"⏸ <b>{tr('queue_paused', lang)}!</b>\n\n" if p_data.get("global_paused") else f"▶️ <b>{tr('btn_resume_all', lang)}!</b>\n\n"
        await edit_msg(client, chat_id, message_id, prefix + text, markup)

    elif data == "action:sync_all":
        await client.post(f"{VAULT_API_BASE}/api/sync-all", headers=INTERNAL_HEADERS, timeout=10.0)
        text, markup = await build_dashboard_message(client)
        text = f"{tr('check_started_all', lang)}\n\n" + text
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
                f"📁 {tr('no_repos_cat', lang)} <b>{html.escape(cat_name)}</b>.",
                {"inline_keyboard": [[{"text": tr("btn_back_menu", lang), "callback_data": "action:dashboard"}]]},
            )
            return

        lines = [f"📁 <b>{tr('cat_title', lang)}: {html.escape(cat_name)}</b> ({len(repos)} repository)\n"]
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

        kb.append([{"text": tr("btn_back_menu", lang), "callback_data": "action:dashboard"}])
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

        status_str = tr("status_paused", lang) if is_paused else tr("status_active", lang)
        mode_str = tr("mode_latest", lang) if only_latest else tr("mode_all", lang)
        text = (
            f"📦 <b>{html.escape(repo['full_name'])}</b> [{status_str}]\n"
            f"📁 {tr('cat_title', lang)}: <code>{html.escape(repo.get('category') or 'Generale')}</code>\n"
            f"🏷 Tag: <code>{html.escape(repo.get('tags') or 'N/A')}</code>\n"
            f"⚙️ {tr('mode_label', lang)}: <b>{mode_str}</b>\n"
            f"📚 {tr('releases_in_archive', lang)}: <b>{len(releases)}</b>\n\n"
        )
        if latest:
            tag_name = html.escape(latest.get("tag_name") or "v?")
            rel_name = html.escape(latest.get("name") or "")
            name_info = f" (<i>{rel_name}</i>)" if rel_name and rel_name != tag_name else ""
            text += (
                f"🆕 <b>{tr('latest_version', lang)}:</b> <code>{tag_name}</code>{name_info}\n"
                f"📅 <b>{tr('date', lang)}:</b> {html.escape(latest.get('published_at', '')[:10])}\n"
                f"💾 <b>{tr('size', lang)}:</b> {format_bytes(latest.get('total_size') or 0)}\n\n"
                f"👉 <i>Tocca <b>{tr('btn_patch_notes', lang)}</b> qui sotto per leggere le note di rilascio complete!</i>\n"
            )

        pause_label = tr("btn_resume_repo", lang) if is_paused else tr("btn_pause_repo", lang)
        btn_all_repo = ("⬜ 📚 " + tr("btn_mode_all", lang)) if only_latest else ("✅ 📚 " + tr("btn_mode_all", lang))
        btn_lat_repo = ("✅ ⚡ " + tr("btn_mode_latest", lang)) if only_latest else ("⬜ ⚡ " + tr("btn_mode_latest", lang))
        
        kb = []
        if latest:
            top_row = [
                {
                    "text": f"📝 {tr('btn_patch_notes', lang)} ({latest.get('tag_name') or 'Ultima'})",
                    "callback_data": f"patchnote:{repo_id}:{latest['id']}",
                }
            ]
            if len(releases) > 1:
                top_row.append({
                    "text": f"📚 {tr('btn_releases_history', lang)} ({len(releases)})",
                    "callback_data": f"repolist:{repo_id}",
                })
            kb.append(top_row)

        kb.extend([
            [
                {"text": btn_all_repo, "callback_data": f"repomode:{repo_id}:0"},
                {"text": btn_lat_repo, "callback_data": f"repomode:{repo_id}:1"},
            ],
            [
                {"text": pause_label, "callback_data": f"pauserepo:{repo_id}"},
                {"text": tr("btn_check_now", lang), "callback_data": f"syncrepo:{repo_id}"},
            ],
            [
                {"text": tr("btn_purge_data", lang), "callback_data": f"repopurge:{repo_id}"},
            ],
            [{"text": f"{tr('btn_back_cat', lang)} {repo.get('category') or 'Generale'}", "callback_data": f"cat:{(repo.get('category') or 'Generale')[:24]}"}],
        ])
        await edit_msg(client, chat_id, message_id, text, {"inline_keyboard": kb})

    elif data.startswith("patchnote:"):
        parts = data.split(":")
        repo_id = int(parts[1])
        rel_id = int(parts[2]) if len(parts) > 2 else 0

        rel_resp = await client.get(f"{VAULT_API_BASE}/api/repos/{repo_id}/releases", headers=INTERNAL_HEADERS, timeout=10.0)
        if rel_resp.status_code != 200:
            return
        rdata = rel_resp.json()
        repo = rdata["repository"]
        releases = rdata["releases"]

        target_release = None
        if rel_id:
            for r in releases:
                if r["id"] == rel_id:
                    target_release = r
                    break
        if not target_release and releases:
            target_release = releases[0]

        if not target_release:
            await edit_msg(
                client,
                chat_id,
                message_id,
                f"❌ <i>{tr('no_patch_notes', lang)}</i>",
                {"inline_keyboard": [[{"text": tr("btn_back_repo", lang), "callback_data": f"repo:{repo_id}"}]]},
            )
            return

        body = (target_release.get("body") or "").strip()
        formatted_notes = format_patch_notes(body, lang)

        tag = target_release.get("tag_name") or "v?"
        name = target_release.get("name") or ""
        name_extra = f" (<i>{html.escape(name)}</i>)" if name and name != tag else ""

        text = (
            f"📝 <b>Patch Notes — {html.escape(repo['full_name'])}</b>\n"
            f"🏷 <b>{tr('latest_version', lang)}:</b> <code>{html.escape(tag)}</code>{name_extra}\n"
            f"📅 <b>{tr('date', lang)}:</b> {html.escape(target_release.get('published_at', '')[:10])}\n"
            f"💾 <b>{tr('size', lang)}:</b> {format_bytes(target_release.get('total_size') or 0)}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{formatted_notes}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        nav_row = [{"text": tr("btn_back_repo", lang), "callback_data": f"repo:{repo_id}"}]
        if len(releases) > 1:
            nav_row.append({"text": f"📚 {tr('btn_releases_history', lang)} ({len(releases)})", "callback_data": f"repolist:{repo_id}"})

        kb = [
            nav_row,
            [{"text": f"{tr('btn_back_cat', lang)} {repo.get('category') or 'Generale'}", "callback_data": f"cat:{(repo.get('category') or 'Generale')[:24]}"}],
        ]
        await edit_msg(client, chat_id, message_id, text, {"inline_keyboard": kb})

    elif data.startswith("repolist:"):
        repo_id = int(data.split(":", 1)[1])
        rel_resp = await client.get(f"{VAULT_API_BASE}/api/repos/{repo_id}/releases", headers=INTERNAL_HEADERS, timeout=10.0)
        if rel_resp.status_code != 200:
            return
        rdata = rel_resp.json()
        repo = rdata["repository"]
        releases = rdata["releases"]

        text = (
            f"📚 <b>{html.escape(repo['full_name'])}</b> — {tr('releases_in_archive', lang)} ({len(releases)})\n\n"
            f"<i>{tr('view_patch_notes_hint', lang)}</i>"
        )
        kb = []
        for r in releases[:12]:
            pub_date = (r.get("published_at") or "")[:10]
            date_str = f" • {pub_date}" if pub_date else ""
            tag = r.get("tag_name") or "v?"
            kb.append([{"text": f"📝 {tag}{date_str}", "callback_data": f"patchnote:{repo_id}:{r['id']}"}])

        kb.append([{"text": tr("btn_back_repo", lang), "callback_data": f"repo:{repo_id}"}])
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
            tr("purge_confirm", lang),
            {
                "inline_keyboard": [
                    [{"text": tr("btn_purge_confirm", lang), "callback_data": f"repopurge_ok:{repo_id}"}],
                    [{"text": tr("btn_cancel", lang), "callback_data": f"repo:{repo_id}"}],
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
            tr("purge_done", lang),
            {"inline_keyboard": [[{"text": tr("btn_back_repo", lang), "callback_data": f"repo:{repo_id}"}]]},
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
            tr("check_started_repo", lang),
            {"inline_keyboard": [[{"text": tr("btn_back_repo", lang), "callback_data": f"repo:{repo_id}"}]]},
        )

    elif data.startswith("setmode:"):
        parts = data.split(":")
        key = parts[1]
        val = parts[2] == "1" if len(parts) > 2 else False
        item = PENDING_ADDS.get(key)
        if not item:
            await edit_msg(client, chat_id, message_id, tr("expired_req", lang))
            return
        item["only_latest"] = val
        text, markup = build_pending_add_view(key, item)
        await edit_msg(client, chat_id, message_id, text, markup)

    elif data.startswith("togmode:"):
        key = data.split(":", 1)[1]
        item = PENDING_ADDS.get(key)
        if not item:
            await edit_msg(client, chat_id, message_id, tr("expired_req", lang))
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
            await edit_msg(client, chat_id, message_id, tr("expired_req", lang))
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
            mode_desc = tr("desc_latest_only", lang) if only_latest else tr("desc_all_history", lang)
            await edit_msg(
                client,
                chat_id,
                message_id,
                f"{tr('added_success', lang)}\n\n"
                f"🔹 <b>Repo:</b> <code>{html.escape(res['full_name'])}</code>\n"
                f"📁 <b>{tr('cat_title', lang)}:</b> <code>{html.escape(res['category'])}</code>\n"
                f"🏷 <b>Tag:</b> <code>{html.escape(res['tags'])}</code>\n\n"
                f"{mode_desc}",
                {"inline_keyboard": [[{"text": tr("btn_go_dashboard", lang), "callback_data": "action:dashboard"}]]},
            )
        else:
            err_detail = resp.json().get("detail", "Error")
            await edit_msg(client, chat_id, message_id, f"⚠️ Error: <b>{html.escape(str(err_detail))}</b>")

    elif data.startswith("cancel:"):
        key = data.split(":", 1)[1]
        PENDING_ADDS.pop(key, None)
        await edit_msg(client, chat_id, message_id, tr("cancelled", lang))


async def handle_message(client: httpx.AsyncClient, msg: Dict[str, Any]) -> None:
    from_user = msg.get("from") or {}
    user_id = from_user.get("id")
    chat_id = (msg.get("chat") or {}).get("id")
    text = (msg.get("text") or "").strip()
    lang = get_bot_language()

    # STRICT SECURITY GATE: Only the configured AUTHORIZED_USER_ID is allowed
    if not AUTHORIZED_USER_ID or user_id != AUTHORIZED_USER_ID or chat_id != AUTHORIZED_USER_ID:
        logger.warning(f"Unauthorized access attempt blocked from user_id={user_id}, username={from_user.get('username')}")
        if chat_id:
            await send_msg(client, chat_id, tr("access_denied", lang))
        return

    if not text:
        return

    t_lower = text.lower()

    if text.startswith("/start"):
        # Anchor the permanent Reply Keyboard at the bottom of the chat
        await send_msg(
            client,
            chat_id,
            f"🛡 <b>{tr('bot_title', lang)}</b>\n<i>{tr('auth_line', lang)}</i>",
            reply_markup=build_main_reply_keyboard(lang),
        )
        dash_text, markup = await build_dashboard_message(client)
        await send_msg(client, chat_id, dash_text, markup)
        return

    # Language selection
    if (
        text.startswith("/lang")
        or text.startswith("🌐")
        or "lingua" in t_lower
        or "language" in t_lower
        or "idioma" in t_lower
        or "sprache" in t_lower
        or "langue" in t_lower
        or "язык" in t_lower
        or "语言" in t_lower
        or "言語" in t_lower
        or "언어" in t_lower
    ):
        picker_text, markup = build_language_picker_view()
        await send_msg(client, chat_id, picker_text, markup)
        return

    # Sync / Check releases
    if (
        text.startswith("/sync")
        or text.startswith("🔄")
        or "check" in t_lower
        or "sincronizz" in t_lower
        or "vérifier" in t_lower
        or "verificar" in t_lower
        or "prüfen" in t_lower
        or "проверить" in t_lower
        or "更新" in t_lower
        or "確認" in t_lower
        or "확인" in t_lower
    ):
        await client.post(f"{VAULT_API_BASE}/api/sync-all", headers=INTERNAL_HEADERS, timeout=10.0)
        await send_msg(
            client,
            chat_id,
            f"{tr('check_started_all', lang)}\n\n💡 <i>Tocca <b>{tr('reply_btn_status', lang)}</b> per seguire lo stato in tempo reale.</i>",
            reply_markup=build_main_reply_keyboard(lang),
        )
        return

    # Status / Dashboard / Menu / Categories
    if (
        text.startswith("/status")
        or text.startswith("/menu")
        or text.startswith("/repos")
        or text.startswith("📊")
        or text.startswith("📁")
        or "status" in t_lower
        or "stato" in t_lower
        or "statut" in t_lower
        or "estado" in t_lower
        or "статус" in t_lower
        or "状态" in t_lower
        or "ステータス" in t_lower
        or "상태" in t_lower
        or "categor" in t_lower
        or "menu" in t_lower
        or "menü" in t_lower
        or "menú" in t_lower
        or "категор" in t_lower
        or "分类" in t_lower
        or "カテゴリ" in t_lower
        or "카테고리" in t_lower
    ):
        dash_text, markup = await build_dashboard_message(client)
        await send_msg(client, chat_id, dash_text, markup)
        return

    # Check if the message contains one or more GitHub / Nexus links or owner/repo
    repos = extract_github_repos_from_text(text)
    if repos:
        for r_slug in repos:
            await handle_github_link_submission(client, chat_id, r_slug)
        return

    # Default fallback: show dashboard and keep reply keyboard active
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
                                    {"command": "menu", "description": "Release Vault Dashboard"},
                                    {"command": "status", "description": "Check queue and server disk status"},
                                    {"command": "sync", "description": "Check for new releases now"},
                                    {"command": "lang", "description": "Change language / Cambia lingua"},
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
