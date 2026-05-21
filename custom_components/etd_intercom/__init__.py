"""ETD Intercom integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EtdApiError, EtdIntercomApiClient
from .const import CONF_CUSTOM_DEVICES, CONF_INCLUDE_MANUAL_DEVICES, CONF_TOKEN, DOMAIN
from .helpers import merge_devices, parse_custom_devices

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.CAMERA]


def _include_manual(entry: ConfigEntry) -> bool:
    return bool(entry.options.get(CONF_INCLUDE_MANUAL_DEVICES, entry.data.get(CONF_INCLUDE_MANUAL_DEVICES, True)))


def _custom_devices_text(entry: ConfigEntry) -> str:
    return str(entry.options.get(CONF_CUSTOM_DEVICES, entry.data.get(CONF_CUSTOM_DEVICES, "")) or "")


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ETD Intercom from a config entry."""
    session = async_get_clientsession(hass)
    api = EtdIntercomApiClient(session, entry.data[CONF_TOKEN])

    auto_devices = []
    try:
        auto_devices = await api.get_intercoms()
        _LOGGER.info("Loaded %s ETD intercoms from API", len(auto_devices))
    except EtdApiError as err:
        _LOGGER.warning("Could not load ETD intercom list: %s", err)

    try:
        custom_devices = parse_custom_devices(_custom_devices_text(entry))
    except ValueError as err:
        _LOGGER.warning("Invalid custom ETD devices configuration: %s", err)
        custom_devices = []

    devices = merge_devices(
        auto_devices,
        include_manual_devices=_include_manual(entry),
        custom_devices=custom_devices,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "devices": devices,
    }

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload ETD Intercom config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
