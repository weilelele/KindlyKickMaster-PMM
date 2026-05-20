from __future__ import annotations

import asyncio
import json
import time
import lark_oapi as lark
import httpx
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
)
from config import settings

_lark = (
    lark.Client.builder()
    .app_id(settings.feishu_app_id)
    .app_secret(settings.feishu_app_secret)
    .log_level(lark.LogLevel.WARNING)
    .build()
)

# ── App access token (cached) ─────────────────────────────────────

_token_cache: dict = {"token": None, "expires_at": 0.0}


async def _get_app_token() -> str:
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["token"]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
            json={"app_id": settings.feishu_app_id, "app_secret": settings.feishu_app_secret},
            timeout=10,
        )
        data = resp.json()
    token = data["app_access_token"]
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + data.get("expire", 7200)
    return token


# ── User info ─────────────────────────────────────────────────────

async def get_user_name(open_id: str) -> str | None:
    token = await _get_app_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://open.feishu.cn/open-apis/contact/v3/users/{open_id}",
            params={"user_id_type": "open_id"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
    data = resp.json()
    return data.get("data", {}).get("user", {}).get("name")


# ── Feishu Doc content ────────────────────────────────────────────

async def get_feishu_doc_content(document_id: str) -> str | None:
    """Fetch plain text content of a Feishu Docx document."""
    token = await _get_app_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/raw_content",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
    data = resp.json()
    if data.get("code") == 0:
        return data.get("data", {}).get("content", "")
    return None


# ── File download ─────────────────────────────────────────────────

async def download_file(message_id: str, file_key: str) -> bytes | None:
    """Download a file attachment from a message."""
    token = await _get_app_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{file_key}",
            params={"type": "file"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    if resp.status_code == 200:
        return resp.content
    return None


async def get_message_content(message_id: str) -> str | None:
    """Fetch the raw content string of a message by its ID."""
    token = await _get_app_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}",
            params={"user_id_type": "open_id"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
    data = resp.json()
    if data.get("code") != 0:
        return None
    items = data.get("data", {}).get("items", [])
    if not items:
        return None
    return items[0].get("body", {}).get("content", "")


async def download_image(message_id: str, image_key: str) -> bytes | None:
    """Download an image attachment from a message."""
    token = await _get_app_token()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{image_key}",
            params={"type": "image"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    if resp.status_code == 200:
        return resp.content
    return None


# ── Send messages ─────────────────────────────────────────────────

def _text_body(text: str) -> str:
    return json.dumps({"text": text})


async def send_to_chat(chat_id: str, text: str) -> None:
    req = (
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("text")
            .content(_text_body(text))
            .build()
        )
        .build()
    )
    resp = await asyncio.to_thread(_lark.im.v1.message.create, req)
    if not resp.success():
        raise RuntimeError(f"Feishu send failed [{resp.code}]: {resp.msg}")


async def send_to_group(text: str) -> None:
    await send_to_chat(settings.group_chat_id, text)


async def send_to_user(open_id: str, text: str) -> None:
    req = (
        CreateMessageRequest.builder()
        .receive_id_type("open_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(open_id)
            .msg_type("text")
            .content(_text_body(text))
            .build()
        )
        .build()
    )
    resp = await asyncio.to_thread(_lark.im.v1.message.create, req)
    if not resp.success():
        raise RuntimeError(f"Feishu send failed [{resp.code}]: {resp.msg}")
