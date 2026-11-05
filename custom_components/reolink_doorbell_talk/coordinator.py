"""Reachability check, so the cameras show as unavailable when the doorbell is off."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_SECONDS = 60
CONNECT_TIMEOUT = 5
HTTP_PORT = 80  # the video is read from the doorbell's HTTP (FLV) port


class ReolinkTalkCoordinator(DataUpdateCoordinator[bool]):
    """Check every minute that the doorbell answers on its HTTP port."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(seconds=UPDATE_SECONDS),
        )
        self._host: str = entry.data[CONF_HOST]

    async def _async_update_data(self) -> bool:
        """Return True when the doorbell accepts a TCP connection."""
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, HTTP_PORT), CONNECT_TIMEOUT
            )
        except (OSError, TimeoutError) as err:
            raise UpdateFailed(f"The doorbell at {self._host} is not reachable") from err
        writer.close()
        return True
