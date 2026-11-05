"""WebSocket voice commands: talking, busy and the administrators-only option."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.reolink_doorbell_talk.websocket import SESSIONS

from .conftest import SERIAL


def _fake_session():
    session = MagicMock()
    session.async_start = AsyncMock()
    session.async_close = AsyncMock()
    return session


async def _setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return er.async_get(hass).async_get_entity_id("camera", "reolink_doorbell_talk", f"{SERIAL}_view")


async def test_talk_opens_a_session_and_reports_busy(hass: HomeAssistant, hass_ws_client, reachable, entry) -> None:
    entity_id = await _setup(hass, entry)
    client = await hass_ws_client(hass)
    with patch("custom_components.reolink_doorbell_talk.websocket.TalkSession", return_value=_fake_session()):
        await client.send_json_auto_id({"type": "reolink_doorbell_talk/talk", "entity_id": entity_id})
        assert (await client.receive_json())["success"] is True
        event = await client.receive_json()
        assert event["event"]["event"] == "ready" and event["event"]["session"]
        assert len(hass.data[SESSIONS]) == 1

        await client.send_json_auto_id({"type": "reolink_doorbell_talk/talk", "entity_id": entity_id})
        busy = await client.receive_json()
        assert busy["success"] is False and busy["error"]["code"] == "busy"


async def test_unknown_entity(hass: HomeAssistant, hass_ws_client, reachable, entry) -> None:
    await _setup(hass, entry)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "reolink_doorbell_talk/talk", "entity_id": "camera.nope"})
    reply = await client.receive_json()
    assert reply["success"] is False and reply["error"]["code"] == "not_found"


async def test_admin_only_blocks_normal_users(
    hass: HomeAssistant, hass_ws_client, hass_read_only_access_token, reachable, entry
) -> None:
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, options={"admin_only": True})
    entity_id = await _setup(hass, entry)

    normal = await hass_ws_client(hass, hass_read_only_access_token)
    await normal.send_json_auto_id({"type": "reolink_doorbell_talk/talk", "entity_id": entity_id})
    reply = await normal.receive_json()
    assert reply["success"] is False and reply["error"]["code"] == "unauthorized"
    assert not hass.data.get(SESSIONS)

    admin = await hass_ws_client(hass)
    with patch("custom_components.reolink_doorbell_talk.websocket.TalkSession", return_value=_fake_session()):
        await admin.send_json_auto_id({"type": "reolink_doorbell_talk/talk", "entity_id": entity_id})
        assert (await admin.receive_json())["success"] is True
