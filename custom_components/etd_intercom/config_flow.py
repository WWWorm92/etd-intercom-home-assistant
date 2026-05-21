"""Config flow for ETD Intercom."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EtdApiError, EtdIntercomApiClient
from .const import (
    AUTH_METHOD_SMS,
    AUTH_METHOD_TOKEN,
    CONF_AUTH_METHOD,
    CONF_PHONE,
    CONF_TOKEN,
    DOMAIN,
)


class EtdIntercomConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an ETD Intercom config flow."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize flow state."""
        self._phone: str | None = None
        self._call_id: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Choose auth method."""
        await self.async_set_unique_id("etd_intercom")
        self._abort_if_unique_id_configured()

        if user_input is not None:
            method = user_input[CONF_AUTH_METHOD]
            if method == AUTH_METHOD_TOKEN:
                return await self.async_step_token()
            if method == AUTH_METHOD_SMS:
                return await self.async_step_phone()

        schema = vol.Schema(
            {
                vol.Required(CONF_AUTH_METHOD): vol.In(
                    {
                        AUTH_METHOD_TOKEN: "По готовому токену",
                        AUTH_METHOD_SMS: "По номеру телефона и SMS",
                    }
                )
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors={})

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
            except EtdApiError:
                errors["base"] = "invalid_token"
            else:
                return self.async_create_entry(
                    title="ETD Intercom",
                    data={CONF_AUTH_METHOD: AUTH_METHOD_TOKEN, CONF_TOKEN: token},
                )

        schema = vol.Schema({vol.Required(CONF_TOKEN): str})
        return self.async_show_form(step_id="token", data_schema=schema, errors=errors)

    async def async_step_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Phone login step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            phone = user_input[CONF_PHONE].strip()
            api = EtdIntercomApiClient(async_get_clientsession(self.hass))

            try:
                call_id = await api.login_by_phone(phone)
                await api.resend_sms(call_id)
            except EtdApiError:
                errors["base"] = "cannot_send_sms"
            else:
                self._phone = phone
                self._call_id = call_id
                return await self.async_step_sms_code()

        schema = vol.Schema({vol.Required(CONF_PHONE): str})
        return self.async_show_form(step_id="phone", data_schema=schema, errors=errors)

    async def async_step_sms_code(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """SMS code submit step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api = EtdIntercomApiClient(async_get_clientsession(self.hass))
            try:
                token = await api.submit_sms_code(
                    call_id=str(self._call_id),
                    code=user_input["code"],
                )
            except EtdApiError:
                errors["base"] = "invalid_code"
            else:
                return self.async_create_entry(
                    title="ETD Intercom",
                    data={
                        CONF_AUTH_METHOD: AUTH_METHOD_SMS,
                        CONF_PHONE: self._phone,
                        CONF_TOKEN: token,
                    },
                )

        schema = vol.Schema({vol.Required("code"): str})
        return self.async_show_form(
            step_id="sms_code",
            data_schema=schema,
            errors=errors,
            description_placeholders={"phone": self._phone or ""},
        )
