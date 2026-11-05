"""Diagnostics for Reolink Doorbell Talk (credentials are redacted)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, CONF_HOST, "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "unique_id": entry.unique_id,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            TO_REDACT,
        ),
        "entities": [
            {"entity_id": e.entity_id, "disabled": e.disabled}
            for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        ],
    }
