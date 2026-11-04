# Reolink Doorbell Talk

Vídeo, sonido y **voz bidireccional** con un timbre Reolink desde Home Assistant, en un único paquete (integración + tarjetas). Funciona en casa y fuera de casa **sin abrir puertos, sin VPN y sin servicios externos**: todo viaja por la conexión normal de Home Assistant.

> **Estado: beta (0.3.11).** Funciona en las pruebas del autor con un único modelo (Reolink Video Doorbell PoE), pero puede haber errores y cambios entre versiones. Si algo falla, abre una *issue* con los diagnósticos de la integración (con los datos sensibles censurados).

[English version](README.md)

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
4. Las tarjetas se registran solas. Añádelas al panel (el identificador de la cámara depende del nombre de tu timbre y del idioma; búscalo en *Ajustes → Dispositivos y servicios*):

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

## Estado del timbre

Cada minuto la integración comprueba que el timbre responde. Si no responde (apagado, sin red, cable desconectado), las dos cámaras pasan a *no disponible* y las tarjetas muestran "El timbre no responde" en lugar de quedarse cargando; cuando vuelve, el vídeo se reanuda solo.

## Opciones de la integración

- **Calidad del vídeo**: ligera (menos datos, recomendada fuera de casa) o alta.
- **Mantener el vídeo preparado**: el vídeo aparece casi al instante, a cambio de una conexión permanente y ligera con el timbre.

También puedes **reconfigurar** (cambiar IP o credenciales) y **reautenticar** (si cambia la contraseña) desde la propia integración, y descargar **diagnósticos** con los datos sensibles censurados.

## Opciones de las tarjetas

Ambas tarjetas tienen editor visual (añade la tarjeta desde el selector de tarjetas, o edítala y desactiva *Mostrar editor de código*). Las opciones en YAML:

`entity` (obligatoria), `title`, `mode` (`toggle` o `hold`, mantener para hablar; `hold_to_talk: true` equivale a `mode: hold` y es lo que escribe el editor visual), `max_seconds` (90), `idle_seconds` (45), `warn_seconds` (10), `timeout` (12), `autoplay` (true), `show_info` (false: muestra en el vídeo el transporte y el retraso, útil para diagnosticar), `view_fallback` (true: la tarjeta LAN cae a HLS si WebRTC no está disponible), `max_width` (460), `view_timeout` (6), `hls_url` (por defecto se usa la copia incluida de hls.js).

## Cómo funciona

- **Vídeo y sonido**: el timbre ofrece un flujo FLV por HTTP. Home Assistant lo convierte a HLS (`stream`) y la tarjeta lo reproduce con hls.js (incluido). En el modo LAN se usa WebRTC con el go2rtc integrado de Home Assistant.
- **Voz**: micrófono del navegador → AudioWorklet (8 kHz, G.711 µ-law) → WebSocket de Home Assistant → cliente RTSP con *backchannel* ONVIF → timbre. Un solo dispositivo puede hablar a la vez; la sesión se cierra por tiempo máximo, por inactividad o al pasar la app a segundo plano.

## Limitaciones conocidas

- El HLS tiene un retraso mínimo de unos 3 s (viene de cómo Home Assistant segmenta el vídeo). Para menos retraso en casa usa la tarjeta LAN.
- **Safari**: el go2rtc integrado de Home Assistant solo admite WebRTC por TCP, que Safari en el navegador puede no soportar; en ese caso la tarjeta LAN **cae sola a HLS**. En las apps Companion de iOS y de Android, las tarjetas funcionan en las pruebas del autor.
- **WebRTC Camera (AlexxIT) instalado a la vez**: en una instalación se observó que la cámara WebRTC de esta integración no ofrecía WebRTC mientras WebRTC Camera estaba activo; la tarjeta LAN lo detecta y usa HLS. Si quieres WebRTC, prueba a desactivar WebRTC Camera.
- Se necesita HTTPS para el micrófono.
- La contraseña del timbre se guarda solo en la configuración de Home Assistant, no en archivos del paquete. Está en texto plano en `/config/.storage/core.config_entries` y por tanto también en las copias de seguridad: **cifra tus copias**. Se recomienda crear en el timbre un usuario propio para Home Assistant en vez de usar el administrador.
- Cualquier usuario de Home Assistant que pueda abrir el panel puede hablar por el timbre.
- Si añades otra vez un timbre ya configurado, se actualizan su IP, usuario y contraseña.

## Problemas frecuentes

- *"No se pudo abrir el canal de voz"*: otro dispositivo está hablando, o el timbre no acepta una segunda sesión de voz. Reintenta.
- *"Error de configuración"* en la tarjeta: recarga con Ctrl+Shift+R; comprueba en *Ajustes → Paneles → Recursos* que existen los recursos de `/reolink_talk/`.
- *Sin vídeo en el modo LAN*: comprueba que la entidad es la del timbre y que el go2rtc integrado de Home Assistant está en marcha; recarga la tarjeta.
