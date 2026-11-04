"""Config flow tests: setup, duplicates, re-authentication, reconfigure and options."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.reolink_talk.config_flow import CannotConnect, InvalidAuth
from custom_components.reolink_talk.const import DOMAIN

from .conftest import HOST, PASSWORD, SERIAL, USER

NO_SETUP = patch("custom_components.reolink_talk.async_setup_entry", return_value=True)
USER_INPUT = {"host": HOST, "username": USER, "password": PASSWORD}


async def test_user_flow_creates_the_entry(hass: HomeAssistant, validate) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    with NO_SETUP:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Front door"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == SERIAL


async def test_invalid_auth_then_success(hass: HomeAssistant, validate) -> None:
    validate.side_effect = InvalidAuth
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "invalid_auth"}
    validate.side_effect = None
    validate.return_value = {"serial": SERIAL, "name": "Front door"}
    with NO_SETUP:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_cannot_connect(hass: HomeAssistant, validate) -> None:
    validate.side_effect = CannotConnect
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_adding_the_same_doorbell_again_updates_its_credentials(hass: HomeAssistant, validate, entry) -> None:
    entry.add_to_hass(hass)
    new = {"host": "192.0.2.99", "username": "other", "password": "new-pass"}
    with NO_SETUP:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], new)
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"
    assert dict(entry.data) == new


async def test_reauth_updates_the_password(hass: HomeAssistant, validate, entry) -> None:
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "reauth_confirm"
    validate.side_effect = InvalidAuth
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"password": "wrong"})
    assert result["errors"] == {"base": "invalid_auth"}
    validate.side_effect = None
    validate.return_value = {"serial": SERIAL}
    with NO_SETUP:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"password": "right"})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reauth_successful"
    assert entry.data["password"] == "right"
    assert entry.data["host"] == HOST  # untouched


async def test_reconfigure_changes_the_address(hass: HomeAssistant, validate, entry) -> None:
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "reconfigure"
    new = {"host": "192.0.2.77", "username": USER, "password": PASSWORD}
    with NO_SETUP:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], new)
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    assert entry.data["host"] == "192.0.2.77"


async def test_reconfigure_refuses_a_different_doorbell(hass: HomeAssistant, validate, entry) -> None:
    entry.add_to_hass(hass)
    validate.return_value = {"serial": "SOMEONE-ELSE"}
    result = await entry.start_reconfigure_flow(hass)
    with NO_SETUP:
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "wrong_device"
    assert entry.data["host"] == HOST


async def test_options_flow(hass: HomeAssistant, reachable, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"quality": "main", "preload": False, "admin_only": True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert dict(entry.options) == {"quality": "main", "preload": False, "admin_only": True}
