from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ETDApiClient, ETDAuthError, ETDError, normalize_phone, normalize_token
from .const import (
    AUTH_METHOD_SMS,
    AUTH_METHOD_TOKEN,
    CONF_AUTH_METHOD,
    CONF_CUSTOM_DEVICES,
    CONF_PHONE,
    CONF_TOKEN,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ETDIntercomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self.api: ETDApiClient | None = None
        self._phone: str | None = None
        self._call_id: str | None = None
        self._custom_devices: str = ""

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            method = user_input[CONF_AUTH_METHOD]
            if method == AUTH_METHOD_TOKEN:
                return await self.async_step_token()
            if method == AUTH_METHOD_SMS:
                return await self.async_step_phone()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AUTH_METHOD): vol.In(
                        {
                            AUTH_METHOD_TOKEN: "По готовому токену",
                            AUTH_METHOD_SMS: "По номеру телефона и SMS",
                        }
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_token(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {"error": ""}

        if user_input is not None:
            try:
                token = normalize_token(user_input[CONF_TOKEN])
                session = async_get_clientsession(self.hass)
                api = ETDApiClient(session, token)
                # Validate token by trying to load intercom list.
                await api.fetch_intercoms()
                return self.async_create_entry(
                    title="ETD Intercom",
                    data={
                        CONF_AUTH_METHOD: AUTH_METHOD_TOKEN,
                        CONF_TOKEN: token,
                        CONF_CUSTOM_DEVICES: user_input.get(CONF_CUSTOM_DEVICES, ""),
                    },
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("ETD token validation failed: %s", err)
                errors["base"] = "invalid_token"
                description_placeholders["error"] = str(err)

        return self.async_show_form(
            step_id="token",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOKEN): str,
                    vol.Optional(CONF_CUSTOM_DEVICES, default=""): str,
                }
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_phone(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {"error": ""}

        if user_input is not None:
            try:
                phone = normalize_phone(user_input[CONF_PHONE])
            except ValueError:
                errors["base"] = "invalid_phone"
                return self.async_show_form(
                    step_id="phone",
                    data_schema=vol.Schema({vol.Required(CONF_PHONE): str}),
                    errors=errors,
                    description_placeholders=description_placeholders,
                )

            self._custom_devices = user_input.get(CONF_CUSTOM_DEVICES, "")
            session = async_get_clientsession(self.hass)
            self.api = ETDApiClient(session)

            try:
                call_id = await self.api.login_by_phone(phone)
                await self.api.resend_sms(call_id)
                self._phone = phone
                self._call_id = call_id
                return await self.async_step_sms_code()
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("ETD SMS request failed: %s", err)
                errors["base"] = "cannot_send_sms"
                description_placeholders["error"] = str(err)

        return self.async_show_form(
            step_id="phone",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PHONE): str,
                    vol.Optional(CONF_CUSTOM_DEVICES, default=""): str,
                }
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_sms_code(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {"error": ""}

        if user_input is not None:
            if not self.api or not self._call_id:
                return await self.async_step_phone()

            try:
                token = await self.api.submit_sms_code(self._call_id, user_input["code"])
                return self.async_create_entry(
                    title="ETD Intercom",
                    data={
                        CONF_AUTH_METHOD: AUTH_METHOD_SMS,
                        CONF_PHONE: self._phone,
                        CONF_TOKEN: token,
                        CONF_CUSTOM_DEVICES: self._custom_devices,
                    },
                )
            except ETDAuthError as err:
                errors["base"] = "invalid_code"
                description_placeholders["error"] = str(err)
            except ETDError as err:
                errors["base"] = "cannot_login"
                description_placeholders["error"] = str(err)

        return self.async_show_form(
            step_id="sms_code",
            data_schema=vol.Schema({vol.Required("code"): str}),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        # Do not pass config_entry to the options flow.
        # In current Home Assistant versions self.config_entry is provided
        # by OptionsFlow itself; assigning it manually causes a 500 error.
        return ETDIntercomOptionsFlow()


class ETDIntercomOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_custom = self.config_entry.options.get(
            CONF_CUSTOM_DEVICES,
            self.config_entry.data.get(CONF_CUSTOM_DEVICES, ""),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_CUSTOM_DEVICES, default=current_custom): str,
                }
            ),
        )
