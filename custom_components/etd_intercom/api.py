"""ETD Intercom API client."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from aiohttp import ClientError, ClientResponse, ClientSession

from .const import (
    API_INTERCOM_LIST_URL,
    API_LOGIN_URL,
    API_OPEN_URL,
    API_PROFILE_ME_URL,
    API_RESEND_SMS_URL,
    API_SUBMIT_SMS_URL,
)


class EtdApiError(Exception):
    """ETD API error."""


def slugify(value: str) -> str:
    """Create a stable ASCII-ish slug for common Russian ETD names."""
    value = value.lower().strip()
    replacements = {
        "калитка": "kalitka",
        "ворота": "vorota",
        "подъезд": "podiezd",
        "парадная": "podiezd",
        "улица": "ulitsa",
        "двор": "dvor",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "intercom"


class EtdIntercomApiClient:
    """Small async client for ETD Intercom API."""

    def __init__(self, session: ClientSession, token: str | None = None) -> None:
        self._session = session
        self._token = token.strip() if token else ""

    @staticmethod
    def normalize_token(token: str) -> str:
        """Return normalized Authorization header value."""
        token = token.strip()
        if token.lower().startswith("bearer "):
            return token
        return f"Bearer {token}"

    @property
    def authorization_header(self) -> str:
        """Return Authorization header value."""
        return self.normalize_token(self._token)

    def public_headers(self) -> dict[str, str]:
        """Headers for unauthenticated ETD calls."""
        return {
            "User-Agent": "okhttp/4.12.0",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def auth_headers(self) -> dict[str, str]:
        """Headers for authenticated ETD calls."""
        return {
            "Authorization": self.authorization_header,
            "User-Agent": "okhttp/4.12.0",
            "Accept": "application/json",
        }

    async def _read_json_or_text(self, response: ClientResponse) -> tuple[Any, str]:
        text = await response.text()
        if not text:
            return None, text
        try:
            return json.loads(text), text
        except ValueError:
            return None, text

    async def login_by_phone(self, phone: str) -> str:
        """Start phone login and return call_id."""
        payload = {"phone": phone.strip()}

        try:
            async with asyncio.timeout(20):
                response = await self._session.post(
                    API_LOGIN_URL,
                    headers=self.public_headers(),
                    json=payload,
                )
                data, text = await self._read_json_or_text(response)
        except (TimeoutError, ClientError) as err:
            raise EtdApiError(f"ETD login request failed: {err}") from err

        if response.status != 200:
            raise EtdApiError(f"ETD login failed: status={response.status}, body={text}")

        call_id = data.get("call_id") if isinstance(data, dict) else None
        if not call_id:
            raise EtdApiError(f"ETD login response has no call_id: {text}")

        return str(call_id)

    async def resend_sms(self, call_id: str) -> dict[str, Any]:
        """Ask ETD to send or resend SMS by call_id."""
        params = {"id_call": str(call_id)}

        try:
            async with asyncio.timeout(20):
                response = await self._session.post(
                    API_RESEND_SMS_URL,
                    headers=self.public_headers(),
                    params=params,
                )
                data, text = await self._read_json_or_text(response)
        except (TimeoutError, ClientError) as err:
            raise EtdApiError(f"ETD resend SMS request failed: {err}") from err

        if response.status != 200:
            raise EtdApiError(f"ETD resend SMS failed: status={response.status}, body={text}")

        return data if isinstance(data, dict) else {"raw": text}

    async def submit_sms_code(self, call_id: str, code: str) -> str:
        """Submit SMS code and return normalized token."""
        payload = {"call_id": str(call_id), "code": str(code).strip()}

        try:
            async with asyncio.timeout(20):
                response = await self._session.post(
                    API_SUBMIT_SMS_URL,
                    headers=self.public_headers(),
                    json=payload,
                )
                data, text = await self._read_json_or_text(response)
        except (TimeoutError, ClientError) as err:
            raise EtdApiError(f"ETD submit SMS request failed: {err}") from err

        if response.status != 200:
            raise EtdApiError(f"ETD submit SMS failed: status={response.status}, body={text}")

        token = None
        if isinstance(data, dict):
            access_token = data.get("access_token")
            if isinstance(access_token, dict):
                token = access_token.get("access_token")
            elif isinstance(access_token, str):
                token = access_token
            token = token or data.get("token")

        if not token:
            raise EtdApiError(f"ETD submit response has no access token: {text}")

        return self.normalize_token(str(token))

    async def validate_token(self) -> bool:
        """Check that token is accepted by ETD."""
        try:
            async with asyncio.timeout(20):
                response = await self._session.get(
                    API_PROFILE_ME_URL,
                    headers=self.auth_headers(),
                )
                await response.text()
        except (TimeoutError, ClientError) as err:
            raise EtdApiError(f"ETD profile check failed: {err}") from err

        if response.status == 401:
            raise EtdApiError("ETD token is unauthorized")

        return 200 <= response.status < 300

    async def get_intercoms(self) -> list[dict[str, Any]]:
        """Fetch intercoms available to the account."""
        try:
            async with asyncio.timeout(20):
                response = await self._session.get(
                    API_INTERCOM_LIST_URL,
                    headers=self.auth_headers(),
                )
                data, text = await self._read_json_or_text(response)
        except (TimeoutError, ClientError) as err:
            raise EtdApiError(f"ETD intercom list request failed: {err}") from err

        if response.status != 200:
            raise EtdApiError(f"ETD intercom list failed: status={response.status}, body={text}")

        if not isinstance(data, dict):
            raise EtdApiError(f"ETD intercom list is not JSON object: {text}")

        devices: list[dict[str, Any]] = []
        for flat in data.get("flats", []):
            for intercom in flat.get("intercoms", []):
                intercom_id = str(intercom.get("sip_username") or "").strip()
                if not intercom_id:
                    continue

                name = str(intercom.get("default_name") or intercom_id).strip()
                camera = intercom.get("camera") or {}
                icon = "mdi:gate-open" if "калитка" in name.lower() or "ворота" in name.lower() else "mdi:door-open"

                devices.append(
                    {
                        "slug": slugify(name),
                        "name": name,
                        "id": intercom_id,
                        "icon": icon,
                        "source": "intercom_list",
                        "device_id": intercom.get("device_id"),
                        "open_message_code": intercom.get("open_message_code"),
                        "open_dtfm_codes": intercom.get("open_dtfm_codes"),
                        "camera_preview_jpeg": camera.get("preview_jpeg"),
                        # Do not expose camera.embed_link as an entity attribute: it contains a video token.
                    }
                )

        return devices

    async def open_intercom(self, intercom_id: str) -> dict[str, Any]:
        """Send open command to ETD intercom."""
        url = API_OPEN_URL.format(intercom_id=intercom_id)
        result: dict[str, Any] = {
            "url": url,
            "status_code": None,
            "ok": False,
            "content_type": None,
            "body_raw": None,
            "body_json": None,
            "error": None,
        }

        try:
            async with asyncio.timeout(20):
                response = await self._session.post(url, headers=self.auth_headers())
                data, text = await self._read_json_or_text(response)

            result["status_code"] = response.status
            result["ok"] = 200 <= response.status < 300
            result["content_type"] = response.headers.get("Content-Type")
            result["body_raw"] = text
            result["body_json"] = data

        except TimeoutError:
            result["error"] = "timeout"

        except ClientError as err:
            result["error"] = str(err)

        return result
