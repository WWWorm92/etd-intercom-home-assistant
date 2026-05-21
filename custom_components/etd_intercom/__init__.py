from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from aiohttp import ClientError, web

from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ETDApiClient, ETDDevice, apply_default_video_links, get_shared_video_params, merge_devices, parse_custom_devices
from .const import (
    CARD_FILENAME,
    CONF_CUSTOM_DEVICES,
    CONF_TOKEN,
    DOMAIN,
    PLATFORMS,
    STATIC_DIR_NAME,
    STATIC_URL_PATH,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class ETDData:
    api: ETDApiClient
    devices: list[ETDDevice]


class ETDWHEPProxyView(HomeAssistantView):
    """Proxy WHEP SDP signaling to ETD/Flussonic without exposing Bearer token to frontend."""

    url = "/api/etd_intercom/whep/{entry_id}/{intercom_id}"
    name = "api:etd_intercom:whep"
    requires_auth = True

    async def post(self, request: web.Request, entry_id: str, intercom_id: str) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        data: ETDData | None = hass.data.get(DOMAIN, {}).get(entry_id)
        if data is None:
            return web.Response(status=404, text="ETD entry not found")

        device = next((item for item in data.devices if item.id == intercom_id), None)
        if device is None:
            return web.Response(status=404, text="ETD intercom not found")
        if not device.whep_url:
            return web.Response(status=404, text="ETD WHEP URL is not available")
        if not data.api.token:
            return web.Response(status=401, text="ETD token is not configured")

        offer_sdp = await request.text()
        if not offer_sdp.strip():
            return web.Response(status=400, text="Empty SDP offer")

        headers = {
            "Authorization": data.api.token,
            "Content-Type": "application/sdp",
            "Accept": "application/sdp, */*",
            "Origin": "https://etd-online.ru",
            "Referer": "https://etd-online.ru/",
            "User-Agent": "Mozilla/5.0 HomeAssistant ETDIntercom/0.7",
        }

        try:
            async with asyncio.timeout(25):
                response = await data.api.session.post(
                    device.whep_url,
                    headers=headers,
                    data=offer_sdp.encode("utf-8"),
                )
                body = await response.read()
        except (TimeoutError, ClientError) as err:
            _LOGGER.warning("ETD WHEP proxy failed for %s: %s", intercom_id, err)
            return web.Response(status=502, text=f"ETD WHEP proxy failed: {err}")

        response_headers = {}
        if location := response.headers.get("Location"):
            response_headers["Location"] = location

        content_type = response.headers.get("Content-Type") or "application/sdp"
        return web.Response(
            status=response.status,
            body=body,
            headers=response_headers,
            content_type=content_type.split(";", 1)[0],
        )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up ETD Intercom static frontend resources."""
    frontend_path = Path(__file__).parent / STATIC_DIR_NAME
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL_PATH, str(frontend_path), False)]
    )
    hass.http.register_view(ETDWHEPProxyView())
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    api = ETDApiClient(session, entry.data.get(CONF_TOKEN))

    api_devices: list[ETDDevice] = []
    try:
        api_devices = await api.fetch_intercoms()
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Failed to load ETD intercom list, using manual devices only: %s", err)

    custom_raw = entry.options.get(CONF_CUSTOM_DEVICES, entry.data.get(CONF_CUSTOM_DEVICES, ""))
    manual_devices = parse_custom_devices(custom_raw)
    devices = merge_devices(api_devices, manual_devices)

    # ETD uses one video token for the account in embed_link.
    # Manually added IDs are not returned by /intercom/list, so they do not have embed/WHEP links.
    # Reuse the token from any API camera to build iframe and WHEP URLs for custom IDs.
    video_token, video_sip_username = get_shared_video_params(api_devices)
    devices = apply_default_video_links(devices, video_token, video_sip_username)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ETDData(api=api, devices=devices)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info(
        "ETD Intercom loaded %s devices. Lovelace card URL: %s/%s",
        len(devices),
        STATIC_URL_PATH,
        CARD_FILENAME,
    )
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
