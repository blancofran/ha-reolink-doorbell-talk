"""WebSocket commands that carry the microphone audio to the doorbell through HA."""

from __future__ import annotations

import base64
import binascii
import logging
import uuid

try:  # HA docs now use probatio; older cores still ship voluptuous.
    import probatio as vol
except ImportError:  # pragma: no cover
    import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_ADMIN_ONLY, DEFAULT_ADMIN_ONLY, DOMAIN
from .talk import BackchannelClient, BackchannelError, TalkSession

_LOGGER = logging.getLogger(__name__)

SESSIONS = f"{DOMAIN}_sessions"  # hass.data: session id -> (entry_id, connection, session)


def _entry_for_entity(hass: HomeAssistant, entity_id: str) -> ConfigEntry | None:
    entry_ent = er.async_get(hass).async_get(entity_id)
    if entry_ent is None or entry_ent.platform != DOMAIN or not entry_ent.config_entry_id:
        return None
    return hass.config_entries.async_get_entry(entry_ent.config_entry_id)


async def async_close_sessions(hass: HomeAssistant, entry_id: str) -> None:
    """Close every voice session of a config entry (used when the entry is unloaded)."""
    sessions = hass.data.get(SESSIONS, {})
    for session_id, (owner, _connection, session) in list(sessions.items()):
        if owner == entry_id:
            sessions.pop(session_id, None)
            await session.async_close("unloaded")


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    """Register the WebSocket commands."""
    websocket_api.async_register_command(hass, ws_talk)
    websocket_api.async_register_command(hass, ws_audio)


@websocket_api.websocket_command(
    {vol.Required("type"): "reolink_talk/talk", vol.Required("entity_id"): str}
)
@websocket_api.async_response
async def ws_talk(hass: HomeAssistant, connection, msg: dict) -> None:
    """Open a voice session; the audio then arrives with reolink_talk/audio."""
    entry = _entry_for_entity(hass, msg["entity_id"])
    if entry is None:
        connection.send_error(msg["id"], "not_found", "Unknown talk entity")
        return
    if entry.options.get(CONF_ADMIN_ONLY, DEFAULT_ADMIN_ONLY) and not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Only administrators can talk")
        return
    sessions = hass.data.setdefault(SESSIONS, {})
    if any(item[0] == entry.entry_id for item in sessions.values()):
        connection.send_error(msg["id"], "busy", "Someone else is already talking")
        return

    session_id = uuid.uuid4().hex
    data = entry.data

    def _closed(reason: str) -> None:
        sessions.pop(session_id, None)
        connection.send_message(
            websocket_api.event_message(msg["id"], {"event": "closed", "reason": reason})
        )

    client = BackchannelClient(data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD])
    session = TalkSession(client, _closed)
    # Reserve the slot before the slow network handshake so two clients cannot race.
    sessions[session_id] = (entry.entry_id, connection, session)
    try:
        await session.async_start()
    except BackchannelError as err:
        sessions.pop(session_id, None)
        _LOGGER.warning("Could not open the doorbell voice channel: %s", err)
        if str(err) == "invalid_auth":
            entry.async_start_reauth(hass)
        connection.send_error(msg["id"], "talk_failed", str(err))
        return

    @callback
    def _unsub() -> None:
        hass.async_create_task(session.async_close("client"))

    connection.subscriptions[msg["id"]] = _unsub
    connection.send_result(msg["id"])
    connection.send_message(
        websocket_api.event_message(msg["id"], {"event": "ready", "session": session_id})
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "reolink_talk/audio",
        vol.Required("session"): str,
        vol.Required("data"): str,
    }
)
@callback
def ws_audio(hass: HomeAssistant, connection, msg: dict) -> None:
    """Receive a chunk of mu-law audio (base64) for a session."""
    item = hass.data.get(SESSIONS, {}).get(msg["session"])
    if item is None or item[1] is not connection:
        return
    try:
        item[2].feed(base64.b64decode(msg["data"], validate=True))
    except (binascii.Error, ValueError):
        _LOGGER.debug("Ignoring a malformed audio chunk")
