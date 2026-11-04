"""Constants for the Reolink Doorbell Talk integration."""

from __future__ import annotations

from urllib.parse import quote

DOMAIN = "reolink_talk"

CONF_PRELOAD = "preload"
CONF_QUALITY = "quality"
CONF_ADMIN_ONLY = "admin_only"
DEFAULT_ADMIN_ONLY = False
QUALITY_LIGHT = "sub"
QUALITY_HIGH = "main"
DEFAULT_QUALITY = QUALITY_LIGHT
DEFAULT_PRELOAD = True

CARD_URL = "/reolink_talk/reolink-talk-card.js"
CARD_LAN_URL = "/reolink_talk/reolink-talk-lan-card.js"
CARD_VERSION = "0.5.1"


def stream_source(
    host: str, username: str, password: str, quality: str = DEFAULT_QUALITY
) -> str:
    """Return a plain FLV URL that Home Assistant's own HLS stream can read."""
    channel = "channel0_main.bcs" if quality == QUALITY_HIGH else "channel0_sub.bcs"
    user = quote(username, safe="")
    pwd = quote(password, safe="")
    return (
        f"http://{host}/flv?port=1935&app=bcs&stream={channel}"
        f"&user={user}&password={pwd}"
    )


def webrtc_source(host: str, username: str, password: str) -> str:
    """Return the go2rtc source for the LAN-only WebRTC mode (main stream, audio to Opus)."""
    user = quote(username, safe="")
    pwd = quote(password, safe="")
    return (
        f"ffmpeg:http://{host}/flv?port=1935&app=bcs&stream=channel0_main.bcs"
        f"&user={user}&password={pwd}#video=copy#audio=copy#audio=opus"
    )
