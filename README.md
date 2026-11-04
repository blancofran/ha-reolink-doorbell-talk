# Reolink Doorbell Talk

Live video, sound and **two-way voice** with a Reolink doorbell from Home Assistant, in a single package (integration + cards). It works at home and away **without opening ports, VPNs or external services**: everything goes through Home Assistant's normal connection.

> **Status: beta (0.5.1).** It works in the author's tests with a single model (Reolink Video Doorbell PoE), but there may be bugs and changes between versions. If something fails, open an issue and attach the integration diagnostics (sensitive data is redacted).

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

| Option | Default | What it does |
|---|---|---|
| `entity` | required | The doorbell camera of this integration |
| `title` | "Doorbell" | Title shown on the card |
| `hold_to_talk` | `false` | `true`: talk only while the button is pressed. Otherwise tap to start and tap to stop |
| `autoplay` | `true` | Start the video when the card appears |
| `aspect_ratio` | `4:3` | Shape of the video, for example `16:9` |
| `crop_video` | `false` | `true`: fill the frame, cropping the edges, instead of showing the whole image |
| `max_width` | no limit | Maximum width of the card, in pixels |
| `show_info` | `false` | Shows the delay on the video; useful when reporting a problem |
| `view_fallback` | `true` | LAN card only: switch to the normal video if the fast video cannot connect |
| `max_seconds` | `90` | Longest a single conversation can last |
| `idle_seconds` | `45` | The microphone closes after this many seconds of silence |
| `warn_seconds` | `10` | Warning shown this many seconds before the microphone closes |
| `timeout` | `12` | Seconds to wait for the doorbell to answer when you start talking |

Advanced: `view_timeout` (seconds to wait for the fast video, 6), `hls_url` (use your own copy of hls.js instead of the bundled one) and `mode: hold` (same as `hold_to_talk: true`).

## Resizing

In sections dashboards the cards can be resized freely in edit mode (drag the handles, or use the *Layout* tab): the card fills the space it is given, in width and in height, and the video adapts to it. Use `aspect_ratio` to match the shape of your other cameras, `crop_video` to fill the frame without black bars, and `max_width` if you do want a width limit.

## Compatibility

Tested devices. Reports come from users; the author has only the first one.

| Device | Video + sound | Voice | Reported by |
|---|---|---|---|
| Reolink Video Doorbell PoE | Works | Works | author |

**Does it work with your doorbell or camera?** Tell us with a [compatibility report](https://github.com/blancofran/ha-reolink-doorbell-talk/issues/new?template=compatibility_report.yml), whether it works or not. [All reports](https://github.com/blancofran/ha-reolink-doorbell-talk/issues?q=label%3Acompatibility) are public. Other brands are not supported yet: the video address is Reolink-specific, although the voice channel uses the standard ONVIF backchannel.

## Known limitations

- The main card has a delay of about 3 seconds. For less delay at home, use the LAN card.
- In the **Safari** browser the LAN card may not show video; it then switches to the main card's video by itself. Both cards work in the iOS and Android Home Assistant apps.
- If the **WebRTC Camera** add-on (AlexxIT) is also installed, the LAN card may fall back to the normal video. Disable that add-on if you want the lower delay.
- To talk you need to open Home Assistant over **HTTPS**.
- The doorbell password is stored inside Home Assistant, never in this package's files, but it is saved in plain text in Home Assistant's own configuration and therefore also in your backups: **encrypt your backups**. It is better to create a separate doorbell user for Home Assistant than to use the admin account.
- By default anyone who can open the dashboard can talk through the doorbell. Turn on *Only administrators can talk* in the integration options to restrict it.
- Adding a doorbell that is already configured updates its address, username and password.

## Troubleshooting

- *"Could not open the voice channel"*: another device is talking, or the doorbell does not accept a second voice session. Try again.
- *"Configuration error"* on the card: reload with Ctrl+Shift+R and check in *Settings → Dashboards → Resources* that the `/reolink_talk/` resources exist.
- *No video in the LAN card*: check that the card points to the doorbell's camera and reload the page. If the fast video cannot connect, the card switches to the normal video by itself.

## Reporting a problem or giving feedback

- **Something does not work?** [Open an issue](https://github.com/blancofran/ha-reolink-doorbell-talk/issues/new/choose) and choose *Bug report*. The form asks for what is needed: integration and Home Assistant versions, doorbell model and firmware, which card, where you use it, and what happened.
- **Attach the diagnostics.** *Settings → Devices & services → Reolink Doorbell Talk → ⋮ → Download diagnostics*, then drag the file into the issue. Passwords, usernames, addresses and serial numbers are hidden. For card problems, also copy the browser console lines that start with `[reolink-talk]` (turn on `show_info: true` in the card to see the transport and delay on the video).
- **Questions, ideas, "does it work with my doorbell?"** Use [Discussions](https://github.com/blancofran/ha-reolink-doorbell-talk/discussions). Telling us that it works with your model is very useful too: it is only tested with the Reolink Video Doorbell PoE.
- **Security problems:** see [SECURITY.md](SECURITY.md) and do not open a public issue.

## Contributing

Want to help with the code or the translations? See [CONTRIBUTING.md](CONTRIBUTING.md).

## Third-party software

The card bundles hls.js (Apache-2.0). See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## License

MIT
