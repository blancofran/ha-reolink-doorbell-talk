# Contributing

Thank you for helping! Bug reports, compatibility reports and ideas are welcome: see *Reporting a problem or giving feedback* in the [README](README.md). This page is for people who want to change the code.

## How it works

- **Video and sound**: the doorbell offers an FLV stream over HTTP. Home Assistant turns it into HLS (`stream`) and the card plays it with hls.js (bundled). The LAN card uses WebRTC through Home Assistant's built-in go2rtc.
- **Voice**: browser microphone → AudioWorklet (8 kHz, G.711 µ-law) → Home Assistant WebSocket → RTSP client using the ONVIF *backchannel* → doorbell. Only one device can talk at a time; the session ends at the maximum time, when idle, or when the app goes to the background.

## Layout

| Path | What it is |
|---|---|
| `custom_components/reolink_talk/` | The integration (config flow, cameras, voice client, WebSocket commands, diagnostics) |
| `custom_components/reolink_talk/www/` | The two Lovelace cards, the microphone client and the bundled hls.js |
| `tests/` | Tests (see below) |

## Running the tests

Tests that need no Home Assistant (Python 3.11 or newer):

```bash
python3 tests/test_standalone.py
python3 tests/test_talk.py
```

Tests of the cards, in a simulated browser (Node.js 20 or newer):

```bash
cd tests/js && npm ci && npm test
```

Tests with Home Assistant (`pytest-homeassistant-custom-component`, Python 3.13):

```bash
pip install pytest-homeassistant-custom-component
python .github/scripts/ha_requirements.py > /tmp/ha_requirements.txt && pip install -r /tmp/ha_requirements.txt
pytest -q tests
```

The CI (`.github/workflows/validate.yml`) runs all of them plus hassfest and the HACS validation.

## Guidelines

- Code, comments, commit messages and the GitHub pages are in English. The cards and the integration are translated (English, Spanish); the Spanish README is `README.es.md`.
- Keep passwords and other secrets out of code, tests, logs and diagnostics.
- When you change a card, bump `CARD_VERSION` in `const.py` together with the `version` in `manifest.json`, so browsers load the new file.
