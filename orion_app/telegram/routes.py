"""FastAPI routes for the Orion Telegram module (Social Hub).

Every Telegram HTTP endpoint lives here so that no Telegram logic sits in
``orion_app/main.py``. ``main.py`` merely includes :data:`router` under the
``/api/telegram`` prefix::

    from .telegram.routes import router as telegram_router
    app.include_router(telegram_router)
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .client import telegram_client
from .integration import telegram_integration
from .proxy_manager import telegram_proxy_manager

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


# ---------------------------------------------------------------------------
# Connection / status
# ---------------------------------------------------------------------------
@router.get("/status")
def telegram_status() -> Dict[str, Any]:
    """Return Telegram connection, account, and proxy status."""
    return telegram_client.get_status()


@router.post("/login")
def telegram_login(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Request a Telegram login code for a phone number."""
    phone = str(payload.get("phone", "")).strip()
    if not phone:
        raise HTTPException(status_code=400, detail="phone is required")
    return telegram_client.login(phone)


@router.post("/verify")
def telegram_verify(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Verify the Telegram login code and complete sign-in."""
    code = str(payload.get("code", "")).strip()
    phone_code_hash = str(payload.get("phone_code_hash", "")).strip()
    if not code:
        raise HTTPException(status_code=400, detail="code is required")
    return telegram_client.verify_code(phone_code_hash, code)


@router.post("/logout")
def telegram_logout() -> Dict[str, Any]:
    """Clear the current Telegram session."""
    return telegram_client.logout()


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------
@router.get("/me")
def telegram_me() -> Dict[str, Any]:
    """Return the signed-in Telegram profile."""
    return telegram_client.get_me()


@router.post("/profile/edit")
def telegram_edit_profile(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update the signed-in profile's name and bio."""
    first_name = str(payload.get("first_name", "")).strip()
    last_name = str(payload.get("last_name", "")).strip()
    bio = str(payload.get("bio", "")).strip()
    if not first_name:
        raise HTTPException(status_code=400, detail="first_name is required")
    return telegram_client.edit_profile(first_name, last_name, bio)


@router.get("/profile/{user_id}")
def telegram_profile(user_id: str) -> Dict[str, Any]:
    """Return profile details for a user or chat."""
    return telegram_client.get_profile(user_id)


# ---------------------------------------------------------------------------
# Chats, messages, contacts
# ---------------------------------------------------------------------------
@router.get("/chats")
def telegram_chats(limit: int = 100) -> List[Dict[str, Any]]:
    """List dialogs (chats, groups, channels)."""
    return telegram_client.get_chats(limit=limit)


@router.get("/messages/{chat_id}")
def telegram_messages(chat_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Return message history for a chat."""
    return telegram_client.get_messages(chat_id, limit=limit)


@router.post("/send")
def telegram_send(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send a text message to a chat."""
    chat_id = payload.get("chat_id")
    text = str(payload.get("text", "")).strip()
    if not chat_id or not text:
        raise HTTPException(status_code=400, detail="chat_id and text are required")
    return telegram_client.send_message(int(chat_id), text)


@router.post("/send_media")
async def telegram_send_media(
    chat_id: int = Form(...),
    file: UploadFile = File(...),
    caption: str = Form(default=""),
) -> Dict[str, Any]:
    """Send a document or image to a chat."""
    suffix = Path(file.filename).suffix if file.filename else ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        return telegram_client.send_media(chat_id, tmp_path, caption)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.post("/delete/{chat_id}/{message_id}")
def telegram_delete_message(chat_id: int, message_id: int) -> Dict[str, Any]:
    """Delete a message from a chat."""
    telegram_client.delete_message(chat_id, message_id)
    return {"deleted": True}


@router.post("/read/{chat_id}")
def telegram_mark_read(chat_id: int) -> Dict[str, Any]:
    """Mark a chat's messages as read."""
    telegram_client.mark_as_read(chat_id)
    return {"read": True}


@router.get("/contacts")
def telegram_contacts() -> List[Dict[str, Any]]:
    """List Telegram contacts."""
    return telegram_client.get_contacts()


@router.get("/members/{chat_id}")
def telegram_members(chat_id: int) -> List[Dict[str, Any]]:
    """List members of a group or channel."""
    return telegram_client.get_chat_members(chat_id)


@router.post("/search")
def telegram_search(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Search chats by title, username, or last message."""
    query = str(payload.get("query", "")).strip()
    return telegram_client.search_chats(query)


# ---------------------------------------------------------------------------
# Hidden proxy management
# ---------------------------------------------------------------------------
@router.get("/proxies")
def telegram_proxies_list() -> List[Dict[str, Any]]:
    """List the configured proxy pool."""
    return telegram_proxy_manager.get_proxies()


@router.post("/proxies")
def telegram_add_proxy(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Add and test a manual proxy."""
    return telegram_proxy_manager.add_proxy(payload)


@router.post("/proxies/refresh")
def telegram_refresh_proxies() -> Dict[str, Any]:
    """Re-test the whole proxy pool and pick the best node."""
    proxies = telegram_proxy_manager.test_all_proxies()
    best = telegram_proxy_manager.get_best_proxy()
    return {"refreshed": True, "proxies_count": len(proxies), "best_proxy": best}


# ---------------------------------------------------------------------------
# Telethon integration: archive, history import, MTProto proxy pool
# ---------------------------------------------------------------------------
@router.get("/integration/status")
def telegram_integration_status() -> Dict[str, Any]:
    """Return the Telethon integration status (credentials, session, import)."""
    return telegram_integration.status()


@router.get("/integration/dialogs")
def telegram_archived_dialogs() -> List[Dict[str, Any]]:
    """List dialogs stored in the local Telegram archive."""
    return telegram_integration.archived_dialogs()


@router.get("/integration/messages/{chat_id}")
def telegram_archived_messages(chat_id: str) -> List[Dict[str, Any]]:
    """Return archived messages for a chat."""
    return telegram_integration.archived_messages(chat_id)


@router.get("/media/{chat_id}/{message_id}")
def telegram_media(chat_id: str, message_id: str):
    """Serve a downloaded Telegram media file from the local archive."""
    from fastapi.responses import FileResponse

    media_path = telegram_integration.media_file(chat_id, message_id)
    if media_path is None or not media_path.is_file():
        raise HTTPException(status_code=404, detail="Telegram media not found")
    return FileResponse(media_path)


@router.post("/integration/import")
def telegram_start_import() -> Dict[str, Any]:
    """Start a full history import into the local archive."""
    return telegram_integration.start_import()


@router.get("/integration/import/status")
def telegram_import_status() -> Dict[str, Any]:
    """Report progress of the running (or last) history import."""
    return telegram_integration.import_status()


@router.get("/integration/proxies")
def telegram_saved_proxies() -> List[Dict[str, Any]]:
    """List saved MTProto proxy links (secrets redacted)."""
    return telegram_integration.saved_mtproxies()


@router.post("/integration/proxies")
def telegram_save_proxies(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and save shared MTProto proxy links."""
    links = payload.get("links") or []
    if isinstance(links, str):
        links = [links]
    if not isinstance(links, list):
        raise HTTPException(status_code=400, detail="links must be a list of strings")
    return telegram_integration.save_mtproxy_links([str(link) for link in links])


@router.post("/integration/proxies/{proxy_id}/activate")
def telegram_activate_proxy(proxy_id: int) -> Dict[str, Any]:
    """Test and activate a saved MTProto proxy."""
    return telegram_integration.activate_saved_mtproxy(proxy_id)


@router.delete("/integration/proxies")
def telegram_clear_proxies() -> Dict[str, Any]:
    """Remove all saved MTProto proxies."""
    return telegram_integration.clear_proxy()


# ---------------------------------------------------------------------------
# Extended Telegram API surface
# ---------------------------------------------------------------------------
@router.get("/me/photo")
def telegram_me_photo() -> Dict[str, Any]:
    """Return the signed-in user's avatar URL."""
    return telegram_client.get_me_photo()


@router.post("/pin/{chat_id}/{message_id}")
def telegram_pin_message(chat_id: int, message_id: int, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Pin (or unpin) a message in a chat."""
    body = payload or {}
    return telegram_client.pin_message(
        chat_id, message_id, notify=bool(body.get("notify", True))
    )


@router.post("/unpin/{chat_id}")
def telegram_unpin_messages(chat_id: int, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Unpin a single message or every pinned message in a chat."""
    body = payload or {}
    message_id = body.get("message_id")
    return telegram_client.unpin_message(chat_id, message_id=message_id)


@router.post("/forward")
def telegram_forward_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Forward one or more messages to another chat."""
    chat_id = payload.get("chat_id")
    from_chat_id = payload.get("from_chat_id")
    message_ids = payload.get("message_ids")
    if chat_id is None or from_chat_id is None or message_ids is None:
        raise HTTPException(
            status_code=400, detail="chat_id, from_chat_id and message_ids are required"
        )
    return telegram_client.forward_messages(chat_id, from_chat_id, message_ids)


@router.post("/edit/{chat_id}/{message_id}")
def telegram_edit_message(chat_id: int, message_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Edit the text of a message."""
    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    return telegram_client.edit_message(chat_id, message_id, text)


@router.post("/reply")
def telegram_reply_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Reply to a message in a chat."""
    chat_id = payload.get("chat_id")
    message_id = payload.get("message_id")
    text = str(payload.get("text", "")).strip()
    if chat_id is None or message_id is None or not text:
        raise HTTPException(status_code=400, detail="chat_id, message_id and text are required")
    return telegram_client.reply_message(chat_id, message_id, text)


@router.get("/history/{chat_id}")
def telegram_chat_history(
    chat_id: int, limit: int = 50, offset_id: int = 0
) -> List[Dict[str, Any]]:
    """Return a paged slice of a chat's message history."""
    return telegram_client.get_chat_history(chat_id, limit=limit, offset_id=offset_id)


@router.post("/search/global")
def telegram_global_search(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Search messages across all chats."""
    query = str(payload.get("query", "")).strip()
    limit = int(payload.get("limit", 20) or 20)
    if not query:
        raise HTTPException(status_code=400, detail="query is required")
    return telegram_client.search_global(query, limit=limit)


@router.get("/search/{chat_id}")
def telegram_search_messages(chat_id: int, q: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    """Search within a single chat's messages."""
    return telegram_client.search_messages(chat_id, q, limit=limit)


@router.post("/join")
def telegram_join_chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Join a public chat or accept a chat invite link."""
    link = str(payload.get("link", "") or "").strip()
    username = str(payload.get("username", "") or "").strip()
    if not link and not username:
        raise HTTPException(status_code=400, detail="link or username is required")
    return telegram_client.join_chat(link=link or None, username=username or None)


@router.post("/leave/{chat_id}")
def telegram_leave_chat(chat_id: int) -> Dict[str, Any]:
    """Leave a group or channel."""
    return telegram_client.leave_chat(chat_id)


@router.post("/archive/{chat_id}")
def telegram_archive_chat(chat_id: int, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Archive or unarchive a chat."""
    body = payload or {}
    return telegram_client.archive_chat(chat_id, archived=bool(body.get("archived", True)))


@router.post("/mute/{chat_id}")
def telegram_mute_chat(chat_id: int, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Mute or unmute notifications for a chat."""
    body = payload or {}
    return telegram_client.mute_chat(chat_id, mute=bool(body.get("mute", True)))


@router.post("/block/{user_id}")
def telegram_block_user(user_id: int, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Block or unblock a user."""
    body = payload or {}
    return telegram_client.block_user(user_id, block=bool(body.get("block", True)))


@router.get("/blocked")
def telegram_blocked_users() -> List[Dict[str, Any]]:
    """List blocked users."""
    return telegram_client.get_blocked_users()


@router.get("/bots")
def telegram_my_bots() -> List[Dict[str, Any]]:
    """List bots owned by the signed-in account."""
    return telegram_client.get_my_bots()


@router.get("/stories/{chat_id}")
def telegram_chat_stories(chat_id: int) -> List[Dict[str, Any]]:
    """Return active stories for a user or chat."""
    return telegram_client.get_stories(chat_id)


@router.post("/typing/{chat_id}")
def telegram_set_typing(chat_id: int, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Broadcast a typing/upload action in a chat."""
    body = payload or {}
    return telegram_client.set_typing(chat_id, action=str(body.get("action", "typing")))


@router.get("/download/{chat_id}/{message_id}")
def telegram_download_media(chat_id: int, message_id: int) -> Dict[str, Any]:
    """Download a message's media to the local cache."""
    return telegram_client.download_media(chat_id, message_id)


@router.post("/invite")
def telegram_invite_to_chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Invite users to a group or channel."""
    chat_id = payload.get("chat_id")
    user_ids = payload.get("user_ids")
    if chat_id is None or not user_ids:
        raise HTTPException(status_code=400, detail="chat_id and user_ids are required")
    return telegram_client.invite_to_chat(chat_id, user_ids)


@router.post("/create_group")
def telegram_create_group(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new group or channel."""
    title = str(payload.get("title", "")).strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    return telegram_client.create_group(
        title,
        user_ids=payload.get("user_ids"),
        is_channel=bool(payload.get("is_channel", False)),
    )


@router.post("/create_channel")
def telegram_create_channel(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new broadcast channel."""
    title = str(payload.get("title", "")).strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    return telegram_client.create_group(
        title, user_ids=payload.get("user_ids"), is_channel=True
    )


@router.post("/admin/promote")
def telegram_promote_admin(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Promote a member to administrator."""
    chat_id = payload.get("chat_id")
    user_id = payload.get("user_id")
    if chat_id is None or user_id is None:
        raise HTTPException(status_code=400, detail="chat_id and user_id are required")
    return telegram_client.promote_admin(chat_id, user_id)


@router.post("/admin/demote")
def telegram_demote_admin(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Demote an administrator back to a member."""
    chat_id = payload.get("chat_id")
    user_id = payload.get("user_id")
    if chat_id is None or user_id is None:
        raise HTTPException(status_code=400, detail="chat_id and user_id are required")
    return telegram_client.demote_admin(chat_id, user_id)


@router.get("/updates")
def telegram_updates(since: float = 0.0, limit: int = 50) -> List[Dict[str, Any]]:
    """Return buffered real-time updates since a timestamp."""
    return telegram_client.get_updates(since=since, limit=limit)
