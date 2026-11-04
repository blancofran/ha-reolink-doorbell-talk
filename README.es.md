# Reolink Doorbell Talk

Vídeo, sonido y **voz bidireccional** con un timbre Reolink desde Home Assistant, en un único paquete (integración + tarjetas). Funciona en casa y fuera de casa **sin abrir puertos, sin VPN y sin servicios externos**: todo viaja por la conexión normal de Home Assistant.

> **Estado: beta (0.5.1).** Funciona en las pruebas del autor con un único modelo (Reolink Video Doorbell PoE), pero puede haber errores y cambios entre versiones. Si algo falla, abre una *issue* con los diagnósticos de la integración (con los datos sensibles censurados).

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
- **Solo los administradores pueden hablar**: los demás usuarios siguen viendo el vídeo pero no pueden usar el botón de hablar (desactivado por defecto).

También puedes **reconfigurar** (cambiar IP o credenciales) y **reautenticar** (si cambia la contraseña) desde la propia integración, y descargar **diagnósticos** con los datos sensibles censurados.

## Opciones de las tarjetas

Ambas tarjetas tienen editor visual (añade la tarjeta desde el selector de tarjetas, o edítala y desactiva *Mostrar editor de código*). Las opciones en YAML:

| Opción | Por defecto | Qué hace |
|---|---|---|
| `entity` | obligatoria | La cámara del timbre de esta integración |
| `title` | «Timbre» | Título de la tarjeta |
| `hold_to_talk` | `false` | `true`: hablas solo mientras mantienes pulsado el botón. Si no, tocas para empezar y tocas para terminar |
| `autoplay` | `true` | Inicia el vídeo al aparecer la tarjeta |
| `aspect_ratio` | `4:3` | Forma del vídeo, por ejemplo `16:9` |
| `crop_video` | `false` | `true`: llena el recuadro recortando los bordes, en vez de mostrar la imagen entera |
| `max_width` | sin límite | Ancho máximo de la tarjeta, en píxeles |
| `show_info` | `false` | Muestra el retraso sobre el vídeo; útil al reportar un problema |
| `view_fallback` | `true` | Solo tarjeta LAN: cambia al vídeo normal si el vídeo rápido no conecta |
| `max_seconds` | `90` | Duración máxima de una conversación |
| `idle_seconds` | `45` | El micrófono se cierra tras estos segundos de silencio |
| `warn_seconds` | `10` | Aviso estos segundos antes de que se cierre el micrófono |
| `timeout` | `12` | Segundos de espera a que el timbre responda al empezar a hablar |

Avanzado: `view_timeout` (segundos de espera del vídeo rápido, 6), `hls_url` (usar tu propia copia de hls.js en vez de la incluida) y `mode: hold` (equivale a `hold_to_talk: true`).

## Cambiar el tamaño

En los paneles de secciones las tarjetas se pueden redimensionar libremente en modo edición (arrastrando los bordes o con la pestaña *Diseño*): la tarjeta llena el hueco que le des, en ancho y en alto, y el vídeo se adapta. Usa `aspect_ratio` para igualar la forma de tus otras cámaras, `crop_video` para llenar el recuadro sin franjas negras y `max_width` si sí quieres limitar el ancho.

## Compatibilidad

Dispositivos probados. Los reportes los envían los usuarios; el autor solo tiene el primero.

| Dispositivo | Vídeo + sonido | Voz | Reportado por |
|---|---|---|---|
| Reolink Video Doorbell PoE | Funciona | Funciona | autor |

**¿Funciona con tu timbre o cámara?** Cuéntanos con un [reporte de compatibilidad](https://github.com/blancofran/ha-reolink-doorbell-talk/issues/new?template=compatibility_report.yml), tanto si funciona como si no. [Todos los reportes](https://github.com/blancofran/ha-reolink-doorbell-talk/issues?q=label%3Acompatibility) son públicos. Otras marcas aún no están soportadas: la dirección del vídeo es propia de Reolink, aunque la voz usa el *backchannel* estándar de ONVIF.

## Limitaciones conocidas

- La tarjeta principal tiene un retraso de unos 3 segundos. Para menos retraso en casa, usa la tarjeta LAN.
- En el navegador **Safari** la tarjeta LAN puede no mostrar vídeo; entonces cambia sola al vídeo de la tarjeta principal. Las dos tarjetas funcionan en las apps de Home Assistant para iOS y Android.
- Si también tienes instalado el complemento **WebRTC Camera** (AlexxIT), la tarjeta LAN puede volver al vídeo normal. Desactiva ese complemento si quieres el menor retraso.
- Para hablar necesitas abrir Home Assistant por **HTTPS**.
- La contraseña del timbre se guarda dentro de Home Assistant, nunca en los archivos de este paquete, pero queda en texto plano en la configuración de Home Assistant y por tanto también en tus copias de seguridad: **cifra tus copias**. Es mejor crear un usuario aparte del timbre para Home Assistant que usar el de administrador.
- Por defecto cualquiera que pueda abrir el panel puede hablar por el timbre. Activa *Solo los administradores pueden hablar* en las opciones de la integración para restringirlo.
- Añadir un timbre que ya está configurado actualiza su dirección, usuario y contraseña.

## Problemas frecuentes

- *"No se pudo abrir el canal de voz"*: otro dispositivo está hablando, o el timbre no acepta una segunda sesión de voz. Reintenta.
- *"Error de configuración"* en la tarjeta: recarga con Ctrl+Shift+R; comprueba en *Ajustes → Paneles → Recursos* que existen los recursos de `/reolink_talk/`.
- *Sin vídeo en la tarjeta LAN*: comprueba que la tarjeta apunta a la cámara del timbre y recarga la página. Si el vídeo rápido no conecta, la tarjeta cambia sola al vídeo normal.

## Reportar un problema o dar tu opinión

- **¿Algo no funciona?** [Abre una issue](https://github.com/blancofran/ha-reolink-doorbell-talk/issues/new/choose) y elige *Bug report*. El formulario pide lo necesario: versiones de la integración y de Home Assistant, modelo y firmware del timbre, qué tarjeta, dónde la usas y qué pasó (está en inglés).
- **Adjunta los diagnósticos.** *Ajustes → Dispositivos y servicios → Reolink Doorbell Talk → ⋮ → Descargar diagnósticos*, y arrastra el archivo a la issue. Contraseñas, usuarios, direcciones y números de serie salen ocultos. Si es un problema de la tarjeta, copia también las líneas de la consola del navegador que empiezan por `[reolink-talk]` (activa `show_info: true` en la tarjeta para ver el transporte y el retraso sobre el vídeo).
- **Preguntas, ideas, «¿funciona con mi timbre?»**: usa [Discussions](https://github.com/blancofran/ha-reolink-doorbell-talk/discussions). Contar que funciona con tu modelo también es muy útil: solo está probado con el Reolink Video Doorbell PoE.
- **Problemas de seguridad:** mira [SECURITY.md](SECURITY.md) y no abras una issue pública.

## Contribuir

¿Quieres ayudar con el código o las traducciones? Mira [CONTRIBUTING.md](CONTRIBUTING.md) (en inglés).

## Software de terceros

La tarjeta incluye hls.js (Apache-2.0). Ver [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## Licencia

MIT
