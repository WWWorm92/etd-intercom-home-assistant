"""Config flow for ETD Intercom."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EtdApiError, EtdIntercomApiClient
from .const import (
    AUTH_METHOD_SMS,
    AUTH_METHOD_TOKEN,
    CONF_AUTH_METHOD,
    CONF_CUSTOM_DEVICES,
    CONF_INCLUDE_MANUAL_DEVICES,
    CONF_PHONE,
    CONF_TOKEN,
    DOMAIN,
)
from .helpers import normalize_phone, parse_custom_devices

_LOGGER = logging.getLogger(__name__)

CUSTOM_DEVICES_EXAMPLE = """000270 | Подъезд 1 | mdi:door-open
001586 | Ворота 1 | mdi:gate-open
# Можно также: 000267=Парадная 2"""


def _custom_devices_selector() -> selector.TextSelector:
    return selector.TextSelector(
        selector.TextSelectorConfig(
            multiline=True,
        )
    )


def _user_schema(default_custom_devices: str = "") -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_AUTH_METHOD): vol.In(
                {
                    AUTH_METHOD_TOKEN: "По готовому токену",
                    AUTH_METHOD_SMS: "По номеру телефона и SMS",
                }
            ),
            vol.Optional(CONF_INCLUDE_MANUAL_DEVICES, default=True): bool,
            vol.Optional(CONF_CUSTOM_DEVICES, default=default_custom_devices): _custom_devices_selector(),
        }
    )


def _options_schema(
    include_manual_devices: bool,
    custom_devices: str,
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_INCLUDE_MANUAL_DEVICES, default=include_manual_devices): bool,
            vol.Optional(CONF_CUSTOM_DEVICES, default=custom_devices): _custom_devices_selector(),
        }
    )


class EtdIntercomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle ETD Intercom config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._auth_method: str | None = None
        self._include_manual_devices = True
        self._custom_devices = ""
        self._phone: str | None = None
        self._call_id: str | None = None

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return EtdIntercomOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """First step: choose auth method."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"error": "", "example": CUSTOM_DEVICES_EXAMPLE}

        if user_input is not None:
            custom_devices = str(user_input.get(CONF_CUSTOM_DEVICES) or "")
            try:
                parse_custom_devices(custom_devices)
            except ValueError as err:
                errors[CONF_CUSTOM_DEVICES] = "invalid_custom_devices"
                placeholders["error"] = str(err)
            else:
                self._auth_method = user_input[CONF_AUTH_METHOD]
                self._include_manual_devices = user_input.get(CONF_INCLUDE_MANUAL_DEVICES, True)
                self._custom_devices = custom_devices

                if self._auth_method == AUTH_METHOD_TOKEN:
                    return await self.async_step_token()
                return await self.async_step_phone()

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(),
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Token auth step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            token = EtdIntercomApiClient.normalize_token(user_input[CONF_TOKEN])
            api = EtdIntercomApiClient(async_get_clientsession(self.hass), token)
            try:
                await api.validate_token()
            except EtdApiError as err:
                _LOGGER.warning("ETD token validation failed: %s", err)
                errors["base"] = "invalid_token"
            else:
                return self.async_create_entry(
                    title="ETD Intercom",
                    data={
                        CONF_AUTH_METHOD: AUTH_METHOD_TOKEN,
                        CONF_TOKEN: token,
                        CONF_INCLUDE_MANUAL_DEVICES: self._include_manual_devices,
                        CONF_CUSTOM_DEVICES: self._custom_devices,
                    },
                )

        schema = vol.Schema({vol.Required(CONF_TOKEN): str})
        return self.async_show_form(step_id="token", data_schema=schema, errors=errors)

    async def async_step_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Phone login step."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"error": ""}

        if user_input is not None:
            try:
                phone = normalize_phone(user_input[CONF_PHONE])
            except ValueError:
                errors["base"] = "invalid_phone"
            else:
                api = EtdIntercomApiClient(async_get_clientsession(self.hass))
                try:
                    call_id = await api.login_by_phone(phone)
                    await api.resend_sms(call_id)
                except EtdApiError as err:
                    _LOGGER.warning("ETD SMS request failed: %s", err)
                    errors["base"] = "cannot_send_sms"
                    placeholders["error"] = str(err)
                else:
                    self._phone = phone
                    self._call_id = call_id
                    return await self.async_step_sms_code()

        schema = vol.Schema({vol.Required(CONF_PHONE): str})
        return self.async_show_form(
            step_id="phone",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_sms_code(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """SMS code submit step."""
        errors: dict[str, str] = {}
        placeholders = {"phone": self._phone or ""}

        if user_input is not None:
            api = EtdIntercomApiClient(async_get_clientsession(self.hass))
            try:
                token = await api.submit_sms_code(
                    call_id=str(self._call_id),
                    code=user_input["code"],
                )
            except EtdApiError as err:
                _LOGGER.warning("ETD SMS code submit failed: %s", err)
                errors["base"] = "invalid_code"
            else:
                return self.async_create_entry(
                    title="ETD Intercom",
                    data={
                        CONF_AUTH_METHOD: AUTH_METHOD_SMS,
                        CONF_PHONE: self._phone,
                        CONF_TOKEN: token,
                        CONF_INCLUDE_MANUAL_DEVICES: self._include_manual_devices,
                        CONF_CUSTOM_DEVICES: self._custom_devices,
                    },
                )

        schema = vol.Schema({vol.Required("code"): str})
        return self.async_show_form(
            step_id="sms_code",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )


class EtdIntercomOptionsFlow(config_entries.OptionsFlow):
    """Handle ETD Intercom options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage ETD Intercom options."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"error": "", "example": CUSTOM_DEVICES_EXAMPLE}

        current_include_manual = bool(
            self._config_entry.options.get(
                CONF_INCLUDE_MANUAL_DEVICES,
                self._config_entry.data.get(CONF_INCLUDE_MANUAL_DEVICES, True),
            )
        )
        current_custom_devices = str(
            self._config_entry.options.get(
                CONF_CUSTOM_DEVICES,
                self._config_entry.data.get(CONF_CUSTOM_DEVICES, ""),
            )
            or ""
        )

        if user_input is not None:
            custom_devices = str(user_input.get(CONF_CUSTOM_DEVICES) or "")
            try:
                parse_custom_devices(custom_devices)
            except ValueError as err:
                errors[CONF_CUSTOM_DEVICES] = "invalid_custom_devices"
                placeholders["error"] = str(err)
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_INCLUDE_MANUAL_DEVICES: user_input.get(
                            CONF_INCLUDE_MANUAL_DEVICES,
                            current_include_manual,
                        ),
                        CONF_CUSTOM_DEVICES: custom_devices,
                    },
                )

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(current_include_manual, current_custom_devices),
            errors=errors,
            description_placeholders=placeholders,
        )
