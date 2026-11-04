"""Camera entity: the doorbell video and sound, served as HLS by Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_PRELOAD,
    CONF_QUALITY,
    DEFAULT_PRELOAD,
    DEFAULT_QUALITY,
    DOMAIN,
    stream_source,
    webrtc_source,
)
from .coordinator import ReolinkTalkCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the HTTPS camera and the LAN-only WebRTC camera (idle until a card uses it)."""
    coordinator: ReolinkTalkCoordinator = entry.runtime_data
    async_add_entities(
        [
            ReolinkTalkCamera(coordinator, entry, "view"),
            ReolinkTalkCamera(coordinator, entry, "webrtc"),
        ]
    )


class ReolinkTalkCamera(CoordinatorEntity[ReolinkTalkCoordinator], Camera):
    """Doorbell camera whose video is read by Home Assistant's stream component.

    It is unavailable while the doorbell does not answer.
    """

    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self, coordinator: ReolinkTalkCoordinator, entry: ConfigEntry, kind: str
    ) -> None:
        """Initialise the entity (kind is "view" for HTTPS or "webrtc" for LAN only)."""
        # CoordinatorEntity does not chain to Camera.__init__, so call both explicitly.
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._entry = entry
        self._kind = kind
        self._attr_translation_key = kind
        self._attr_unique_id = f"{entry.unique_id}_{kind}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.unique_id))},
            manufacturer="Reolink",
            name=entry.title,
        )

    async def async_added_to_hass(self) -> None:
        """Keep the stream ready when the option is on, so the video starts fast."""
        await super().async_added_to_hass()
        if self._kind == "view" and self._entry.options.get(CONF_PRELOAD, DEFAULT_PRELOAD):
            self.async_on_remove(async_at_started(self.hass, self._async_preload))

    async def _async_preload(self, hass: HomeAssistant) -> None:
        """Open the HLS stream and keep it alive, like HA's own preload option."""
        try:
            stream = await self.async_create_stream()
            if stream is None:
                return
            stream.keepalive = True
            stream.add_provider("hls")
            await stream.start()
        except Exception:  # noqa: BLE001 - a failed preload must never break the entity
            _LOGGER.warning("Could not preload the doorbell stream", exc_info=True)

    async def stream_source(self) -> str | None:
        """Return the stream URL that Home Assistant reads."""
        data = self._entry.data
        if self._kind == "webrtc":
            return webrtc_source(data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD])
        return stream_source(
            data[CONF_HOST],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            self._entry.options.get(CONF_QUALITY, DEFAULT_QUALITY),
        )

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image taken from the running stream, if there is one."""
        if self.stream is None:
            return None
        try:
            return await self.stream.async_get_image(width, height)
        except Exception:  # noqa: BLE001 - no image is better than an error
            return None
