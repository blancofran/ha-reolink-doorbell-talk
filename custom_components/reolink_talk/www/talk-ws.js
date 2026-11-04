// talk-ws: captura el micrófono, lo convierte a G.711 mu-law (8 kHz) y lo envía a Home Assistant por la
// conexión WebSocket normal. La integración lo reenvía al timbre por RTSP. Funciona desde cualquier sitio
// desde el que se pueda abrir Home Assistant (no usa UDP ni puertos extra).
const WORKLET = `
function enc(f) {
  let s = Math.round(Math.max(-1, Math.min(1, f)) * 32767);
  const sign = s < 0 ? 0x80 : 0;
  if (s < 0) s = -s;
  if (s > 32635) s = 32635;
  s += 0x84;
  let exp = 7;
  for (let m = 0x4000; (s & m) === 0 && exp > 0; exp--, m >>= 1) {}
  const mant = (s >> (exp + 3)) & 0x0f;
  return ~(sign | (exp << 4) | mant) & 0xff;
}
class RtMulaw extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 8000;
    this.phase = 0; this.sum = 0; this.cnt = 0;
    this.out = new Uint8Array(160); this.n = 0;
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      this.sum += ch[i]; this.cnt++; this.phase += 1;
      if (this.phase >= this.ratio) {
        this.phase -= this.ratio;
        this.out[this.n++] = enc(this.sum / this.cnt);
        this.sum = 0; this.cnt = 0;
        if (this.n === 160) { this.port.postMessage(this.out.slice()); this.n = 0; }
      }
    }
    return true;
  }
}
registerProcessor('rt-mulaw', RtMulaw);
`;

export async function startWsTalk({ hass, entityId, onReady, onClosed }) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
  });
  let ctx = null, node = null, unsub = null, sessionId = null, stopped = false;

  const stop = () => {
    if (stopped) return;
    stopped = true;
    try { if (node) { node.port.onmessage = null; node.disconnect(); } } catch (e) {}
    try { stream.getTracks().forEach((t) => t.stop()); } catch (e) {}
    try { if (ctx) ctx.close(); } catch (e) {}
    try { if (unsub) unsub(); } catch (e) {}
  };

  try {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
    await ctx.resume();
    const url = URL.createObjectURL(new Blob([WORKLET], { type: 'application/javascript' }));
    try { await ctx.audioWorklet.addModule(url); } finally { URL.revokeObjectURL(url); }
    node = new AudioWorkletNode(ctx, 'rt-mulaw');
    ctx.createMediaStreamSource(stream).connect(node);
    // Conectado a la salida con volumen 0: así el navegador procesa el audio sin interrupciones (Safari lo necesita).
    const mute = ctx.createGain();
    mute.gain.value = 0;
    node.connect(mute);
    mute.connect(ctx.destination);

    let pending = [];
    node.port.onmessage = (e) => {
      if (!sessionId || stopped) return;
      pending.push(e.data);
      if (pending.length < 3) return; // 60 ms por mensaje
      const buf = new Uint8Array(pending.length * 160);
      pending.forEach((c, i) => buf.set(c, i * 160));
      pending = [];
      let bin = '';
      for (let i = 0; i < buf.length; i++) bin += String.fromCharCode(buf[i]);
      hass.connection.sendMessage({ type: 'reolink_talk/audio', session: sessionId, data: btoa(bin) });
    };

    unsub = await hass.connection.subscribeMessage((ev) => {
      if (stopped) return;
      if (ev.event === 'ready') { sessionId = ev.session; if (onReady) onReady(); }
      else if (ev.event === 'closed') { stop(); if (onClosed) onClosed(ev.reason); }
    }, { type: 'reolink_talk/talk', entity_id: entityId });
  } catch (e) {
    stop();
    throw e;
  }
  return { stop };
}
