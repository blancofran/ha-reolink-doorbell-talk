"""Config flow for Reolink Doorbell Talk."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import aiohttp

try:  # HA docs now use probatio; older cores still ship voluptuous.
    import probatio as vol
except ImportError:  # pragma: no cover
    import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_PRELOAD,
    CONF_QUALITY,
    DEFAULT_PRELOAD,
    DEFAULT_QUALITY,
    DOMAIN,
    QUALITY_HIGH,
    QUALITY_LIGHT,
)

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=10)


class InvalidAuth(Exception):
    """The doorbell rejected the credentials."""


class CannotConnect(Exception):
    """The doorbell could not be reached."""


async def _async_validate(hass, host: str, username: str, password: str) -> dict:
    """Log in to the doorbell and return its basic info."""
    session = async_get_clientsession(hass, verify_ssl=False)
    base = f"https://{host}/cgi-bin/api.cgi"
    login = [
        {
            "cmd": "Login",
            "param": {
                "User": {"Version": "0", "userName": username, "password": password}
            },
        }
    ]
    try:
        async with session.post(
            f"{base}?cmd=Login", json=login, timeout=_TIMEOUT
        ) as resp:
            data = await resp.json(content_type=None)
        item = data[0]
        if item.get("code") != 0:
            raise InvalidAuth
        token = item["value"]["Token"]["name"]
        async with session.post(
            f"{base}?cmd=GetDevInfo&token={token}",
            json=[{"cmd": "GetDevInfo", "action": 0, "param": {}}],
            timeout=_TIMEOUT,
        ) as resp:
            info = await resp.json(content_type=None)
        dev = info[0].get("value", {}).get("DevInfo", {})
        try:
            async with session.post(
                f"{base}?cmd=Logout&token={token}",
                json=[{"cmd": "Logout", "param": {}}],
                timeout=_TIMEOUT,
            ):
                pass
        except (aiohttp.ClientError, TimeoutError):
            pass
    except (aiohttp.ClientError, TimeoutError, ValueError, KeyError, IndexError) as err:
        raise CannotConnect from err
    return dev


class ReolinkTalkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the user flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return ReolinkTalkOptionsFlow()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Start a re-authentication (the password stopped working)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _async_validate(
                    self.hass,
                    entry.data[CONF_HOST],
                    entry.data[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"name": entry.title},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address or credentials of an existing doorbell."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                dev = await _async_validate(
                    self.hass,
                    user_input[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                serial = dev.get("serial")
                if serial and serial != entry.unique_id:
                    return self.async_abort(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        current = entry.data
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current[CONF_HOST]): str,
                vol.Required(CONF_USERNAME, default=current[CONF_USERNAME]): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for host and credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                dev = await _async_validate(
                    self.hass,
                    user_input[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                serial = dev.get("serial") or user_input[CONF_HOST]
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(
                    title=dev.get("name") or user_input[CONF_HOST],
                    data=user_input,
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_USERNAME, default="admin"): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class ReolinkTalkOptionsFlow(OptionsFlow):
    """Options: video quality and keeping the stream ready."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_QUALITY, default=options.get(CONF_QUALITY, DEFAULT_QUALITY)
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[QUALITY_LIGHT, QUALITY_HIGH],
                        translation_key="quality",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_PRELOAD, default=options.get(CONF_PRELOAD, DEFAULT_PRELOAD)
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
