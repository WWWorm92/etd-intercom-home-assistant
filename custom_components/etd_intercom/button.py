"""Button entities for ETD Intercom."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EtdApiError, EtdIntercomApiClient
from .const import CONF_TOKEN, DOMAIN, FALLBACK_DEVICES

_LOGGER = logging.getLogger(__name__)


def merge_devices(auto_devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge auto devices from ETD with manual fallback devices."""
    by_id: dict[str, dict[str, Any]] = {}

    for device in FALLBACK_DEVICES:
        item = dict(device)
        item.setdefault("source", "fallback")
        by_id[item["id"]] = item

    for device in auto_devices:
        intercom_id = device["id"]
        current = by_id.get(intercom_id, {})
        # Keep known fallback slug where available, but use ETD name/metadata.
        merged = {**current, **device}
        if current.get("slug"):
            merged["slug"] = current["slug"]
        if current.get("icon"):
            merged["icon"] = current["icon"]
        by_id[intercom_id] = merged

    def sort_key(device: dict[str, Any]) -> tuple[int, int, str]:
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

    return sorted(by_id.values(), key=sort_key)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ETD Intercom button entities."""
    session = async_get_clientsession(hass)
    api = EtdIntercomApiClient(session, entry.data[CONF_TOKEN])

    auto_devices: list[dict[str, Any]] = []
    try:
        auto_devices = await api.get_intercoms()
        _LOGGER.info("Loaded %s ETD intercoms from API", len(auto_devices))
    except EtdApiError as err:
        _LOGGER.warning("Could not load ETD intercom list, using fallback list: %s", err)

    devices = merge_devices(auto_devices)
    async_add_entities(EtdIntercomOpenButton(api, device) for device in devices)


class EtdIntercomOpenButton(ButtonEntity):
    """Button that sends an ETD open command."""

    _attr_has_entity_name = True

    def __init__(self, api: EtdIntercomApiClient, device: dict[str, Any]) -> None:
        self._api = api
        self._device = device
        self._last_response: dict[str, Any] | None = None

        self._attr_name = "Открыть"
        self._attr_unique_id = f"etd_intercom_{device['slug']}_open"
        self._attr_suggested_object_id = f"etd_{device['slug']}_open"
        self._attr_icon = device.get("icon", "mdi:door-open")

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device["id"])},
            name=self._device["name"],
            manufacturer="ETD",
            model="Intercom",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic attributes."""
        attrs: dict[str, Any] = {
            "intercom_id": self._device["id"],
            "intercom_name": self._device["name"],
            "source": self._device.get("source"),
            "open_message_code": self._device.get("open_message_code"),
            "open_dtfm_codes": self._device.get("open_dtfm_codes"),
        }

        if self._device.get("camera_preview_jpeg"):
            attrs["camera_preview_jpeg"] = self._device["camera_preview_jpeg"]

        if self._last_response:
            attrs.update(
                {
                    "last_status_code": self._last_response.get("status_code"),
                    "last_ok": self._last_response.get("ok"),
                    "last_content_type": self._last_response.get("content_type"),
                    "last_body_raw": self._last_response.get("body_raw"),
                    "last_body_json": self._last_response.get("body_json"),
                    "last_error": self._last_response.get("error"),
                }
            )

        return attrs

    async def async_press(self) -> None:
        """Open intercom."""
        response = await self._api.open_intercom(self._device["id"])
        self._last_response = response
        self.async_write_ha_state()

        if not response.get("ok"):
            _LOGGER.warning(
                "ETD open failed for %s (%s): %s",
                self._device["name"],
                self._device["id"],
                response,
            )
            raise HomeAssistantError(
                f"ETD не принял команду открытия: "
                f"status={response.get('status_code')}, error={response.get('error')}, "
                f"body={response.get('body_raw')}"
            )

        _LOGGER.info(
            "ETD open command accepted for %s (%s): %s",
            self._device["name"],
            self._device["id"],
            response,
        )
