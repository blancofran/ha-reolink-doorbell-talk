"""Setup, availability, unload and diagnostics of the integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.reolink_talk.const import DOMAIN
from custom_components.reolink_talk.diagnostics import async_get_config_entry_diagnostics
from custom_components.reolink_talk.websocket import SESSIONS

from .conftest import HOST, PASSWORD, SERIAL, USER


def _camera_ids(hass, entry):
    registry = er.async_get(hass)
    return {
        e.unique_id: e.entity_id
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }


async def test_setup_creates_both_cameras(hass: HomeAssistant, reachable, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    ids = _camera_ids(hass, entry)
    assert set(ids) == {f"{SERIAL}_view", f"{SERIAL}_webrtc"}
    for entity_id in ids.values():
        assert hass.states.get(entity_id).state == "idle"


async def test_setup_retries_when_the_doorbell_is_off(hass: HomeAssistant, entry) -> None:
    entry.add_to_hass(hass)
    with patch(
        "custom_components.reolink_talk.coordinator.asyncio.open_connection",
        AsyncMock(side_effect=OSError("unreachable")),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_cameras_become_unavailable_and_recover(hass: HomeAssistant, reachable, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ids = _camera_ids(hass, entry)
    coordinator = entry.runtime_data

    reachable.side_effect = OSError("down")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert all(hass.states.get(i).state == "unavailable" for i in ids.values())

    reachable.side_effect = None
    reachable.return_value = (MagicMock(), MagicMock())
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert all(hass.states.get(i).state == "idle" for i in ids.values())


async def test_unload_closes_open_voice_sessions(hass: HomeAssistant, reachable, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    mine, other = MagicMock(), MagicMock()
    mine.async_close, other.async_close = AsyncMock(), AsyncMock()
    hass.data[SESSIONS] = {"a": (entry.entry_id, MagicMock(), mine), "b": ("other-entry", MagicMock(), other)}
    assert await hass.config_entries.async_unload(entry.entry_id)
    mine.async_close.assert_awaited_once_with("unloaded")
    other.async_close.assert_not_awaited()
    assert list(hass.data[SESSIONS]) == ["b"]


async def test_diagnostics_hide_the_credentials(hass: HomeAssistant, reachable, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    data = await async_get_config_entry_diagnostics(hass, entry)
    text = str(data)
    for secret in (PASSWORD, HOST, USER, SERIAL):
        assert secret not in text, secret
    assert data["entry"]["data"]["password"] == "**REDACTED**"
    assert len(data["entities"]) == 2


async def test_stream_source_uses_the_quoted_credentials(hass: HomeAssistant, reachable, entry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    ids = _camera_ids(hass, entry)
    from homeassistant.components.camera import async_get_stream_source

    view = await async_get_stream_source(hass, ids[f"{SERIAL}_view"])
    webrtc = await async_get_stream_source(hass, ids[f"{SERIAL}_webrtc"])
    assert view.startswith(f"http://{HOST}/flv?") and "channel0_sub.bcs" in view
    assert "p%40ss%20w%26rd%231" in view and PASSWORD not in view
    assert webrtc.startswith(f"ffmpeg:http://{HOST}/flv?") and "audio=opus" in webrtc
