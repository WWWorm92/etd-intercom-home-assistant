from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import BASE_API_URL, DEFAULT_USER_AGENT

_LOGGER = logging.getLogger(__name__)


class ETDError(Exception):
    """Base ETD API error."""


class ETDAuthError(ETDError):
    """ETD authorization error."""


@dataclass(slots=True)
class ETDDevice:
    id: str
    name: str
    icon: str | None = None
    preview_jpeg: str | None = None
    embed_link: str | None = None
    whep_url: str | None = None
    address: str | None = None
    source: str = "api"


def normalize_token(token: str) -> str:
    token = (token or "").strip()
    if not token:
        raise ETDAuthError("Empty token")
    if token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"


def normalize_phone(phone: str) -> str:
    phone = (phone or "").strip()
    phone = re.sub(r"[\s\-()]+", "", phone)

    if phone.startswith("+7") and len(phone) == 12 and phone[2:].isdigit():
        return phone
    if phone.startswith("8") and len(phone) == 11 and phone.isdigit():
        return "+7" + phone[1:]
    if phone.startswith("7") and len(phone) == 11 and phone.isdigit():
        return "+" + phone

    raise ValueError("phone_format")


def make_default_preview_url(intercom_id: str) -> str:
    return f"https://cameras-preview-server.etd-online.ru/api/cameras/preview/{intercom_id}.jpg"


def make_whep_url_from_embed_link(embed_link: str | None) -> str | None:
    if not embed_link:
        return None

    try:
        parsed = urlparse(embed_link)
        query = parse_qs(parsed.query)
        token = (query.get("token") or [None])[0]
        video = (query.get("video") or [None])[0]
        if not token or not video:
            return None
        video = video.strip("/")
        return f"https://flussonic.etd-site.ru/{video}/whep?token={token}"
    except Exception:  # noqa: BLE001
        return None


def make_default_whep_url(intercom_id: str, token: str | None = None) -> str | None:
    if not token:
        return None
    return f"https://flussonic.etd-site.ru/intercoms_6/{intercom_id}/whep?token={token}"


def make_default_embed_link(intercom_id: str, token: str | None = None, sip_username: str | None = None) -> str | None:
    # A correct embed link normally comes from /intercom/list.
    # For manually added IDs, keep this empty unless the user provides a link.
    return None


def guess_icon(name: str) -> str:
    low = name.lower()
    if "ворот" in low or "калит" in low or "gate" in low:
        return "mdi:gate-open"
    return "mdi:door-open"


def slugify(value: str) -> str:
    translit = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
        "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
        "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
        "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    value = "".join(translit.get(ch.lower(), ch.lower()) for ch in value)
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "device"


def parse_custom_devices(raw: str | None) -> list[ETDDevice]:
    if not raw:
        return []

    raw = raw.strip()
    devices: list[ETDDevice] = []

    if not raw:
        return []

    # JSON format support.
    if raw.startswith("[") or raw.startswith("{"):
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    intercom_id = str(item.get("id") or item.get("sip_username") or "").strip()
                    if not intercom_id:
                        continue
                    name = str(item.get("name") or item.get("default_name") or intercom_id).strip()
                    devices.append(
                        ETDDevice(
                            id=intercom_id,
                            name=name,
                            icon=item.get("icon") or guess_icon(name),
                            preview_jpeg=item.get("preview_jpeg") or make_default_preview_url(intercom_id),
                            embed_link=item.get("embed_link"),
                            whep_url=item.get("whep_url") or make_whep_url_from_embed_link(item.get("embed_link")),
                            address=item.get("address"),
                            source="manual",
                        )
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to parse custom devices JSON: %s", err)
        return devices

    # Line format:
    # 000270 | Подъезд 1 | mdi:door-open | preview | embed | whep
    # 000267=Парадная 2
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if "|" in line:
            parts = [part.strip() for part in line.split("|")]
            intercom_id = parts[0] if len(parts) > 0 else ""
            name = parts[1] if len(parts) > 1 and parts[1] else intercom_id
            icon = parts[2] if len(parts) > 2 and parts[2] else guess_icon(name)
            preview = parts[3] if len(parts) > 3 and parts[3] else make_default_preview_url(intercom_id)
            embed = parts[4] if len(parts) > 4 and parts[4] else None
            whep = parts[5] if len(parts) > 5 and parts[5] else make_whep_url_from_embed_link(embed)
        elif "=" in line:
            intercom_id, name = [part.strip() for part in line.split("=", 1)]
            icon = guess_icon(name)
            preview = make_default_preview_url(intercom_id)
            embed = None
            whep = None
        else:
            intercom_id = line
            name = line
            icon = guess_icon(name)
            preview = make_default_preview_url(intercom_id)
            embed = None
            whep = None

        if intercom_id:
            devices.append(
                ETDDevice(
                    id=intercom_id,
                    name=name,
                    icon=icon,
                    preview_jpeg=preview,
                    embed_link=embed,
                    whep_url=whep or make_whep_url_from_embed_link(embed),
                    source="manual",
                )
            )

    return devices


def merge_devices(api_devices: list[ETDDevice], manual_devices: list[ETDDevice]) -> list[ETDDevice]:
    merged: dict[str, ETDDevice] = {}

    for device in api_devices:
        merged[device.id] = device

    for device in manual_devices:
        # Manual devices override names/icons, but preserve API camera links if manual link not provided.
        existing = merged.get(device.id)
        if existing:
            merged[device.id] = ETDDevice(
                id=device.id,
                name=device.name or existing.name,
                icon=device.icon or existing.icon,
                preview_jpeg=device.preview_jpeg or existing.preview_jpeg,
                embed_link=device.embed_link or existing.embed_link,
                whep_url=device.whep_url or existing.whep_url or make_whep_url_from_embed_link(device.embed_link or existing.embed_link),
                address=device.address or existing.address,
                source="api+manual",
            )
        else:
            merged[device.id] = device

    return list(merged.values())


class ETDApiClient:
    def __init__(self, session: ClientSession, token: str | None = None) -> None:
        self.session = session
        self.token = normalize_token(token) if token else None

    def set_token(self, token: str) -> None:
        self.token = normalize_token(token)

    def public_headers(self) -> dict[str, str]:
        return {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def auth_headers(self) -> dict[str, str]:
        if not self.token:
            raise ETDAuthError("Token is not configured")
        return {
            "Authorization": self.token,
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json",
        }

    async def _json_response(self, response) -> Any:
        text = await response.text()
        try:
            return json.loads(text) if text else {}
        except Exception:  # noqa: BLE001
            return {"raw": text}

    async def login_by_phone(self, phone: str) -> str:
        phone = normalize_phone(phone)
        url = f"{BASE_API_URL}/call/login"

        try:
            async with asyncio.timeout(20):
                response = await self.session.post(
                    url,
                    headers=self.public_headers(),
                    json={"phone": phone},
                )
                data = await self._json_response(response)
        except (TimeoutError, ClientError) as err:
            raise ETDError(f"login request failed: {err}") from err

        if response.status != 200:
            raise ETDError(f"ETD login error {response.status}: {data}")

        call_id = data.get("call_id") if isinstance(data, dict) else None
        if not call_id:
            raise ETDError(f"ETD login response without call_id: {data}")

        return str(call_id)

    async def resend_sms(self, call_id: str) -> dict[str, Any]:
        url = f"{BASE_API_URL}/call/resend-sms?id_call={call_id}"

        try:
            async with asyncio.timeout(20):
                response = await self.session.post(url, headers=self.public_headers())
                data = await self._json_response(response)
        except (TimeoutError, ClientError) as err:
            raise ETDError(f"resend sms request failed: {err}") from err

        if response.status != 200:
            raise ETDError(f"ETD resend SMS error {response.status}: {data}")

        return data if isinstance(data, dict) else {"response": data}

    async def submit_sms_code(self, call_id: str, code: str) -> str:
        url = f"{BASE_API_URL}/call/submit"

        try:
            async with asyncio.timeout(20):
                response = await self.session.post(
                    url,
                    headers=self.public_headers(),
                    json={"call_id": str(call_id), "code": str(code)},
                )
                data = await self._json_response(response)
        except (TimeoutError, ClientError) as err:
            raise ETDError(f"submit sms request failed: {err}") from err

        if response.status != 200:
            raise ETDAuthError(f"ETD submit SMS error {response.status}: {data}")

        token = None
        if isinstance(data, dict):
            access_token = data.get("access_token")
            if isinstance(access_token, dict):
                token = access_token.get("access_token")
            elif isinstance(access_token, str):
                token = access_token
            token = token or data.get("token")

        if not token:
            raise ETDAuthError(f"ETD submit response without token: {data}")

        self.set_token(token)
        return self.token or normalize_token(token)

    async def fetch_intercoms(self) -> list[ETDDevice]:
        url = f"{BASE_API_URL}/intercom/list"

        try:
            async with asyncio.timeout(30):
                response = await self.session.get(url, headers=self.auth_headers())
                data = await self._json_response(response)
        except (TimeoutError, ClientError) as err:
            raise ETDError(f"intercom list request failed: {err}") from err

        if response.status != 200:
            raise ETDError(f"ETD intercom list error {response.status}: {data}")

        devices: list[ETDDevice] = []
        flats = data.get("flats", []) if isinstance(data, dict) else []
        for flat in flats:
            address = flat.get("address_standard") if isinstance(flat, dict) else None
            for intercom in flat.get("intercoms", []) or []:
                intercom_id = str(intercom.get("sip_username") or "").strip()
                if not intercom_id:
                    continue
                name = str(intercom.get("default_name") or intercom_id).strip()
                camera = intercom.get("camera") or {}
                embed_link = camera.get("embed_link")
                devices.append(
                    ETDDevice(
                        id=intercom_id,
                        name=name,
                        icon=guess_icon(name),
                        preview_jpeg=camera.get("preview_jpeg") or make_default_preview_url(intercom_id),
                        embed_link=embed_link,
                        whep_url=make_whep_url_from_embed_link(embed_link),
                        address=intercom.get("address") or address,
                        source="api",
                    )
                )

        return devices

    async def open_intercom(self, intercom_id: str) -> dict[str, Any]:
        url = f"{BASE_API_URL}/intercom/{intercom_id}/open"

        try:
            async with asyncio.timeout(20):
                response = await self.session.post(url, headers=self.auth_headers())
                text = await response.text()
        except (TimeoutError, ClientError) as err:
            return {
                "status": None,
                "ok": False,
                "body_raw": None,
                "body_json": None,
                "error": str(err),
            }

        try:
            body_json = json.loads(text) if text else None
        except Exception:  # noqa: BLE001
            body_json = None

        return {
            "status": response.status,
            "ok": 200 <= response.status < 300,
            "body_raw": text,
            "body_json": body_json,
            "error": None,
        }

    async def fetch_image(self, url: str) -> bytes | None:
        try:
            async with asyncio.timeout(20):
                response = await self.session.get(url, headers={"User-Agent": DEFAULT_USER_AGENT})
                if response.status != 200:
                    _LOGGER.debug("Preview image returned HTTP %s for %s", response.status, url)
                    return None
                return await response.read()
        except (TimeoutError, ClientError) as err:
            _LOGGER.debug("Failed to fetch preview image %s: %s", url, err)
            return None
