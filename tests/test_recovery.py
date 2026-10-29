"""Regression coverage for startup retry and credential recovery."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError
import pytest

from homeassistant.config_entries import ConfigEntryState, SOURCE_REAUTH, SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.etd_intercom import async_setup_entry
from custom_components.etd_intercom.api import ETDApiClient, ETDAuthError, ETDDevice, ETDError
from custom_components.etd_intercom.const import DOMAIN

API_CLASS = "custom_components.etd_intercom.ETDApiClient"
FLOW_API = "custom_components.etd_intercom.config_flow.ETDApiClient"
DATA = {"auth_method": "token", "token": "Bearer old", "custom_devices": "123 | Door"}


def entry_for(hass, **kwargs):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, **kwargs)
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize("failure", [ETDError("offline"), ETDError("HTTP 503")])
async def test_setup_failure_then_ha_retry_creates_devices(hass, freezer, failure):
    """The HA setup manager retries; no successful empty setup is recorded."""
    entry = entry_for(hass)
    await hass.async_start()
    camera = ETDDevice(id="42", name="Camera", preview_jpeg="https://example.invalid/p.jpg")
    with (
        patch("custom_components.etd_intercom.async_setup", return_value=True),
        patch(API_CLASS) as api_cls,
        patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock) as forward,
    ):
        api_cls.return_value.fetch_intercoms = AsyncMock(side_effect=failure)
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        assert entry.entry_id not in hass.data.get(DOMAIN, {})
        forward.assert_not_awaited()
        api_cls.return_value.fetch_intercoms.side_effect = None
        api_cls.return_value.fetch_intercoms.return_value = [camera]
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert {d.id for d in hass.data[DOMAIN][entry.entry_id].devices} == {"42", "123"}
        forward.assert_awaited_once()


async def test_auth_failure_starts_reauth_instead_of_retry(hass):
    entry = entry_for(hass)
    with (
        patch("custom_components.etd_intercom.async_setup", return_value=True),
        patch(API_CLASS) as api_cls,
        patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock) as forward,
    ):
        api_cls.return_value.fetch_intercoms = AsyncMock(side_effect=ETDAuthError("expired"))
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    forward.assert_not_awaited()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_valid_empty_account_still_loads_manual_devices(hass):
    entry = entry_for(hass)
    with patch(API_CLASS) as api_cls, patch.object(hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock):
        api_cls.return_value.fetch_intercoms = AsyncMock(return_value=[])
        assert await async_setup_entry(hass, entry)
    assert [d.id for d in hass.data[DOMAIN][entry.entry_id].devices] == ["123"]


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
async def test_api_classifies_http_failure(status):
    session = AsyncMock()
    response = session.get.return_value
    response.status = status
    response.text.return_value = '{"error":"private response body"}'
    error = ETDAuthError if status in (401, 403) else ETDError
    with pytest.raises(error) as raised:
        await ETDApiClient(session, "test").fetch_intercoms()
    assert "private response body" not in str(raised.value)
    assert isinstance(raised.value, ETDAuthError) is (status in (401, 403))


@pytest.mark.parametrize("failure", [ClientConnectionError("offline"), TimeoutError()])
async def test_api_wraps_network_errors(failure):
    session = AsyncMock()
    session.get.side_effect = failure
    with pytest.raises(ETDError) as raised:
        await ETDApiClient(session, "test").fetch_intercoms()
    assert not isinstance(raised.value, ETDAuthError)


@pytest.mark.parametrize("body", [
    "<html>maintenance</html>", "{}", "[]", '{"flats":null}',
    '{"flats":[null]}', '{"flats":[{"intercoms":"broken"}]}',
    '{"flats":[{"intercoms":[null]}]}',
    '{"flats":[{"intercoms":[{"sip_username":"42","camera":"broken"}]}]}',
])
async def test_api_rejects_broken_success_response(body):
    session = AsyncMock()
    session.get.return_value.status = 200
    session.get.return_value.text.return_value = body
    with pytest.raises(ETDError):
        await ETDApiClient(session, "test").fetch_intercoms()


async def test_api_accepts_genuinely_empty_list():
    session = AsyncMock()
    session.get.return_value.status = 200
    session.get.return_value.text.return_value = '{"flats":[]}'
    assert await ETDApiClient(session, "test").fetch_intercoms() == []


async def test_api_parses_valid_devices():
    session = AsyncMock()
    session.get.return_value.status = 200
    session.get.return_value.text.return_value = (
        '{"flats":[{"address_standard":"Address","intercoms":['
        '{"sip_username":"42","default_name":"Door","camera":'
        '{"preview_jpeg":"https://example.invalid/preview.jpg"}}]}]}'
    )
    devices = await ETDApiClient(session, "test").fetch_intercoms()
    assert len(devices) == 1
    assert devices[0].id == "42"
    assert devices[0].name == "Door"
    assert devices[0].address == "Address"
    assert devices[0].preview_jpeg == "https://example.invalid/preview.jpg"


async def reauth_form(hass, entry, method):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id}, data=entry.data,
    )
    assert result["step_id"] == "reauth_confirm"
    return await hass.config_entries.flow.async_configure(result["flow_id"], {"auth_method": method})


async def test_token_reauth_updates_existing_entry_and_preserves_options(hass):
    entry = entry_for(hass, title="My intercom", options={"custom_devices": "456 | Gate"})
    original_id = entry.entry_id
    result = await reauth_form(hass, entry, "token")
    assert result["step_id"] == "token"
    with patch(FLOW_API) as api_cls, patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        api_cls.return_value.fetch_intercoms = AsyncMock(return_value=[])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"token": "new"})
        await hass.async_block_till_done()
        reload.assert_awaited_once_with(original_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"] == "Bearer new"
    assert entry.data["custom_devices"] == DATA["custom_devices"]
    assert entry.options == {"custom_devices": "456 | Gate"}
    assert entry.title == "My intercom"
    assert [e.entry_id for e in hass.config_entries.async_entries(DOMAIN)] == [original_id]


@pytest.mark.parametrize("failure,expected", [(ETDAuthError("bad"), "invalid_token"), (ETDError("offline"), "cannot_connect")])
async def test_reauth_failure_keeps_credentials_and_shows_correct_error(hass, failure, expected):
    entry = entry_for(hass)
    result = await reauth_form(hass, entry, "token")
    with patch(FLOW_API) as api_cls, patch.object(hass.config_entries, "async_reload") as reload:
        api_cls.return_value.fetch_intercoms = AsyncMock(side_effect=failure)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"token": "bad"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    assert entry.data == DATA
    reload.assert_not_called()


async def test_sms_reauth_reuses_entry(hass):
    entry = entry_for(hass, options={"custom_devices": "456 | Gate"})
    result = await reauth_form(hass, entry, "sms")
    with patch(FLOW_API) as api_cls, patch.object(hass.config_entries, "async_reload", return_value=True):
        api = api_cls.return_value
        api.login_by_phone = AsyncMock(return_value="call")
        api.resend_sms = AsyncMock(return_value={})
        api.submit_sms_code = AsyncMock(side_effect=[ETDAuthError("bad code"), "Bearer renewed"])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"phone": "89991234567"})
        assert result["step_id"] == "sms_code"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": "000000"})
        assert result["errors"] == {"base": "invalid_code"}
        assert entry.data["token"] == "Bearer old"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"code": "123456"})
        await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"] == "Bearer renewed"
    assert entry.data["phone"] == "+79991234567"
    assert entry.data["custom_devices"] == DATA["custom_devices"]
    assert entry.options == {"custom_devices": "456 | Gate"}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_initial_token_setup_still_creates_entry(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"auth_method": "token"})
    with patch(FLOW_API) as api_cls, patch("custom_components.etd_intercom.async_setup_entry", return_value=True):
        api_cls.return_value.fetch_intercoms = AsyncMock(return_value=[])
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"token": "new"})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["token"] == "Bearer new"
