"""Helpers for ETD Intercom."""

from __future__ import annotations

import json
import re
from typing import Any

from .const import MANUAL_DEVICES, PREVIEW_URL_TEMPLATE


def normalize_phone(phone: str) -> str:
    """Normalize Russian phone numbers to +7XXXXXXXXXX."""
    cleaned = phone.strip()
    cleaned = re.sub(r"[\s\-()]+", "", cleaned)

    if cleaned.startswith("+7") and len(cleaned) == 12 and cleaned[1:].isdigit():
        return cleaned

    if cleaned.startswith("8") and len(cleaned) == 11 and cleaned.isdigit():
        return "+7" + cleaned[1:]

    if cleaned.startswith("7") and len(cleaned) == 11 and cleaned.isdigit():
        return "+" + cleaned

    raise ValueError("invalid_phone")


def slugify(value: str) -> str:
    """Create a stable slug for common Russian ETD names."""
    value = value.lower().strip()
    replacements = {
        "калитка": "kalitka",
        "ворота": "vorota",
        "подъезд": "podiezd",
        "парадная": "podiezd",
        "улица": "ulitsa",
        "двор": "dvor",
        "камера": "camera",
        "открыть": "open",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "intercom"


def _looks_like_intercom_id(value: str) -> bool:
    return bool(re.fullmatch(r"\d{3,10}", value.strip()))


def _icon_for_name(name: str) -> str:
    lower = name.lower()
    if "калит" in lower or "ворот" in lower or "gate" in lower:
        return "mdi:gate-open"
    return "mdi:door-open"


def _normalize_custom_device(item: dict[str, Any], index: int = 0) -> dict[str, Any]:
    intercom_id = str(
        item.get("id")
        or item.get("sip_username")
        or item.get("intercom_id")
        or ""
    ).strip()

    if not _looks_like_intercom_id(intercom_id):
        raise ValueError(f"invalid_custom_device_id:{intercom_id or index}")

    name = str(
        item.get("name")
        or item.get("default_name")
        or item.get("title")
        or f"ETD {intercom_id}"
    ).strip()

    icon = str(item.get("icon") or _icon_for_name(name)).strip()
    slug = str(item.get("slug") or slugify(f"{name}_{intercom_id}")).strip()

    preview = str(
        item.get("camera_preview_jpeg")
        or item.get("preview_jpeg")
        or item.get("preview")
        or PREVIEW_URL_TEMPLATE.format(intercom_id=intercom_id)
    ).strip()

    embed_link = item.get("camera_embed_link") or item.get("embed_link")

    device = {
        "id": intercom_id,
        "slug": slug,
        "name": name,
        "icon": icon,
        "source": "custom",
        "camera_name": str(item.get("camera_name") or name),
        "camera_preview_jpeg": preview,
        "camera_device_id": item.get("camera_device_id"),
        "camera_embed_link": str(embed_link).strip() if embed_link else None,
    }

    for key in ("address", "flat", "flat_id", "open_dtfm_codes", "open_message_code"):
        if item.get(key) is not None:
            device[key] = item[key]

    return device


def parse_custom_devices(text: str | None) -> list[dict[str, Any]]:
    """Parse custom devices from UI text.

    Supported formats:
      000270 | Подъезд 1
      001586; Ворота 1; mdi:gate-open
      000267=Парадная 2

    JSON is also supported:
      [{"id": "000270", "name": "Подъезд 1", "icon": "mdi:door-open"}]
    """
    raw = (text or "").strip()
    if not raw:
        return []

    if raw[0] in "[{":
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as err:
            raise ValueError(f"invalid_custom_devices_json:{err}") from err

        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list):
            raise ValueError("custom_devices_json_must_be_list")
        return [_normalize_custom_device(item, index) for index, item in enumerate(parsed, start=1)]

    devices: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if "=" in line and "|" not in line and ";" not in line:
            intercom_id, name = line.split("=", 1)
            parts = [intercom_id.strip(), name.strip()]
        elif "|" in line:
            parts = [part.strip() for part in line.split("|")]
        else:
            parts = [part.strip() for part in line.split(";")]

        if not parts or not parts[0]:
            raise ValueError(f"invalid_custom_device_line:{line_number}")

        intercom_id = parts[0]
        name = parts[1] if len(parts) > 1 and parts[1] else f"ETD {intercom_id}"
        icon = parts[2] if len(parts) > 2 and parts[2] else _icon_for_name(name)
        preview = parts[3] if len(parts) > 3 and parts[3] else PREVIEW_URL_TEMPLATE.format(intercom_id=intercom_id)
        embed_link = parts[4] if len(parts) > 4 and parts[4] else None

        devices.append(
            _normalize_custom_device(
                {
                    "id": intercom_id,
                    "name": name,
                    "icon": icon,
                    "camera_preview_jpeg": preview,
                    "camera_embed_link": embed_link,
                },
                line_number,
            )
        )

    return devices


def _manual_device_with_camera(device: dict[str, Any]) -> dict[str, Any]:
    item = dict(device)
    item.setdefault("source", "manual")
    item.setdefault("camera_preview_jpeg", PREVIEW_URL_TEMPLATE.format(intercom_id=item["id"]))
    item.setdefault("camera_name", item["name"])
    item.setdefault("camera_device_id", None)
    item.setdefault("camera_embed_link", None)
    return item


def merge_devices(
    auto_devices: list[dict[str, Any]],
    include_manual_devices: bool = True,
    custom_devices: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Merge manual, API and custom devices.

    Priority: predefined manual < API < user custom.
    User custom devices can therefore add missing IDs and also rename/override an API device.
    """
    by_id: dict[str, dict[str, Any]] = {}

    if include_manual_devices:
        for device in MANUAL_DEVICES:
            item = _manual_device_with_camera(device)
            by_id[item["id"]] = item

    for device in auto_devices:
        intercom_id = device["id"]
        current = by_id.get(intercom_id, {})
        merged = {**current, **device}

        # Preserve known short slugs/icons from manual list when available.
        if current.get("slug"):
            merged["slug"] = current["slug"]
        if current.get("icon"):
            merged["icon"] = current["icon"]

        merged.setdefault("source", "api")
        merged.setdefault("camera_preview_jpeg", PREVIEW_URL_TEMPLATE.format(intercom_id=intercom_id))
        by_id[intercom_id] = merged

    for device in custom_devices or []:
        intercom_id = device["id"]
        current = by_id.get(intercom_id, {})
        merged = {**current, **device}
        merged.setdefault("camera_preview_jpeg", PREVIEW_URL_TEMPLATE.format(intercom_id=intercom_id))
        by_id[intercom_id] = merged

    return sorted(by_id.values(), key=sort_key)


def sort_key(device: dict[str, Any]) -> tuple[int, int, str]:
    """Sort: kalitki, vorota, podiezdy/other."""
    name = str(device.get("name", "")).lower()
    slug = str(device.get("slug", ""))
    number = 999

    for part in reversed(slug.split("_")):
        if part.isdigit():
            number = int(part)
            break

    if "kalitka" in slug or "калитка" in name:
        group = 1
    elif "vorota" in slug or "ворота" in name:
        group = 2
    else:
        group = 3

    return (group, number, slug)
