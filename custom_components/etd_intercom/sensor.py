from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

TOPIC_STATE = "etd/intercom/call/state"
TOPIC_DATA = "etd/intercom/call/data"


def _payload_to_str(payload: Any) -> str:
    if isinstance(payload, bytes):
        return payload.decode("utf-8", errors="replace").strip()
    return str(payload).strip()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([ETDIntercomCallSensor(entry.entry_id)])


class ETDIntercomCallSensor(SensorEntity):
    """MQTT-backed sensor for incoming ETD intercom calls."""

    _attr_has_entity_name = False
    _attr_name = "ETD Intercom Call"
    _attr_unique_id = None
    _attr_icon = "mdi:phone-ring"
    _attr_should_poll = False

    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id
        self._attr_unique_id = f"etd_{entry_id}_intercom_call"
        self._attr_native_value = "idle"
        self._attrs: dict[str, Any] = {
            "intercom_id": None,
            "name": "Домофон",
            "time": None,
            "mqtt_state_topic": TOPIC_STATE,
            "mqtt_data_topic": TOPIC_DATA,
        }
        self._unsub_state = None
        self._unsub_data = None
        self._mqtt_available = False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = dict(self._attrs)
        attrs["mqtt_available"] = self._mqtt_available
        return attrs

    async def async_added_to_hass(self) -> None:
        try:
            from homeassistant.components import mqtt

            self._unsub_state = await mqtt.async_subscribe(
                self.hass,
                TOPIC_STATE,
                self._message_state,
                0,
            )
            self._unsub_data = await mqtt.async_subscribe(
                self.hass,
                TOPIC_DATA,
                self._message_data,
                0,
            )
            self._mqtt_available = True
        except Exception as err:  # noqa: BLE001
            self._mqtt_available = False
            _LOGGER.warning(
                "ETD Intercom Call sensor could not subscribe to MQTT topics. "
                "Make sure MQTT integration is configured: %s",
                err,
            )
        self.async_write_ha_state()

    @callback
    def _message_state(self, msg) -> None:
        payload = _payload_to_str(msg.payload)
        if not payload:
            return
        self._attr_native_value = payload
        self._attrs["last_state_payload"] = payload
        self.async_write_ha_state()

    @callback
    def _message_data(self, msg) -> None:
        payload = _payload_to_str(msg.payload)
        if not payload:
            return

        try:
            data = json.loads(payload)
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Invalid ETD call MQTT payload: %s", payload)
            self._attrs["last_raw_payload"] = payload
            self.async_write_ha_state()
            return

        state = data.get("state")
        if state:
            self._attr_native_value = state

        self._attrs.update(
            {
                "intercom_id": data.get("intercom_id"),
                "name": data.get("name"),
                "time": data.get("time"),
                "last_raw_payload": payload,
            }
        )
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_state:
            self._unsub_state()
            self._unsub_state = None
        if self._unsub_data:
            self._unsub_data()
            self._unsub_data = None
