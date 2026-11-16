// Tests of the Lovelace cards in a simulated browser (jsdom). Run: cd tests/js && npm ci && npm test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { JSDOM } from 'jsdom';

const WWW = new URL('../../custom_components/reolink_doorbell_talk/www/', import.meta.url);
const ENTITY = 'camera.doorbell';

// Fresh browser per test; the card files are ES modules, so `import.meta.url` is replaced by a constant.
async function load(file) {
  const dom = new JSDOM('<!doctype html><body></body>', { runScripts: 'outside-only', pretendToBeVisual: true });
  const w = dom.window;
  for (const m of ['load', 'play', 'pause']) w.HTMLMediaElement.prototype[m] = () => {};
  const src = readFileSync(new URL(file, WWW), 'utf8').replaceAll('import.meta.url', "'http://ha.test/reolink_doorbell_talk/card.js'");
  w.eval(src);
  return w;
}

const hass = (w, state = 'idle', language = 'en') => ({
  language,
  states: { [ENTITY]: { entity_id: ENTITY, state } },
});

async function makeCard(config = {}, state = 'idle', language = 'en') {
  const w = await load('reolink-talk-card.js');
  const card = w.document.createElement('reolink-talk-card');
  card.setConfig({ entity: ENTITY, autoplay: false, ...config });
  card.hass = hass(w, state, language);
  const q = (id) => card.shadowRoot.getElementById(id);
  return { w, card, q };
}

test('setConfig requires an entity', async () => {
  const w = await load('reolink-talk-card.js');
  const card = w.document.createElement('reolink-talk-card');
  assert.throws(() => card.setConfig({}), /define entity/);
  card.setConfig({ view_entity: ENTITY }); // alias
  assert.equal(card._c.entity, ENTITY);
});

test('texts follow the Home Assistant language', async () => {
  const en = await makeCard({}, 'idle', 'en');
  assert.equal(en.q('t').textContent, 'Talk to the doorbell');
  assert.equal(en.q('ttl').textContent, 'Doorbell');
  const es = await makeCard({}, 'idle', 'es');
  assert.equal(es.q('t').textContent, 'Hablar al timbre');
  assert.equal(es.q('ttl').textContent, 'Timbre');
  const custom = await makeCard({ title: 'Front door' });
  assert.equal(custom.q('ttl').textContent, 'Front door');
});

test('online: the talk button is enabled and there is no video message', async () => {
  const { q } = await makeCard();
  assert.equal(q('b').disabled, false);
  assert.equal(q('vmsg').textContent, '');
});

test('offline: the talk button is disabled and the video says so', async () => {
  const { q } = await makeCard({}, 'unavailable');
  assert.equal(q('b').disabled, true);
  assert.equal(q('vmsg').textContent, 'The doorbell is not responding');
});

test('offline message is translated', async () => {
  const { q } = await makeCard({}, 'unavailable', 'es');
  assert.equal(q('vmsg').textContent, 'El timbre no responde');
});

test('the talk button works again when the doorbell comes back', async () => {
  const { w, card, q } = await makeCard({}, 'unavailable');
  assert.equal(q('b').disabled, true);
  card.hass = hass(w, 'idle');
  assert.equal(q('b').disabled, false);
  assert.equal(q('vmsg').textContent, '');
});

test('offline: clicking or holding the button does not start the voice', async () => {
  const toggle = await makeCard({}, 'unavailable');
  toggle.q('b').click();
  assert.equal(toggle.card._state, 'off');
  assert.ok(!toggle.card._talk);
  const hold = await makeCard({ hold_to_talk: true }, 'unavailable');
  // Real browsers do not deliver this event to a disabled button; if one does, the card only shows the offline notice.
  hold.q('b').dispatchEvent(new hold.w.Event('pointerdown', { bubbles: true }));
  assert.ok(['off', 'error'].includes(hold.card._state), hold.card._state);
  assert.ok(!hold.card._talk);
});

test('a conversation in progress is closed when the doorbell goes offline', async () => {
  const { w, card } = await makeCard();
  let torn = 0;
  card._teardownTalk = () => { torn++; card._talk = null; };
  card._talk = { kind: 'ws' };
  card.hass = hass(w, 'unavailable');
  assert.equal(torn, 1);
  assert.equal(card._state, 'off');
});

test('layout options become CSS variables', async () => {
  const { card } = await makeCard({ aspect_ratio: '16:9', crop_video: true, max_width: 600 });
  assert.equal(card.style.getPropertyValue('--rt-aspect'), '16 / 9');
  assert.equal(card.style.getPropertyValue('--rt-fit'), 'cover');
  assert.equal(card.style.getPropertyValue('--rt-max-width'), '600px');
  const plain = await makeCard({});
  assert.equal(plain.card.style.getPropertyValue('--rt-aspect'), '4 / 3');
  assert.equal(plain.card.style.getPropertyValue('--rt-fit'), 'contain');
  assert.equal(plain.card.style.getPropertyValue('--rt-max-width'), '');
  const bad = await makeCard({ aspect_ratio: 'wide' });
  assert.equal(bad.card.style.getPropertyValue('--rt-aspect'), '4 / 3');
});

test('hold_to_talk switches the mode to hold', async () => {
  const { card, q } = await makeCard({ hold_to_talk: true });
  assert.equal(card._c.mode, 'hold');
  assert.equal(q('t').textContent, 'Hold to talk');
});

test('the editor form lists the card options, and only the LAN card has the fallback switch', async () => {
  const w = await load('reolink-talk-card.js');
  const names = (cls) => cls.getConfigForm().schema.map((s) => s.name);
  const card = names(w.customElements.get('reolink-talk-card'));
  for (const n of ['entity', 'title', 'hold_to_talk', 'autoplay', 'aspect_ratio', 'crop_video', 'show_info', 'fullscreen_button', 'advanced']) {
    assert.ok(card.includes(n), n);
  }
  assert.ok(!card.includes('view_fallback'));
  await w.eval(readFileSync(new URL('reolink-talk-lan-card.js', WWW), 'utf8'));
  const lan = names(w.customElements.get('reolink-talk-lan-card'));
  assert.ok(lan.includes('view_fallback'));
});

test('the LAN card forces WebRTC and keeps the same offline behaviour', async () => {
  const w = await load('reolink-talk-card.js');
  w.eval(readFileSync(new URL('reolink-talk-lan-card.js', WWW), 'utf8'));
  await w.customElements.whenDefined('reolink-talk-lan-card');
  const card = w.document.createElement('reolink-talk-lan-card');
  card.setConfig({ entity: ENTITY, autoplay: false, view_transport: 'hls' });
  assert.equal(card._c.view_transport, 'webrtc');
  card.hass = hass(w, 'unavailable');
  assert.equal(card.shadowRoot.getElementById('b').disabled, true);
  assert.equal(card.shadowRoot.getElementById('ttl').textContent, 'Doorbell (LAN)');
});

test('while the video loads the card says so instead of showing an error', async () => {
  const { card, q } = await makeCard({});
  card._hass.callWS = () => new Promise(() => {}); // Home Assistant never answers: the video stays loading
  card._startViewHls();
  assert.equal(q('vmsg').textContent, 'Loading video…');
});

// jsdom has no Fullscreen API: a small fake with the same calls and events.
function fakeFullscreen(w) {
  const d = w.document;
  const st = { el: null, calls: [] };
  Object.defineProperty(d, 'fullscreenEnabled', { value: true });
  Object.defineProperty(d, 'fullscreenElement', { get: () => st.el });
  w.HTMLElement.prototype.requestFullscreen = function () { st.calls.push('enter'); st.el = this; d.dispatchEvent(new w.Event('fullscreenchange')); return Promise.resolve(); };
  d.exitFullscreen = () => { st.calls.push('exit'); st.el = null; d.dispatchEvent(new w.Event('fullscreenchange')); return Promise.resolve(); };
  return st;
}

async function makeFsCard(config = {}, withApi = true) {
  const w = await load('reolink-talk-card.js');
  const st = withApi ? fakeFullscreen(w) : null;
  const card = w.document.createElement('reolink-talk-card');
  w.document.body.appendChild(card);
  card.setConfig({ entity: ENTITY, autoplay: false, ...config });
  card.hass = hass(w);
  return { w, card, st, q: (id) => card.shadowRoot.getElementById(id) };
}

test('fullscreen: the button toggles the whole card and its icon follows', async () => {
  const { card, st, q } = await makeFsCard();
  assert.ok(card.hasAttribute('data-fs-ok'));
  assert.equal(q('fsi').getAttribute('icon'), 'mdi:fullscreen');
  q('fs').click();
  assert.deepEqual(st.calls, ['enter']);
  assert.equal(st.el, card); // the card (video + talk button), not just the video
  assert.equal(q('fsi').getAttribute('icon'), 'mdi:fullscreen-exit');
  q('fs').click();
  assert.deepEqual(st.calls, ['enter', 'exit']);
  assert.equal(q('fsi').getAttribute('icon'), 'mdi:fullscreen');
});

test('fullscreen: the button is hidden when the option is off', async () => {
  assert.ok(!(await makeFsCard({ fullscreen_button: false })).card.hasAttribute('data-fs-ok'));
  assert.ok(!(await makeFsCard({ fullscreen_button: false }, false)).card.hasAttribute('data-fs-ok'));
});

test('fullscreen without the browser API: the card covers the window with CSS and Escape leaves', async () => {
  const { w, card, q } = await makeFsCard({}, false);
  assert.ok(card.hasAttribute('data-fs-ok')); // iPhone, Companion app on iOS, Fully Kiosk...
  q('fs').click();
  assert.ok(card.hasAttribute('data-fs-css'));
  assert.equal(q('fsi').getAttribute('icon'), 'mdi:fullscreen-exit');
  w.document.dispatchEvent(new w.KeyboardEvent('keydown', { key: 'Escape' }));
  assert.ok(!card.hasAttribute('data-fs-css'));
  assert.equal(q('fsi').getAttribute('icon'), 'mdi:fullscreen');
  q('fs').click();
  q('fs').click();
  assert.ok(!card.hasAttribute('data-fs-css'));
});

test('fullscreen without the browser API: a conversation survives entering and leaving', async () => {
  const { card, q } = await makeFsCard({}, false);
  let torn = 0;
  card._teardownTalk = () => { torn++; card._talk = null; };
  card._talk = { kind: 'ws' };
  q('fs').click();
  q('fs').click();
  assert.equal(torn, 0);
  assert.ok(card._talk);
});

test('fullscreen without the browser API: if the container limits the card, it gives up and hides the button', async () => {
  const { w, card, q } = await makeFsCard({}, false);
  card.getBoundingClientRect = () => ({ width: 300, height: 200 }); // not the size of the window
  q('fs').click();
  await new Promise((r) => w.requestAnimationFrame(r));
  await new Promise((r) => setTimeout(r, 20));
  assert.ok(!card.hasAttribute('data-fs-css'));
  assert.ok(!card.hasAttribute('data-fs-ok'));
});

test('fullscreen: when the browser refuses the request, the CSS mode takes over', async () => {
  const { w, card, q } = await makeFsCard();
  w.HTMLElement.prototype.requestFullscreen = () => Promise.reject(new Error('not allowed'));
  q('fs').click();
  await new Promise((r) => setTimeout(r, 10));
  assert.ok(card.hasAttribute('data-fs-css'));
});

test('fullscreen: leaving it does not close a conversation, and going offline still does', async () => {
  const { w, card, st, q } = await makeFsCard();
  let torn = 0;
  card._teardownTalk = () => { torn++; card._talk = null; };
  card._talk = { kind: 'ws' };
  q('fs').click();
  q('fs').click();
  assert.equal(torn, 0);
  assert.ok(card._talk);
  q('fs').click();
  card.hass = hass(w, 'unavailable');
  assert.equal(torn, 1);
  assert.equal(st.el, card); // the card stays in full screen, showing the offline notice
});

test('fullscreen: removing the card from the page leaves full screen', async () => {
  const { card, st, q } = await makeFsCard();
  q('fs').click();
  card.remove();
  assert.equal(st.el, null);
});
