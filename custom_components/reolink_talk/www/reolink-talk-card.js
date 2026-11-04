// reolink-talk-card: doorbell video and sound (Home Assistant HLS, over HTTPS) and a talk button
// (browser microphone -> Home Assistant WebSocket -> doorbell). It works the same at home and away,
// in any browser, without WebRTC, go2rtc or open ports.
// Config: entity (the integration's camera), view_transport (hls | webrtc), title, mode (toggle|hold), max_seconds, idle_seconds,
// warn_seconds, timeout, autoplay, show_info (show transport and delay), view_fallback (false: do not fall back to HLS when
// WebRTC fails), max_width, hls_url. (view_entity is accepted as an alias of entity.)
const RT_TEXT = {
  es: {
    talk: 'Hablar al timbre', talking: 'Hablando… toca para terminar', hold: 'Mantén presionado para hablar',
    holdOn: 'Hablando… suelta para terminar', connecting: 'Conectando con el timbre…', error: 'No se pudo hablar',
    sound: 'Activar sonido', mute: 'Silenciar', noMic: 'Sin permiso de micrófono en este dispositivo',
    needHttps: 'El micrófono necesita una dirección HTTPS', lost: 'Se perdió la conexión con el timbre',
    timeoutMsg: 'El timbre no respondió a tiempo', bg: 'Micrófono cerrado: la app pasó a segundo plano',
    maxTime: 'Micrófono cerrado: se acabó el tiempo', idle: 'Micrófono cerrado por inactividad',
    videoErr: 'No se pudo cargar el video', closeIn: (s) => `Se cerrará en ${s} s · toca la pantalla para seguir`,
    busy: 'Otro dispositivo está hablando con el timbre', talkFail: 'No se pudo abrir el canal de voz',
    rtcErr: 'WebRTC no conectó (solo funciona en la red local)',
    offline: 'El timbre no responde', title: 'Timbre', titleLan: 'Timbre (LAN)',
  },
  en: {
    talk: 'Talk to the doorbell', talking: 'Talking… tap to stop', hold: 'Hold to talk', holdOn: 'Talking… release to stop',
    connecting: 'Connecting to the doorbell…', error: 'Could not talk', sound: 'Turn sound on', mute: 'Mute',
    noMic: 'No microphone permission on this device', needHttps: 'The microphone needs an HTTPS address',
    lost: 'Connection to the doorbell lost', timeoutMsg: 'The doorbell did not answer in time',
    bg: 'Microphone closed: app went to background', maxTime: 'Microphone closed: time is up',
    idle: 'Microphone closed due to inactivity', videoErr: 'Could not load the video',
    closeIn: (s) => `Closing in ${s} s · tap the screen to keep going`,
    busy: 'Another device is already talking to the doorbell', talkFail: 'Could not open the voice channel',
    rtcErr: 'WebRTC could not connect (it only works on the local network)',
    offline: 'The doorbell is not responding', title: 'Doorbell', titleLan: 'Doorbell (LAN)',
  },
};

// hls.js is needed in almost every browser (old iPhone Safari plays HLS without it).
// The copy bundled in the package is used; if it is missing, the CDN is tried.
const HLS_LOCAL_URL = new URL('hls.light.min.js', import.meta.url).href;
const HLS_CDN_URL = 'https://cdnjs.cloudflare.com/ajax/libs/hls.js/1.5.8/hls.light.min.js';
let _hlsLoader = null;
function _loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src;
    s.onload = () => (window.Hls ? resolve(window.Hls) : reject(new Error('hls.js')));
    s.onerror = () => { s.remove(); reject(new Error('hls.js')); };
    document.head.appendChild(s);
  });
}
function loadHls(url) {
  if (window.Hls) return Promise.resolve(window.Hls);
  if (!_hlsLoader) {
    const urls = url ? [url] : [HLS_LOCAL_URL, HLS_CDN_URL];
    _hlsLoader = urls.reduce((p, u) => p.catch(() => _loadScript(u)), Promise.reject(new Error('start')))
      .catch((e) => { _hlsLoader = null; throw e; });
  }
  return _hlsLoader;
}

// Texts of the visual editor (the form Home Assistant draws from getConfigForm).
const RT_EDITOR = {
  es: {
    entity: 'Cámara del timbre', title: 'Título', mode: 'Botón de hablar', autoplay: 'Iniciar el vídeo automáticamente',
    show_info: 'Mostrar el transporte y el retraso en el vídeo', view_fallback: 'Usar HLS si WebRTC no funciona',
    advanced: 'Opciones avanzadas', max_seconds: 'Duración máxima de la conversación (s)', idle_seconds: 'Cierre por inactividad (s)',
    warn_seconds: 'Aviso antes de cerrar (s)', timeout: 'Espera máxima de conexión (s)', max_width: 'Ancho máximo (px)',
    toggle: 'Tocar para empezar y para terminar', hold: 'Mantener pulsado para hablar',
    entity_h: 'La cámara «Ver y escuchar» creada por la integración.',
    title_h: 'Si lo dejas vacío se usa «Timbre».',
  },
  en: {
    entity: 'Doorbell camera', title: 'Title', mode: 'Talk button', autoplay: 'Start the video automatically',
    show_info: 'Show the transport and delay on the video', view_fallback: 'Fall back to HLS if WebRTC does not work',
    advanced: 'Advanced options', max_seconds: 'Maximum talk time (s)', idle_seconds: 'Close when idle (s)',
    warn_seconds: 'Warning before closing (s)', timeout: 'Connection timeout (s)', max_width: 'Maximum width (px)',
    toggle: 'Tap to start and to stop', hold: 'Hold to talk',
    entity_h: 'The "View and listen" camera created by the integration.',
    title_h: 'If empty, "Doorbell" is used.',
  },
};

class ReolinkTalkCard extends HTMLElement {
  static isLan = false; // the LAN subclass sets it to true (shows the fallback option in the editor)

  setConfig(config) {
    const entity = config && (config.entity || config.view_entity);
    if (!entity) throw new Error('reolink-talk-card: define entity');
    this._c = Object.assign({
      title: null, mode: 'toggle', timeout: 12, max_seconds: 90, warn_seconds: 10, idle_seconds: 45,
      autoplay: true, show_info: false, view_fallback: true, max_width: 460, hls_url: null, view_transport: 'hls', view_timeout: 6, webrtc_entity: null,
    }, config, { entity });
    if (!this.shadowRoot) this._build();
    this._updateTitle();
    if (this._c.show_info) this.setAttribute('data-info', ''); else this.removeAttribute('data-info');
    this._set(this._state || 'off');
  }

  // The title the user set, or a default in the Home Assistant language.
  _updateTitle() {
    const el = this.shadowRoot && this.shadowRoot.getElementById('ttl');
    if (el && this._c) el.textContent = this._c.title || this._t(this._lan ? 'titleLan' : 'title');
  }

  // The camera is "unavailable" while the doorbell does not answer.
  _isOffline() {
    const st = this._hass && this._c && this._hass.states && this._hass.states[this._c.entity];
    return !!st && st.state === 'unavailable';
  }

  // Repaints every visible text once the language is known (the texts are first drawn before hass arrives).
  _refreshTexts() {
    if (!this.shadowRoot || !this._c) return;
    this._set(this._state || 'off');
    this._refreshSound();
    this._updateTitle();
  }

  set hass(hass) {
    this._hass = hass;
    const lang = (hass && hass.language) || 'en';
    if (lang !== this._lang) { this._lang = lang; this._refreshTexts(); }
    this._updateTitle();
    const off = this._isOffline();
    if (off !== !!this._offline) {
      this._offline = off;
      if (off) { this._stopView(); this._videoMsg(this._t('offline')); }
      else { this._videoMsg(''); this._viewTried = false; }
    }
    if (this._c && this._c.autoplay && !this._viewTried && !off && this.isConnected) {
      this._viewTried = true;
      this._startView();
    }
  }

  // Starting config when the card is added from the card picker: the first camera of this integration.
  static getStubConfig(hass) {
    const ents = (hass && hass.entities) || {};
    const found = Object.keys(ents).find((id) => id.startsWith('camera.') && ents[id].platform === 'reolink_talk' && ents[id].translation_key === 'view');
    return { entity: found || 'camera.doorbell_view_and_listen' };
  }

  // Visual editor: Home Assistant draws this form (no editor element of our own is needed).
  static getConfigForm() {
    const root = document.querySelector('home-assistant');
    const lang = ((root && root.hass && root.hass.language) || 'en').slice(0, 2);
    const L = RT_EDITOR[lang] || RT_EDITOR.en;
    // `default` makes the form show the value the card really uses when the option is not in the YAML.
    const num = (name, min, max, def) => ({ name, default: def, selector: { number: { min, max, mode: 'box' } } });
    const schema = [
      { name: 'entity', required: true, selector: { entity: { filter: { domain: 'camera', integration: 'reolink_talk' } } } },
      { name: 'title', selector: { text: {} } },
      { name: 'mode', default: 'toggle', selector: { select: { mode: 'dropdown', options: [{ value: 'toggle', label: L.toggle }, { value: 'hold', label: L.hold }] } } },
      { name: 'autoplay', default: true, selector: { boolean: {} } },
      { name: 'show_info', default: false, selector: { boolean: {} } },
    ];
    if (this.isLan) schema.push({ name: 'view_fallback', default: true, selector: { boolean: {} } });
    schema.push({
      type: 'expandable', name: 'advanced', title: L.advanced, flatten: true,
      schema: [num('max_seconds', 5, 600, 90), num('idle_seconds', 5, 600, 45), num('warn_seconds', 1, 60, 10), num('timeout', 3, 60, 12), num('max_width', 240, 1200, 460)],
    });
    return {
      schema,
      computeLabel: (s) => L[s.name] || s.name,
      computeHelper: (s) => L[s.name + '_h'] || '',
    };
  }

  getCardSize() { return 5; }
  getGridOptions() { return { columns: 12, rows: 'auto', min_columns: 6 }; }

  _t(k, ...a) {
    const lang = ((this._hass && this._hass.language) || 'en').slice(0, 2);
    const v = (RT_TEXT[lang] || RT_TEXT.en)[k];
    return typeof v === 'function' ? v(...a) : v;
  }

  _log(msg) {
    console.info('[reolink-talk] +' + Math.round(performance.now() - (this._t00 || performance.now())) + ' ms ' + msg);
  }

  connectedCallback() {
    this._onVis = () => {
      if (document.hidden && this._talk) this._auto(this._t('bg'));
      if (document.hidden) this._stopView();
      else if (this._c && this._c.autoplay) { this._viewTried = true; this._startView(); }
    };
    this._onHide = () => { if (this._talk) this._auto(this._t('bg')); this._stopView(); };
    document.addEventListener('visibilitychange', this._onVis);
    window.addEventListener('pagehide', this._onHide);
    if (this._hass && this._c && this._c.autoplay && !this._viewTried) { this._viewTried = true; this._startView(); }
  }

  disconnectedCallback() {
    if (this._talk) this._stop();
    this._stopView();
    this._viewTried = false;
    clearTimeout(this._msgT);
    document.removeEventListener('visibilitychange', this._onVis);
    window.removeEventListener('pagehide', this._onHide);
  }

  // ---------- UI ----------
  _build() {
    const r = this.attachShadow({ mode: 'open' });
    r.innerHTML = `
      <style>
        :host { display: block; }
        .card { display: flex; flex-direction: column; gap: 10px; padding: 14px; color: #fff; box-sizing: border-box;
          background: linear-gradient(160deg, #071d4d 0%, #0a3a94 100%); border-radius: 22px;
          border: 1px solid rgba(45,226,255,0.35); box-shadow: 0 0 24px rgba(45,226,255,0.18);
          margin: 0 auto; width: 100%; max-width: ${this._c.max_width}px;
          font-family: -apple-system, BlinkMacSystemFont, Roboto, "Segoe UI", sans-serif; }
        .head { display: flex; align-items: center; gap: 10px; }
        .head ha-icon { --mdc-icon-size: 24px; color: #2de2ff; }
        .title { font-size: 18px; font-weight: 600; }
        .vwrap { position: relative; border-radius: 14px; overflow: hidden; background: #000; aspect-ratio: 4 / 3; }
        video { width: 100%; height: 100%; object-fit: contain; display: block; }
        #snd { position: absolute; right: 8px; bottom: 8px; border: 0; border-radius: 999px; padding: 6px 12px;
          background: rgba(0,0,0,.55); color: #fff; font-size: 13px; cursor: pointer; display: flex; gap: 6px; align-items: center; }
        #snd ha-icon { --mdc-icon-size: 18px; }
        #tr { position: absolute; left: 8px; bottom: 8px; font-size: 11px; padding: 2px 8px; border-radius: 999px;
          background: rgba(0,0,0,.55); color: #9fe9ff; pointer-events: none; }
        #tr:empty { display: none; }
        :host(:not([data-info])) #tr { display: none; }
        #vmsg { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
          text-align: center; padding: 12px; font-size: 14px; color: rgba(255,255,255,.85); pointer-events: none; }
        #b { width: 100%; min-height: 60px; border: 0; border-radius: 14px; display: flex; align-items: center; justify-content: center;
          gap: 10px; padding: 10px 16px; font: 600 18px/1.2 -apple-system, BlinkMacSystemFont, Roboto, "Segoe UI", sans-serif;
          color: #fff; cursor: pointer; user-select: none; -webkit-user-select: none; -webkit-tap-highlight-color: transparent;
          touch-action: manipulation; transition: background-color .2s ease; }
        #b.off { background: #2f6fe4; } #b.connecting { background: #b7791f; }
        #b.on { background: #d93025; animation: pulse 1.4s ease-in-out infinite; } #b.error { background: #5f6673; }
        @keyframes pulse { 0%,100% { box-shadow: 0 0 0 0 rgba(217,48,37,.55); } 50% { box-shadow: 0 0 0 10px rgba(217,48,37,0); } }
        #b ha-icon { --mdc-icon-size: 28px; }
        .msg { min-height: 16px; font-size: 13px; text-align: center; color: rgba(255,255,255,0.75); }
      </style>
      <div class="card">
        <div class="head"><ha-icon icon="mdi:doorbell-video"></ha-icon><div class="title" id="ttl"></div></div>
        <div class="vwrap"><video id="v" autoplay playsinline muted></video><div id="vmsg"></div><div id="tr"></div>
          <button id="snd"><ha-icon id="sndi" icon="mdi:volume-off"></ha-icon><span id="sndt"></span></button></div>
        <button id="b" class="off"><ha-icon id="i" icon="mdi:microphone"></ha-icon><span id="t"></span></button>
        <div class="msg" id="m"></div>
      </div>`;
    this._updateTitle();
    this._video = r.getElementById('v');
    this._video.addEventListener('playing', () => { this._log('video: playing'); this._onPlaying(); });
    this._video.addEventListener('error', () => {
      const er = this._video.error;
      this._log('video: error ' + (er ? er.code + ' ' + er.message : ''));
      if (this._hls) this._videoFailed(er && er.message ? er.message : 'video error');
    });
    r.getElementById('snd').addEventListener('click', () => {
      this._video.muted = !this._video.muted;
      this._refreshSound();
      if (!this._video.muted) { const p = this._video.play(); if (p && p.catch) p.catch(() => {}); }
    });
    const b = r.getElementById('b');
    if (this._c.mode === 'hold') {
      b.addEventListener('pointerdown', (e) => { e.preventDefault(); this._start(); });
      for (const ev of ['pointerup', 'pointercancel', 'pointerleave']) b.addEventListener(ev, () => { if (this._talk) this._stop(); });
      b.addEventListener('contextmenu', (e) => e.preventDefault());
    } else {
      b.addEventListener('click', () => (this._talk ? this._stop() : this._start()));
    }
    this._refreshSound();
  }

  _refreshSound() {
    const r = this.shadowRoot; if (!r || !this._video) return;
    const off = this._video.muted;
    r.getElementById('sndi').setAttribute('icon', off ? 'mdi:volume-off' : 'mdi:volume-high');
    r.getElementById('sndt').textContent = off ? this._t('sound') : this._t('mute');
  }

  _set(state, msg) {
    this._state = state;
    const r = this.shadowRoot; if (!r) return;
    const c = this._c, hold = c.mode === 'hold';
    const labels = {
      off: [hold ? this._t('hold') : this._t('talk'), 'mdi:microphone'],
      connecting: [this._t('connecting'), 'mdi:phone-in-talk'],
      on: [hold ? this._t('holdOn') : this._t('talking'), 'mdi:microphone'],
      error: [this._t('error'), 'mdi:microphone-off'],
    };
    const [label, icon] = labels[state] || labels.off;
    r.getElementById('b').className = state;
    r.getElementById('t').textContent = label;
    r.getElementById('i').setAttribute('icon', icon);
    r.getElementById('m').textContent = msg || '';
  }

  _videoMsg(text) {
    const el = this.shadowRoot && this.shadowRoot.getElementById('vmsg');
    if (el) el.textContent = text || '';
  }

  _setTransport(t) {
    this._tBase = t || '';
    const el = this.shadowRoot && this.shadowRoot.getElementById('tr');
    if (el) el.textContent = t || '';
  }

  // When the first frame arrives, show how long it took since the video was requested.
  _onPlaying() {
    clearTimeout(this._hlsWatch);
    this._videoMsg('');
    if (!this._tView || !this._tBase) return;
    const secs = ((performance.now() - this._tView) / 1000).toFixed(1);
    this._tView = null;
    this._retries = 0;
    const el = this.shadowRoot && this.shadowRoot.getElementById('tr');
    if (el) el.textContent = this._tBase + ' · ' + secs + ' s';
    console.info('[reolink-talk] primer fotograma: ' + secs + ' s');
  }

  // ---------- video: Home Assistant HLS (camera/stream) ----------
  async _startView() {
    if (this._hls || this._hlsBusy || this._rtc || this._rtcBusy || !this._hass) return;
    if (this._isOffline()) { this._videoMsg(this._t('offline')); return; }
    this._tView = performance.now();
    this._t00 = this._tView;
    this._log('start: ' + this._c.view_transport);
    if (this._c.view_transport === 'webrtc') this._startViewWebrtc();
    else this._startViewHls();
  }

  // Finds another camera of the same device by its translation_key (e.g. 'webrtc').
  _sibling(entityId, key) {
    const ents = (this._hass && this._hass.entities) || {};
    const dev = ents[entityId] && ents[entityId].device_id;
    if (!dev) return null;
    for (const [id, e] of Object.entries(ents)) {
      if (e.device_id === dev && e.translation_key === key) return id;
    }
    return null;
  }

  // ---------- video: WebRTC (local network only; the fastest) ----------
  // If WebRTC is not available or does not connect, the card falls back to HLS by itself (view_fallback: false disables it).
  async _startViewWebrtc() {
    if (this._rtc || this._rtcBusy || !this._hass) return;
    const ent = this._c.webrtc_entity || this._sibling(this._c.entity, 'webrtc');
    if (!ent) { this._fallbackHls('WebRTC camera not found'); return; }
    this._rtcBusy = true;
    this._videoMsg('');
    try {
      let caps = null;
      try { caps = await this._hass.callWS({ type: 'camera/capabilities', entity_id: ent }); } catch (e) { /* try anyway */ }
      if (caps && Array.isArray(caps.frontend_stream_types) && !caps.frontend_stream_types.includes('web_rtc')) {
        this._rtcBusy = false;
        this._fallbackHls('the camera does not offer WebRTC');
        return;
      }
      const s = await this._negotiate(ent);
      this._rtc = s;
      this._log('WebRTC negotiating');
      s.onError = (m) => this._rtcFailed(m || 'error');
      s.pc.onconnectionstatechange = () => {
        const st = s.pc.connectionState;
        this._log('WebRTC state=' + st);
        if (st === 'connected') { clearTimeout(s.fbT); this._setTransport('WebRTC'); }
        else if (['failed', 'closed', 'disconnected'].includes(st) && this._rtc === s) this._rtcFailed(st);
      };
      s.fbT = setTimeout(() => { if (this._rtc === s && s.pc.connectionState !== 'connected') this._rtcFailed('timeout'); }, this._c.view_timeout * 1000);
    } catch (e) { this._rtcBusy = false; this._rtcFailed(e && e.message ? e.message : 'error'); return; }
    this._rtcBusy = false;
  }

  _rtcFailed(why) {
    this._log('WebRTC failed: ' + why);
    this._stopRtc();
    this._fallbackHls(why);
  }

  _fallbackHls(why) {
    this._log('WebRTC not available (' + why + ')');
    if (this._c.view_fallback === false) { this._videoMsg(this._t('rtcErr') + ' (' + why + ')'); return; }
    this._tView = performance.now();
    this._startViewHls();
  }

  async _negotiate(entityId) {
    const hass = this._hass;
    let iceServers = [], upfront = false;
    try {
      const cfg = await hass.callWS({ type: 'camera/webrtc/get_client_config', entity_id: entityId });
      iceServers = (cfg.configuration && cfg.configuration.iceServers) || [];
      upfront = !!cfg.getCandidatesUpfront;
    } catch (e) { /* no configuration: defaults are used */ }
    const pc = new RTCPeerConnection({ iceServers });
    const s = { pc, sessionId: null, pending: [], unsub: null, closed: false };
    pc.addTransceiver('video', { direction: 'recvonly' });
    pc.addTransceiver('audio', { direction: 'recvonly' });
    const ms = new MediaStream();
    pc.ontrack = (ev) => { ms.addTrack(ev.track); if (this._video.srcObject !== ms) this._video.srcObject = ms; };
    const sendCand = (c) => hass.callWS({ type: 'camera/webrtc/candidate', entity_id: entityId, session_id: s.sessionId, candidate: c }).catch(() => {});
    pc.onicecandidate = (ev) => {
      if (!ev.candidate || upfront) return;
      const c = ev.candidate.toJSON();
      if (s.sessionId) sendCand(c); else s.pending.push(c);
    };
    await pc.setLocalDescription(await pc.createOffer());
    if (upfront && pc.iceGatheringState !== 'complete') {
      await new Promise((res) => {
        const done = () => { if (pc.iceGatheringState === 'complete') res(); };
        pc.addEventListener('icegatheringstatechange', done);
        setTimeout(res, 2500);
      });
    }
    s.unsub = await hass.connection.subscribeMessage((ev) => {
      if (s.closed) return;
      if (ev.type === 'session') {
        s.sessionId = ev.session_id;
        s.pending.splice(0).forEach(sendCand);
      } else if (ev.type === 'answer') {
        pc.setRemoteDescription({ type: 'answer', sdp: ev.answer }).catch((e) => s.onError && s.onError(String(e)));
      } else if (ev.type === 'candidate') {
        pc.addIceCandidate(ev.candidate).catch(() => {});
      } else if (ev.type === 'error') {
        s.onError && s.onError(ev.message || ev.code);
      }
    }, { type: 'camera/webrtc/offer', entity_id: entityId, offer: pc.localDescription.sdp });
    return s;
  }

  _stopRtc() {
    const s = this._rtc; this._rtc = null;
    if (!s) return;
    clearTimeout(s.fbT);
    s.closed = true;
    try { if (s.unsub) s.unsub(); } catch (e) {}
    try { s.pc.close(); } catch (e) {}
    if (this._video) this._video.srcObject = null;
  }

  async _startViewHls() {
    if (this._hls || this._hlsBusy || !this._hass) return;
    this._hlsBusy = true;
    this._videoMsg('');
    try {
      const res = await this._hass.callWS({ type: 'camera/stream', entity_id: this._c.entity, format: 'hls' });
      this._log('HLS URL ready ' + res.url);
      const mse = !!(window.MediaSource || window.ManagedMediaSource);
      const native = !mse && !!this._video.canPlayType('application/vnd.apple.mpegurl');
      const video = this._video;
      video.srcObject = null;
      if (native) {
        video.src = res.url;
        this._hls = { kind: 'native' };
      } else {
        const Hls = await loadHls(this._c.hls_url);
        if (!Hls.isSupported()) throw new Error('hls not supported');
        const h = new Hls({ lowLatencyMode: true, liveSyncDuration: 2, liveMaxLatencyDuration: 6, maxLiveSyncPlaybackRate: 1.5, backBufferLength: 10 });
        h.on(Hls.Events.MANIFEST_PARSED, () => this._log('playlist loaded'));
        h.on(Hls.Events.ERROR, (ev, data) => {
          this._log('hls.js error: ' + (data && data.type) + ' / ' + (data && data.details) + (data && data.fatal ? ' (fatal)' : ''));
          if (data && data.fatal && this._hls && this._hls.h === h) this._videoFailed(data.details || 'error');
        });
        h.loadSource(res.url);
        h.attachMedia(video);
        this._hls = { kind: 'hlsjs', h };
        clearInterval(this._latT);
        this._latT = setInterval(() => {
          if (!this._hls || this._hls.h !== h) return clearInterval(this._latT);
          const lat = h.latency, tgt = h.targetLatency;
          if (typeof lat !== 'number' || !isFinite(lat)) return;
          const el = this.shadowRoot && this.shadowRoot.getElementById('tr');
          if (el && this._tBase) el.textContent = this._tBase + ' · delay ' + lat.toFixed(1) + ' s';
          this._log('live delay ' + lat.toFixed(1) + ' s (target ' + (typeof tgt === 'number' && isFinite(tgt) ? tgt.toFixed(1) : '?') + ' s, speed ' + h.playbackRate + ')');
        }, 3000);
      }
      const p = video.play();
      if (p && p.catch) p.catch(() => {});
      this._setTransport('HLS');
      clearTimeout(this._hlsWatch);
      this._hlsWatch = setTimeout(() => {
        if (this._hls && this._tView) { this._log('no image after 12 s'); this._videoFailed('no image'); }
      }, 12000);
    } catch (e) {
      this._log('failed to start HLS: ' + (e && e.message ? e.message : e));
      this._hlsBusy = false;
      this._videoFailed(e && e.message ? e.message : 'error');
      return;
    }
    this._hlsBusy = false;
  }

  // Shows the error and retries with a fresh URL (HLS URLs expire).
  _videoFailed(why) {
    this._stopHls();
    clearTimeout(this._hlsWatch);
    this._retries = (this._retries || 0) + 1;
    if (this._retries <= 2 && this.isConnected && !document.hidden) {
      this._videoMsg(this._t('videoErr') + ' (' + why + ') …');
      clearTimeout(this._retryT);
      this._retryT = setTimeout(() => { this._tView = performance.now(); this._startViewHls(); }, 1500);
    } else {
      this._videoMsg(this._t('videoErr') + ' (' + why + ')');
    }
  }

  _stopHls() {
    const s = this._hls; this._hls = null;
    if (!s) return;
    clearInterval(this._latT);
    try { if (s.h) s.h.destroy(); } catch (e) {}
    if (this._video) { try { this._video.removeAttribute('src'); this._video.load(); } catch (e) {} }
  }

  _stopView() {
    clearTimeout(this._retryT); clearTimeout(this._hlsWatch);
    this._retries = 0;
    this._stopHls();
    this._stopRtc();
    if (this._video) this._video.srcObject = null;
    this._setTransport('');
  }

  // ---------- talk: microphone -> Home Assistant WebSocket -> doorbell ----------
  async _start() {
    if (this._talk || !this._hass) return;
    if (this._isOffline()) { this._fail(this._t('offline')); return; }
    clearTimeout(this._errT); clearTimeout(this._msgT);
    if (this._video && this._video.muted) { this._video.muted = false; this._refreshSound(); }
    if (this._video) { const p = this._video.play(); if (p && p.catch) p.catch(() => {}); }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { this._fail(this._t('needHttps')); return; }
    this._t0 = Date.now();
    this._set('connecting');
    const token = (this._token = {});
    clearInterval(this._iv);
    this._iv = setInterval(() => {
      if (this._state === 'connecting' && (Date.now() - this._t0) / 1000 > this._c.timeout) this._fail(this._t('timeoutMsg'));
    }, 500);
    try {
      const { startWsTalk } = await import(new URL('talk-ws.js', import.meta.url).href);
      if (this._token !== token) return;
      const s = { kind: 'ws', handle: null };
      this._talk = s;
      s.handle = await startWsTalk({
        hass: this._hass,
        entityId: this._c.entity,
        onReady: () => { if (this._talk === s) { this._set('on'); this._guardsOn(); } },
        onClosed: (reason) => {
          if (this._talk !== s) return;
          const k = { idle: 'idle', max_time: 'maxTime' }[reason];
          this._auto(k ? this._t(k) : this._t('lost'));
        },
      });
      if (this._talk !== s) s.handle.stop();
    } catch (e) {
      const msg = e && e.name === 'NotAllowedError' ? this._t('noMic')
        : e && e.code === 'busy' ? this._t('busy')
        : e && e.code === 'talk_failed' ? this._t('talkFail') + ' (' + e.message + ')'
        : String((e && e.message) || e);
      this._fail(msg);
    }
  }

  _guardsOn() {
    const now = Date.now();
    this._onAt = now; this._last = now; this._deadline = now + this._c.max_seconds * 1000;
    this._act = () => {
      const t = Date.now(); this._last = t;
      if (this._deadline - t <= this._c.warn_seconds * 1000) this._deadline = t + this._c.max_seconds * 1000;
    };
    for (const ev of ['pointerdown', 'touchstart', 'click']) document.addEventListener(ev, this._act, true);
    clearInterval(this._tk);
    this._tk = setInterval(() => this._tick(), 500);
  }

  _guardsOff() {
    clearInterval(this._tk); this._tk = null;
    if (this._act) { for (const ev of ['pointerdown', 'touchstart', 'click']) document.removeEventListener(ev, this._act, true); this._act = null; }
  }

  _tick() {
    if (this._state !== 'on' || !this._talk) return;
    const now = Date.now(), c = this._c;
    const left = Math.ceil((this._deadline - now) / 1000);
    const idleLeft = c.mode === 'hold' ? 1e9 : Math.ceil((this._last + c.idle_seconds * 1000 - now) / 1000);
    if (left <= 0) { this._auto(this._t('maxTime')); return; }
    if (idleLeft <= 0) { this._auto(this._t('idle')); return; }
    const rem = Math.min(left, idleLeft), secs = Math.floor((now - this._onAt) / 1000);
    this.shadowRoot.getElementById('m').textContent = rem <= c.warn_seconds
      ? this._t('closeIn', rem) : `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`;
  }

  _teardownTalk() {
    clearInterval(this._iv); this._iv = null;
    this._guardsOff();
    const s = this._talk; this._talk = null; this._token = null;
    try { if (s && s.handle) s.handle.stop(); } catch (e) {}
  }

  _auto(reason) {
    this._teardownTalk();
    this._set('off', reason);
    clearTimeout(this._msgT);
    this._msgT = setTimeout(() => {
      const m = this.shadowRoot && this.shadowRoot.getElementById('m');
      if (m && this._state === 'off') m.textContent = '';
    }, 7000);
  }

  _stop() { this._teardownTalk(); this._set('off'); }

  _fail(msg) {
    this._teardownTalk();
    this._set('error', msg);
    clearTimeout(this._errT);
    this._errT = setTimeout(() => { if (!this._talk) this._set('off'); }, 5000);
  }
}

if (!customElements.get('reolink-talk-card')) customElements.define('reolink-talk-card', ReolinkTalkCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'reolink-talk-card', name: 'Reolink Doorbell Talk',
  description: 'Video, sound and two-way voice for a Reolink doorbell',
});
