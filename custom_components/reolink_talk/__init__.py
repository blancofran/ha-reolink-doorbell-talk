"""Reolink Doorbell Talk: video, audio and two-way voice for a Reolink doorbell."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import CARD_LAN_URL, CARD_URL, CARD_VERSION, CONF_WEBRTC, DEFAULT_WEBRTC, DOMAIN
from .websocket import async_register_commands

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["camera"]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
_CARD_REGISTERED = f"{DOMAIN}_card_registered"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the WebSocket commands once."""
    async_register_commands(hass)
    return True


async def _async_register_resource(hass: HomeAssistant, url: str) -> bool:
    """Add or update the card as a Lovelace resource; return False if impossible."""
    lovelace = hass.data.get("lovelace")
    resources = (
        lovelace.get("resources")
        if isinstance(lovelace, dict)
        else getattr(lovelace, "resources", None)
    )
    if resources is None:
        return False
    try:
        if not getattr(resources, "loaded", True):
            await resources.async_load()
            resources.loaded = True
        for item in resources.async_items():
            if str(item.get("url", "")).split("?")[0] != url.split("?")[0]:
                continue
            if item["url"] == url:
                return True
            if hasattr(resources, "async_update_item"):
                await resources.async_update_item(
                    item["id"], {"res_type": "module", "url": url}
                )
            else:
                item["url"] = url
            return True
        if hasattr(resources, "async_create_item"):
            await resources.async_create_item({"res_type": "module", "url": url})
        else:
            resources.data.append({"type": "module", "url": url})
    except Exception:  # noqa: BLE001 - never block the setup for a cosmetic resource
        _LOGGER.warning("Could not register the card as a dashboard resource", exc_info=True)
        return False
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the card and load it in the dashboards, once."""
    if hass.data.get(_CARD_REGISTERED):
        return
    hass.data[_CARD_REGISTERED] = True
    www = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL.rsplit("/", 1)[0], str(www), cache_headers=False)]
    )
    for base in (CARD_URL, CARD_LAN_URL):
        url = f"{base}?v={CARD_VERSION}"
        if not await _async_register_resource(hass, url):
            # YAML-mode dashboards or an unknown Lovelace layout: fall back to the global module.
            add_extra_js_url(hass, url)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a doorbell from a config entry."""
    await _async_register_card(hass)
    _async_remove_legacy_entities(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


def _async_remove_legacy_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove cameras of earlier versions and the WebRTC camera when it is disabled."""
    registry = er.async_get(hass)
    kinds = ["talk", "remote"]
    if not entry.options.get(CONF_WEBRTC, DEFAULT_WEBRTC):
        kinds.append("webrtc")
    for kind in kinds:
        entity_id = registry.async_get_entity_id("camera", DOMAIN, f"{entry.unique_id}_{kind}")
        if entity_id:
            registry.async_remove(entity_id)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
