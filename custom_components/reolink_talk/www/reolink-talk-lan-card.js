// reolink-talk-lan-card: same card as reolink-talk-card but with WebRTC video (local network only, lowest delay).
// The voice still goes through the Home Assistant WebSocket. If WebRTC is not available the card falls back to HLS.
// To watch the doorbell away from home use reolink-talk-card (HTTPS/HLS).
(async () => {
  await customElements.whenDefined('reolink-talk-card');
  const Base = customElements.get('reolink-talk-card');
  class ReolinkTalkLanCard extends Base {
    setConfig(config) {
      this._lan = true; // default title "Doorbell (LAN)"
      super.setConfig(Object.assign({}, config, { view_transport: 'webrtc' }));
    }
  }
  if (!customElements.get('reolink-talk-lan-card')) customElements.define('reolink-talk-lan-card', ReolinkTalkLanCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: 'reolink-talk-lan-card', name: 'Reolink Doorbell Talk (LAN)',
    description: 'Reolink doorbell with WebRTC video, local network only',
  });
})();
