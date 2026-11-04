// reolink-talk-lan-card: misma tarjeta que reolink-talk-card pero con vídeo por WebRTC (solo red local, mínimo retraso).
// La voz sigue yendo por el WebSocket de Home Assistant. Requiere activar WebRTC en las opciones de la integración.
// Para ver el timbre desde fuera de casa usa reolink-talk-card (HTTPS/HLS).
(async () => {
  await customElements.whenDefined('reolink-talk-card');
  const Base = customElements.get('reolink-talk-card');
  class ReolinkTalkLanCard extends Base {
    setConfig(config) {
      super.setConfig(Object.assign({ title: 'Timbre (LAN)' }, config, { view_transport: 'webrtc' }));
    }
  }
  if (!customElements.get('reolink-talk-lan-card')) customElements.define('reolink-talk-lan-card', ReolinkTalkLanCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: 'reolink-talk-lan-card', name: 'Reolink Doorbell Talk (LAN)',
    description: 'Timbre Reolink con vídeo WebRTC, solo red local',
  });
})();
