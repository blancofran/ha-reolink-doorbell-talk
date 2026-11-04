# Reolink Doorbell Talk

Vídeo, sonido y **voz bidireccional** con un timbre Reolink desde Home Assistant, en un único paquete (integración + tarjetas). Funciona en casa y fuera de casa **sin abrir puertos, sin VPN y sin servicios externos**: todo viaja por la conexión normal de Home Assistant.

> **Estado: beta (0.3.2).** Funciona en las pruebas del autor con un único modelo (Reolink Video Doorbell PoE), pero puede haber errores y cambios entre versiones. Si algo falla, abre una *issue* con los diagnósticos de la integración (con los datos sensibles censurados).

*English version below.*

## Qué incluye

| Pieza | Para qué |
|---|---|
| Integración `reolink_talk` | Cámara con el vídeo del timbre, canal de voz hacia el timbre y registro automático de las tarjetas |
| Tarjeta `custom:reolink-talk-card` | **Casa y fuera**: vídeo por HTTPS (HLS) + botón para hablar. Retraso de unos 3 s |
| Tarjeta `custom:reolink-talk-lan-card` | **Solo en casa**: vídeo por WebRTC (menor retraso) + el mismo botón para hablar |

## Requisitos

- Home Assistant 2025.1 o superior.
- Timbre Reolink Video Doorbell (probado con el modelo PoE) con usuario y contraseña de administrador y acceso por red local.
- Para hablar: abrir Home Assistant por **HTTPS** (por ejemplo Nabu Casa, un proxy inverso o Cloudflare). Los navegadores no permiten usar el micrófono con `http://` (salvo `localhost`).

## Instalación

1. HACS → menú ⋮ → *Repositorios personalizados* → añade `https://github.com/blancofran/ha-reolink-doorbell-talk` como *Integración*.
2. Instala *Reolink Doorbell Talk* y reinicia Home Assistant.
3. *Ajustes → Dispositivos y servicios → Añadir integración → Reolink Doorbell Talk*. Indica la IP del timbre, el usuario y la contraseña.
4. Las tarjetas se registran solas. Añádelas al panel:

```yaml
type: custom:reolink-talk-card
entity: camera.timbre_ver_y_escuchar
title: Timbre
```

Solo en casa, con WebRTC (la cámara WebRTC se crea sola):

```yaml
type: custom:reolink-talk-lan-card
entity: camera.timbre_ver_y_escuchar
```

## Opciones de la integración

- **Calidad del vídeo**: ligera (menos datos, recomendada fuera de casa) o alta.
- **Mantener el vídeo preparado**: el vídeo aparece casi al instante, a cambio de una conexión permanente y ligera con el timbre.

También puedes **reconfigurar** (cambiar IP o credenciales) y **reautenticar** (si cambia la contraseña) desde la propia integración, y descargar **diagnósticos** con los datos sensibles censurados.

## Opciones de las tarjetas

`entity` (obligatoria), `title`, `mode` (`toggle` o `hold`, mantener para hablar), `max_seconds` (90), `idle_seconds` (45), `warn_seconds` (10), `timeout` (12), `autoplay` (true), `max_width` (460), `view_timeout` (6), `hls_url` (por defecto se usa la copia incluida de hls.js).

## Cómo funciona

- **Vídeo y sonido**: el timbre ofrece un flujo FLV por HTTP. Home Assistant lo convierte a HLS (`stream`) y la tarjeta lo reproduce con hls.js (incluido). En el modo LAN se usa WebRTC con el go2rtc integrado de Home Assistant.
- **Voz**: micrófono del navegador → AudioWorklet (8 kHz, G.711 µ-law) → WebSocket de Home Assistant → cliente RTSP con *backchannel* ONVIF → timbre. Un solo dispositivo puede hablar a la vez; la sesión se cierra por tiempo máximo, por inactividad o al pasar la app a segundo plano.

## Limitaciones conocidas

- El HLS tiene un retraso mínimo de unos 3 s (viene de cómo Home Assistant segmenta el vídeo). Para menos retraso en casa usa la tarjeta LAN.
- **iPhone/Safari**: el go2rtc integrado de Home Assistant solo admite WebRTC por TCP, que Safari no soporta; en iPhone usa la tarjeta HTTPS.
- Se necesita HTTPS para el micrófono.
- La contraseña del timbre se guarda solo en la configuración de Home Assistant, no en archivos del paquete.

## Problemas frecuentes

- *"No se pudo abrir el canal de voz"*: otro dispositivo está hablando, o el timbre no acepta una segunda sesión de voz. Reintenta.
- *"Error de configuración"* en la tarjeta: recarga con Ctrl+Shift+R; comprueba en *Ajustes → Paneles → Recursos* que existen los recursos de `/reolink_talk/`.
- *Sin vídeo en el modo LAN*: comprueba que la entidad es la del timbre y que el go2rtc integrado de Home Assistant está en marcha; recarga la tarjeta.

---

# English

> **Status: beta (0.3.2).** It works in the author's tests with a single model (Reolink Video Doorbell PoE), but there may be bugs and changes between versions. If something fails, open an issue and attach the integration diagnostics (sensitive data is redacted).

Video, sound and **two-way voice** with a Reolink doorbell from Home Assistant, in a single package (integration + cards). It works at home and away **without opening ports, VPNs or external services**: everything goes through Home Assistant's normal connection.

## What's inside

| Piece | Purpose |
|---|---|
| `reolink_talk` integration | Camera with the doorbell video, voice channel to the doorbell, automatic card registration |
| `custom:reolink-talk-card` | **Home and away**: HTTPS (HLS) video + talk button. About 3 s delay |
| `custom:reolink-talk-lan-card` | **Home only**: WebRTC video (lowest delay) + the same talk button |

## Requirements

- Home Assistant 2025.1 or newer.
- A Reolink Video Doorbell (tested with the PoE model), admin credentials and LAN access.
- To talk: open Home Assistant over **HTTPS**. Browsers block the microphone on plain `http://` (except `localhost`).

## Installation

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/blancofran/ha-reolink-doorbell-talk` as an *Integration*.
2. Install *Reolink Doorbell Talk* and restart Home Assistant.
3. *Settings → Devices & services → Add integration → Reolink Doorbell Talk*; enter the doorbell IP, user and password.
4. The cards register themselves. Add them to a dashboard:

```yaml
type: custom:reolink-talk-card
entity: camera.doorbell_view_and_listen
```

LAN only: `type: custom:reolink-talk-lan-card` with the same `entity` (the WebRTC camera is created automatically).

## Options

Video quality (light/high) and keep the video ready (near-instant start). The integration also supports reconfigure, re-authentication and redacted diagnostics.

## Known limitations

- HLS has a minimum delay of about 3 s; use the LAN card for less delay at home.
- **iPhone/Safari** cannot use WebRTC with Home Assistant's built-in go2rtc (TCP only): use the HTTPS card.
- HTTPS is required for the microphone.
- The doorbell password lives only in Home Assistant's config entry, never in the package files.
