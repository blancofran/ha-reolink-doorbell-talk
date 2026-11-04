# Reolink Doorbell Talk

Live video, sound and **two-way voice** with a Reolink doorbell from Home Assistant, in a single package (integration + cards). It works at home and away **without opening ports, VPNs or external services**: everything goes through Home Assistant's normal connection.

> **Status: beta (0.5.0).** It works in the author's tests with a single model (Reolink Video Doorbell PoE), but there may be bugs and changes between versions. If something fails, open an issue and attach the integration diagnostics (sensitive data is redacted).

[Versión en español](README.es.md)

## What's inside

| Piece | Purpose |
|---|---|
| `reolink_talk` integration | Camera with the doorbell video, voice channel to the doorbell, automatic card registration |
| `custom:reolink-talk-card` | **Home and away**: HTTPS (HLS) video + talk button. About 3 s delay |
| `custom:reolink-talk-lan-card` | **Home only**: WebRTC video (lower delay) + the same talk button |

## Requirements

- Home Assistant 2025.1 or newer.
- A Reolink Video Doorbell (tested with the PoE model), its admin username and password, and local network access.
- To talk: open Home Assistant over **HTTPS** (for example Nabu Casa, a reverse proxy or Cloudflare). Browsers do not allow the microphone on plain `http://` (except `localhost`).

## Installation

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/blancofran/ha-reolink-doorbell-talk` as an *Integration*.
2. Install *Reolink Doorbell Talk* and restart Home Assistant.
3. *Settings → Devices & services → Add integration → Reolink Doorbell Talk*. Enter the doorbell IP address, username and password.
4. The cards register themselves. Add them to a dashboard (the camera's entity id depends on your doorbell's name and your language; look it up in *Settings → Devices & services*):

```yaml
type: custom:reolink-talk-card
entity: camera.doorbell_view_and_listen
title: Doorbell
```

Home only, with WebRTC (the WebRTC camera is created automatically):

```yaml
type: custom:reolink-talk-lan-card
entity: camera.doorbell_view_and_listen
```

## Doorbell status

Every minute the integration checks that the doorbell answers. If it does not (powered off, no network, cable unplugged), both cameras become *unavailable* and the cards show "The doorbell is not responding" instead of loading forever; the video resumes by itself when it is back.

## Integration options

- **Video quality**: light (less data, recommended away from home) or high.
- **Keep the video ready**: the video appears almost instantly, in exchange for a permanent, light connection to the doorbell.
- **Only administrators can talk**: other users still see the video but cannot use the talk button (off by default).

You can also **reconfigure** (change the address or credentials) and **re-authenticate** (if the password changes) from the integration itself, and download **diagnostics** with sensitive data redacted.

## Card options

Both cards have a visual editor (add the card from the card picker, or edit it and switch off *Show code editor*). The options in YAML:

`entity` (required), `title`, `mode` (`toggle`, or `hold` to talk while pressed; `hold_to_talk: true` is the same as `mode: hold` and is what the visual editor writes), `max_seconds` (90), `idle_seconds` (45), `warn_seconds` (10), `timeout` (12), `autoplay` (true), `show_info` (false: shows the transport and delay on the video, useful for troubleshooting), `view_fallback` (true: the LAN card falls back to HLS when WebRTC is unavailable), `aspect_ratio` (`4:3`; for example `16:9` or `19:8`), `crop_video` (false: crop the video to fill the frame instead of showing it whole), `max_width` (no limit by default), `view_timeout` (6), `hls_url` (by default the bundled copy of hls.js is used).

## Resizing

In sections dashboards the cards can be resized freely in edit mode (drag the handles, or use the *Layout* tab): the card fills the space it is given, in width and in height, and the video adapts to it. Use `aspect_ratio` to match the shape of your other cameras, `crop_video` to fill the frame without black bars, and `max_width` if you do want a width limit.

## How it works

- **Video and sound**: the doorbell offers an FLV stream over HTTP. Home Assistant turns it into HLS (`stream`) and the card plays it with hls.js (bundled). The LAN card uses WebRTC through Home Assistant's built-in go2rtc.
- **Voice**: browser microphone → AudioWorklet (8 kHz, G.711 µ-law) → Home Assistant WebSocket → RTSP client using the ONVIF *backchannel* → doorbell. Only one device can talk at a time; the session ends at the maximum time, when idle, or when the app goes to the background.

## Known limitations

- HLS has a minimum delay of about 3 s (it comes from how Home Assistant segments the video). For less delay at home use the LAN card.
- **Safari** in the browser may not support WebRTC with Home Assistant's built-in go2rtc (TCP only); the LAN card then **falls back to HLS automatically**. The cards work in the iOS and Android Companion apps in the author's tests.
- With **WebRTC Camera (AlexxIT)** installed at the same time, the WebRTC camera of this integration did not offer WebRTC in one installation; the LAN card detects it and uses HLS. Disable WebRTC Camera if you want WebRTC.
- HTTPS is required for the microphone.
- The doorbell password lives only in Home Assistant's config entry, never in the package files. It is stored in plain text in `/config/.storage/core.config_entries` and therefore also in backups: **encrypt your backups**. Creating a dedicated doorbell user for Home Assistant instead of using the admin account is recommended.
- By default any Home Assistant user who can open the dashboard can talk through the doorbell; turn on *Only administrators can talk* in the integration options to restrict it.
- Adding an already configured doorbell again updates its address, username and password.

## Troubleshooting

- *"Could not open the voice channel"*: another device is talking, or the doorbell does not accept a second voice session. Try again.
- *"Configuration error"* on the card: reload with Ctrl+Shift+R and check in *Settings → Dashboards → Resources* that the `/reolink_talk/` resources exist.
- *No video in the LAN card*: check that the entity is the doorbell's and that Home Assistant's built-in go2rtc is running; reload the card. The card falls back to HLS on its own when WebRTC fails.

## Development

Tests that need no Home Assistant:

```bash
python tests/test_standalone.py
python tests/test_talk.py
```

## Third-party software

The card bundles hls.js (Apache-2.0). See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## License

MIT
