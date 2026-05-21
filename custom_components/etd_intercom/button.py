"""Button entities for ETD Intercom."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EtdIntercomApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ETD Intercom button entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    api: EtdIntercomApiClient = data["api"]
    devices: list[dict[str, Any]] = data["devices"]

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
            "address": self._device.get("address"),
            "open_message_code": self._device.get("open_message_code"),
            "open_dtfm_codes": self._device.get("open_dtfm_codes"),
        }

        if self._device.get("camera_preview_jpeg"):
            attrs["camera_preview_jpeg"] = self._device["camera_preview_jpeg"]
        if self._device.get("camera_embed_link"):
            attrs["camera_embed_link"] = self._device["camera_embed_link"]

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
