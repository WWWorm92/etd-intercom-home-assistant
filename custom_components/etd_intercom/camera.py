"""Camera entities for ETD Intercom."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    """Set up ETD Intercom camera entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    api: EtdIntercomApiClient = data["api"]
    devices: list[dict[str, Any]] = data["devices"]

    cameras = [EtdIntercomCamera(api, device) for device in devices if device.get("camera_preview_jpeg")]
    async_add_entities(cameras)


class EtdIntercomCamera(Camera):
    """Still-image camera based on ETD preview JPEG."""

    _attr_has_entity_name = True
    _attr_content_type = "image/jpeg"

    def __init__(self, api: EtdIntercomApiClient, device: dict[str, Any]) -> None:
        super().__init__()
        self._api = api
        self._device = device
        self._preview_url = device.get("camera_preview_jpeg")

        self._attr_name = "Камера"
        self._attr_unique_id = f"etd_intercom_{device['slug']}_camera"
        self._attr_suggested_object_id = f"etd_{device['slug']}_camera"
        self._attr_icon = "mdi:cctv"

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
        """Return camera attributes."""
        attrs: dict[str, Any] = {
            "intercom_id": self._device["id"],
            "intercom_name": self._device["name"],
            "camera_name": self._device.get("camera_name"),
            "camera_preview_jpeg": self._device.get("camera_preview_jpeg"),
            "source": self._device.get("source"),
        }
        if self._device.get("camera_embed_link"):
            attrs["camera_embed_link"] = self._device["camera_embed_link"]
        return attrs

    async def async_camera_image(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes | None:
        """Return the latest camera image."""
        image = await self._api.fetch_camera_image(self._preview_url)
        if image is None:
            _LOGGER.debug("ETD preview image is unavailable for %s", self._device["id"])
        return image
