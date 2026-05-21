from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ETDData
from .api import ETDDevice, slugify
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data: ETDData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ETDOpenButton(entry.entry_id, data, device) for device in data.devices])


class ETDOpenButton(ButtonEntity):
    _attr_has_entity_name = False

    def __init__(self, entry_id: str, data: ETDData, device: ETDDevice) -> None:
        self._entry_id = entry_id
        self._data = data
        self._device = device
        self._last_result: dict[str, Any] | None = None
        self._attr_name = f"ETD {device.name} Open"
        self._attr_unique_id = f"etd_{device.id}_{slugify(device.name)}_open"
        self._attr_icon = device.icon or "mdi:door-open"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "intercom_id": self._device.id,
            "etd_name": self._device.name,
            "source": self._device.source,
        }
        if self._device.address:
            attrs["address"] = self._device.address
        if self._last_result:
            attrs.update(
                {
                    "last_status_code": self._last_result.get("status"),
                    "last_ok": self._last_result.get("ok"),
                    "last_body_raw": self._last_result.get("body_raw"),
                    "last_body_json": self._last_result.get("body_json"),
                    "last_error": self._last_result.get("error"),
                }
            )
        return attrs

    async def async_press(self) -> None:
        self._last_result = await self._data.api.open_intercom(self._device.id)
        self.async_write_ha_state()

        if not self._last_result.get("ok"):
            _LOGGER.warning(
                "ETD open failed for %s (%s): %s",
                self._device.name,
                self._device.id,
                self._last_result,
            )
