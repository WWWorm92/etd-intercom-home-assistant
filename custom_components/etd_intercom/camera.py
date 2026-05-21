from __future__ import annotations

from typing import Any

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ETDData
from .api import ETDDevice, slugify
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data: ETDData = hass.data[DOMAIN][entry.entry_id]
    cameras = [
        ETDPreviewCamera(entry.entry_id, data, device)
        for device in data.devices
        if device.preview_jpeg or device.embed_link
    ]
    async_add_entities(cameras)


class ETDPreviewCamera(Camera):
    _attr_has_entity_name = False

    def __init__(self, entry_id: str, data: ETDData, device: ETDDevice) -> None:
        super().__init__()
        self._entry_id = entry_id
        self._data = data
        self._device = device
        self._attr_name = f"ETD {device.name} Camera"
        self._attr_unique_id = f"etd_{device.id}_{slugify(device.name)}_camera"
        self._attr_icon = "mdi:cctv"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "intercom_id": self._device.id,
            "etd_name": self._device.name,
            "source": self._device.source,
            "preview_jpeg": self._device.preview_jpeg,
            "camera_embed_link": self._device.embed_link,
            "camera_whep_url": self._device.whep_url,
            "camera_whep_proxy_path": f"/api/etd_intercom/whep/{self._entry_id}/{self._device.id}",
            "camera_whep_requires_proxy": True,
        }
        if self._device.address:
            attrs["address"] = self._device.address
        return attrs

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        if not self._device.preview_jpeg:
            return None
        return await self._data.api.fetch_image(self._device.preview_jpeg)
