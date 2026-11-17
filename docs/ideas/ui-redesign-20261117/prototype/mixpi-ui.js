'use strict';
/* MixPi UI prototype: the current build-2 screen and the proposed redesign, sharing one
   simulated engine (decks, pads, USB drive, library scan). Plain DOM, no libraries. */
(function () {
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
function hash(s) { let h = 2166136261; for (const c of s) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }
const fmtN = n => n.toLocaleString('en-GB');

/* ---------- icons ---------- */
const SV = d => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const SF = d => `<svg viewBox="0 0 24 24" fill="currentColor">${d}</svg>`;
const I = {
  usb: SV('<circle cx="12" cy="19.5" r="2"/><path d="M12 17.5V3.5M9.5 6 12 3.5 14.5 6M12 14.5 7.5 12V9.2M12 12.6l4.5-2.6V8"/><rect x="15" y="5.6" width="3" height="2.4" rx=".4"/><circle cx="7.5" cy="8" r="1.2"/>'),
  menu: SV('<path d="M4 7h16M4 12h16M4 17h16"/>'),
  x: SV('<path d="M6 6l12 12M18 6 6 18"/>'),
  pen: SV('<path d="M4 20h4L19.4 8.6a2.1 2.1 0 0 0-3-3L5 17v3z"/><path d="M14.6 7.4l2 2"/>'),
  gear: SV('<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>'),
  eject: SV('<path d="M12 5 19 13H5z"/><path d="M5 18h14"/>'),
  search: SV('<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>'),
  chev: SV('<path d="m9 6 6 6-6 6"/>'),
  back: SV('<path d="M15 6l-6 6 6 6"/>'),
  play: SF('<path d="M7 5v14l12-7z"/>'),
  stop: SF('<rect x="6" y="6" width="12" height="12" rx="1.5"/>'),
  lock: SV('<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>'),
  pi: SV('<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/><rect x="9" y="9" width="6" height="6" rx="1"/>'),
  folder: SV('<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'),
  list: SV('<path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01"/>'),
  clock: SV('<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>'),
  mic: SV('<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>'),
  wave: SV('<path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 10v4"/>'),
  disc: SV('<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="2.5"/>'),
  check: SV('<path d="m5 12.5 4.5 4.5L19 7.5"/>'),
  more: SF('<circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/>'),
  plus: SV('<path d="M12 5v14M5 12h14"/>'),
  up: SV('<path d="m6 15 6-6 6 6"/>'),
  down: SV('<path d="m6 9 6 6 6-6"/>'),
  grip: SV('<path d="M9 6h.01M15 6h.01M9 12h.01M15 12h.01M9 18h.01M15 18h.01"/>'),
  crate: SV('<path d="M4 9h16v10H4zM5 9l2-4h10l2 4M9 13h6"/>'),
  copy: SV('<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>'),
  scan: SV('<path d="M20 12a8 8 0 1 1-2.34-5.66M20 4v4h-4"/>'),
  load: SV('<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>'),
};
const ic = (n, s = 22) => I[n].replace('<svg', `<svg width="${s}" height="${s}" aria-hidden="true"`);

/* ---------- example library ---------- */
const HC = ['#c50a08', '#32be44', '#42d4f4', '#f8d200', '#af00cc', '#fca311', '#e8e8ff', '#3c6cff'];
const TR = {};
function track(id, title, artist, bpm, key, keyName, dur, src, extra = {}) {
  const seed = hash(id), r = rng(seed), cues = [];
  const nc = extra.sample ? 0 : 3 + Math.floor(r() * 3);
  for (let i = 0; i < nc; i++) cues.push({ n: i + 1, pos: dur * (0.07 + (i * 0.8) / nc + r() * 0.04), color: HC[i] });
  TR[id] = Object.assign({ id, title, artist, bpm, key, keyName, dur, src, seed, cues }, extra);
  return id;
}
const PI = [
  track('p1', 'Black & Tan X Popular (YT ft. Lancey Foux X…)', '', 140, '11A', 'F#m', 196, 'pi'),
  track('p2', "Frontin' The Best (Giggs X The Neptunes)", '', 102, '6A', 'Gm', 214, 'pi'),
  track('p3', 'Kanye West-Addiction Kenny dope & Terry Hunt', '', 96, '11B', 'A', 232, 'pi'),
  track('p4', 'MIGOS x JAY-Z (jigga what jigga who)', '', 94, '12A', 'C#m', 188, 'pi'),
  track('p5', 'Whipped Cream', '', 85, '12A', 'C#m', 230, 'pi'),
  track('p6', 'Night Bus Edit', 'Example artist', 140, '8A', 'Am', 201, 'pi'),
  track('p7', 'Peckham Riddim (VIP)', 'Example artist', 142, '4A', 'Fm', 187, 'pi'),
  track('p8', 'Late Checkout', 'Example artist', 98, '9B', 'G', 244, 'pi'),
  track('p9', 'Soft Landing (Dub)', 'Example artist', 124, '2A', 'Ebm', 266, 'pi'),
  track('p10', 'Moonlight Bounce', 'Example artist', 112, '10A', 'Bm', 209, 'pi'),
  track('p11', 'Low End Flip', 'Example artist', 140, '5A', 'Cm', 178, 'pi'),
  track('p12', '2026-11-17_00h09m13s', 'Recording', 102, '12A', 'C#m', 1840, 'pi'),
];
const USB = [
  track('u1', "Frontin' The Best (Giggs X The Neptunes)", '', 102, '6A', 'Gm', 214, 'usb'),
  track('u2', 'Warehouse Call', 'Example artist', 138, '7A', 'Dm', 212, 'usb'),
  track('u3', 'Basement Tape 4', 'Example artist', 140, '8A', 'Am', 190, 'usb'),
  track('u4', 'Slow Motion (Club Mix)', 'Example artist', 100, '3A', 'Bbm', 236, 'usb'),
  track('u5', 'Concrete Garden', 'Example artist', 141, '1A', 'Abm', 205, 'usb'),
  track('u6', 'Night Shift', 'Example artist', 96, '10B', 'D', 221, 'usb'),
  track('u7', 'Pressure Drop VIP', 'Example artist', 140, '6A', 'Gm', 199, 'usb'),
  track('u8', 'Southside Bounce', 'Example artist', 104, '11A', 'F#m', 183, 'usb'),
  track('u9', 'Late Train', 'Example artist', 122, '9A', 'Em', 257, 'usb'),
  track('u10', 'Beautiful', 'Example artist', 92, '5B', 'Eb', 228, 'usb'),
];
const SM = [
  track('s1', 'MergeFX Sample Sound 101.wav', '', 0, '', '', 1.2, 'pi', { sample: 1 }),
  track('s2', "03 - Times' up.flac", '', 0, '6B', 'F', 18, 'pi', { sample: 1 }),
  track('s3', 'Air horn.wav', '', 0, '', '', 2.4, 'usb', { sample: 1 }),
  track('s4', 'Rewind spinback.wav', '', 0, '', '', 3.1, 'pi', { sample: 1 }),
  track('s5', 'Siren rise.wav', '', 0, '', '', 4.2, 'pi', { sample: 1 }),
  track('s6', 'Vocal - Oi.wav', '', 0, '', '', 0.9, 'pi', { sample: 1 }),
  track('s7', 'Riser 8 bar.wav', '', 0, '', '', 15.0, 'pi', { sample: 1 }),
  track('s8', 'Crowd cheer.wav', '', 0, '', '', 6.0, 'pi', { sample: 1 }),
  track('s9', 'Laser zap.wav', '', 0, '', '', 1.0, 'usb', { sample: 1 }),
  track('s10', 'Sub drop.wav', '', 0, '', '', 3.0, 'pi', { sample: 1 }),
  track('s11', 'Gun finger FX.wav', '', 0, '', '', 2.0, 'pi', { sample: 1 }),
  track('s12', 'Big up yourself (vox).wav', '', 0, '', '', 2.6, 'pi', { sample: 1 }),
];
const REC = ['p12'];
const USB_PL = [
  { name: 'Friday set', ids: ['u1', 'u2', 'u3', 'u7', 'u5', 'u8'], n: 24 },
  { name: 'Warm up', ids: ['u4', 'u6', 'u9', 'u10'], n: 31 },
  { name: 'Grime', ids: ['u2', 'u3', 'u5', 'u7'], n: 58 },
  { name: 'Amapiano', ids: ['u9', 'u4'], n: 40 },
  { name: 'R&B slow', ids: ['u6', 'u10', 'u1'], n: 22 },
  { name: 'Edits', ids: ['u8', 'u1', 'u7'], n: 17 },
];
const PI_PL = [{ name: 'Saturday prep', ids: ['p2', 'p4', 'p6', 'p8'], n: 12 }, { name: 'INBOX - LIVE', ids: ['p9', 'p10'], n: 5 }];
const PI_CR = [{ name: 'Grime', ids: ['p6', 'p7', 'p11'], n: 3 }, { name: 'Hip-hop', ids: ['p2', 'p3', 'p4'], n: 3 }];
const SCAN_FILES = ['Beautiful.mp3', 'Concrete Garden.mp3', 'Night Shift.flac', 'Pressure Drop VIP.mp3', 'Late Train.aiff', 'Southside Bounce.mp3', 'Warehouse Call.wav', 'Slow Motion (Club Mix).mp3'];
const SCAN_DIRS = '/home/pi/Music/Backup/media/MANTACORE-g46/Contents/Master Babes/';
const LOOPS = [['1/32', 1 / 32], ['1/16', 1 / 16], ['1/8', 1 / 8], ['1/4', 1 / 4], ['1/2', 1 / 2], ['1', 1], ['2', 2], ['4', 4], ['8', 8], ['16', 16], ['32', 32], ['64', 64]];
const FX_NAMES = ['Echo', 'Reverb', 'Filter', 'Flanger', 'Bitcrusher', 'Phaser', 'Autopan'];

const camelot = k => { if (!k) return '#5d6b80'; const n = parseInt(k, 10); const minor = k.endsWith('A'); return `hsl(${((n - 1) * 30 + 165) % 360},${minor ? 62 : 70}%,${minor ? 62 : 72}%)`; };
function fmtTime(sec, neg) { sec = Math.max(0, sec); const m = Math.floor(sec / 60), s = sec - m * 60; return (neg ? '-' : '') + m + ':' + (s < 10 ? '0' : '') + s.toFixed(2); }
const fmtLen = s => s < 60 ? (s < 10 ? '0:0' : '0:') + Math.round(s) : Math.floor(s / 60) + ':' + String(Math.round(s % 60)).padStart(2, '0');

/* ---------- shared engine ---------- */
const E = {};
function mkDeck(id, pos, play) { return { id, pos, play, key: false, q: true, sync: false, master: false, rate: 0, loop: null, onPi: false, cue: 0, tmode: 'el', pfl: false }; }
function resetEngine() {
  Object.assign(E, {
    decks: { 1: mkDeck('u1', 58.2, true), 2: mkDeck('p5', 21.4, false) },
    pads: ['s1', 's2', 's3', null, 's4', null, 's5', null].map(id => ({ id, play: false, t: 0, onPi: false })),
    usb: { present: true, state: 'ready', opened: true, ping: 0, safeT: 0 },
    scan: { on: false, pct: 0, fi: 0, ft: 0, total: 3050 },
    rec: { on: false, t: 0 },
    fx: { route: 1, mix: 0.55, slots: [{ n: 0, on: true, meta: 0.4 }, { n: 1, on: false, meta: 0.6 }, { n: 2, on: false, meta: 0.5 }] },
    fx2: { route: 2, mix: 0.4, slots: [{ n: 3, on: false, meta: 0.5 }, { n: 4, on: false, meta: 0.3 }, { n: 5, on: false, meta: 0.6 }] },
    cleaned: [],
    eject: { step: -1, t: 0 },
    set: { keylock: 'RB Fast', buffer: '1024', tempo: '8%', fps: '45', ahead: '8', cache: '1024', scanShow: 'bar', deskbar: 'hidden', time: 'elapsed', q1: true, q2: true, split: false },
  });
  E.decks[1].master = true;
}
resetEngine();
const beatLen = id => 60 / (TR[id].bpm || 120);
const usbAvailable = () => E.usb.present && E.usb.state === 'ready';
const trackUsable = id => TR[id].src !== 'usb' || usbAvailable();
function deckUses(n) { const d = E.decks[n]; return d.id && TR[d.id].src === 'usb' && !d.onPi; }
function loadDeck(n, id) {
  const d = E.decks[n];
  if (!id || d.play || !trackUsable(id)) return false;
  if (d.onPi) { E.cleaned.unshift(`Deck ${n}: ${TR[d.id].title}`); toast(`Removed the Pi copy of “${short(TR[d.id].title)}”`); }
  Object.assign(d, { id, pos: 0, play: false, loop: null, onPi: false, cue: 0 });
  return true;
}
function loadPad(i, id) {
  const p = E.pads[i];
  if (p.play || !trackUsable(id)) return false;
  if (p.onPi) E.cleaned.unshift(`Pad ${i + 1}: ${TR[p.id].title}`);
  Object.assign(p, { id, t: 0, onPi: false });
  return true;
}
const short = s => s.length > 28 ? s.slice(0, 27) + '…' : s;
function usage() {
  const u = [];
  for (const n of [1, 2]) {
    const d = E.decks[n]; if (!deckUses(n)) continue;
    const direct = E.set.cache === 'OFF';
    u.push({ kind: 'deck', n, title: TR[d.id].title, play: d.play, block: direct && d.play, unload: direct && !d.play });
  }
  E.pads.forEach((p, i) => { if (p.id && TR[p.id].src === 'usb' && !p.onPi) u.push({ kind: 'pad', n: i + 1, title: TR[p.id].title }); });
  return u;
}
function startScan() { Object.assign(E.scan, { on: true, pct: E.scan.pct >= 100 ? 0 : E.scan.pct, fi: 0, ft: 0 }); dirty = true; }
function finishEject() {
  for (const n of [1, 2]) { const d = E.decks[n]; if (deckUses(n)) { if (E.set.cache === 'OFF') Object.assign(d, { id: null, play: false }); else d.onPi = true; } }
  E.pads.forEach(p => { if (p.id && TR[p.id].src === 'usb') p.onPi = true; });
  E.usb.state = 'safe'; E.usb.opened = false; E.usb.safeT = 30; E.usb.ping = 0;
}

/* ---------- waveforms ---------- */
const PPS = 90; // waveform columns per second at zoom 1
const wfCache = new Map();
function wf(id) {
  if (wfCache.has(id)) return wfCache.get(id);
  const t = TR[id], n = Math.max(2, Math.ceil(t.dur * PPS)), r = rng(t.seed);
  const l = new Float32Array(n), m = new Float32Array(n), h = new Float32Array(n);
  const beat = beatLen(id); let nm = 0.5, nh = 0.5;
  for (let i = 0; i < n; i++) {
    const s = i / PPS;
    if (t.sample) { const env = Math.exp(-s / (t.dur * 0.6)); l[i] = 0.6 * env + 0.2 * r(); m[i] = 0.7 * env * (0.5 + 0.5 * r()); h[i] = 0.5 * env * r(); continue; }
    const ph = (s % beat) / beat, kick = Math.exp(-ph * 10), hp = ((s % (beat / 2)) / (beat / 2)), hat = Math.exp(-hp * 12);
    const bar = Math.floor(s / (beat * 16)), intro = Math.min(1, s / (t.dur * 0.08) + 0.35);
    const outro = Math.min(1, (t.dur - s) / (t.dur * 0.06) + 0.3);
    const e = (0.55 + 0.45 * Math.abs(Math.sin(bar * 1.7 + t.seed % 7))) * intro * outro;
    nm += (r() - 0.5) * 0.25; nm = Math.min(1, Math.max(0.1, nm)); nh += (r() - 0.5) * 0.3; nh = Math.min(1, Math.max(0.05, nh));
    const tone = 0.5 + 0.5 * Math.sin(s * 0.9 + (t.seed % 13));
    l[i] = Math.min(1, (0.14 + 0.86 * kick) * e * (0.6 + 0.5 * tone) + 0.04 * r());
    m[i] = Math.min(1, (0.06 + 0.42 * nm * (1 - 0.6 * tone)) * e * (0.8 + 0.3 * r()));
    h[i] = Math.min(1, (0.16 + 0.75 * hat * nh + 0.25 * (1 - tone)) * e * (0.7 + 0.4 * r()));
  }
  const res = { n, l, m, h }; wfCache.set(id, res); return res;
}
function col(l, m, h, a) { const mx = Math.max(l, m, h) || 1; return `rgba(${(l / mx) * 255 | 0},${(m / mx) * 255 | 0},${(h / mx) * 255 | 0},${a})`; }
const ovCache = new Map();
function overviewImage(id, w, h, th) {
  const key = id + ':' + w + ':' + h + ':' + th;
  if (ovCache.has(key)) return ovCache.get(key);
  const c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d'); const d = wf(id);
  for (let px = 0; px < w; px++) {
    const i0 = Math.floor((px / w) * d.n), i1 = Math.max(i0 + 1, Math.floor(((px + 1) / w) * d.n));
    let a = 0, L = 0, M = 0, H = 0;
    for (let i = i0; i < i1; i++) { const v = Math.max(d.l[i], d.m[i], d.h[i]); if (v > a) a = v; L += d.l[i]; M += d.m[i]; H += d.h[i]; }
    const amp = a * (h / 2 - 1); x.fillStyle = col(L, M, H, 1); x.fillRect(px, h / 2 - amp, 1, amp * 2);
  }
  ovCache.set(key, c); return c;
}
function prepCanvas(cv) {
  const dpr = Math.min(2, window.devicePixelRatio || 1), w = cv.clientWidth || +cv.dataset.w, h = cv.clientHeight || +cv.dataset.h;
  cv._w = w; cv._h = h; cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
  const ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); cv._ctx = ctx;
}
function drawScroll(cv, n, th) {
  const ctx = cv._ctx, w = cv._w, h = cv._h, d = E.decks[n];
  ctx.fillStyle = th === 'rd' ? '#05070a' : '#000'; ctx.fillRect(0, 0, w, h);
  if (!d.id) { ctx.fillStyle = th === 'rd' ? '#3a4658' : '#333'; ctx.font = '600 14px Ubuntu, sans-serif'; ctx.fillText(th === 'rd' ? 'Load a track from Tracks' : '', 12, h / 2 + 5); return; }
  const t = TR[d.id], data = wf(d.id), zoom = +(cv.dataset.z || 1), cx = Math.floor(w / 2), cy = h / 2, pps = PPS * zoom;
  if (d.loop) { const x0 = cx + (d.loop.s - d.pos) * pps, x1 = x0 + d.loop.l * pps; ctx.fillStyle = th === 'rd' ? 'rgba(181,225,92,.16)' : 'rgba(60,200,90,.2)'; ctx.fillRect(x0, 0, x1 - x0, h); }
  for (let x = 0; x < w; x++) {
    const i = Math.floor(d.pos * PPS + (x - cx) / zoom);
    if (i < 0 || i >= data.n) continue;
    const L = data.l[i], M = data.m[i], H = data.h[i], amp = Math.max(L, M * 0.92, H * 0.85) * (h / 2 - 3);
    ctx.fillStyle = col(L, M, H, x < cx && th === 'rd' ? 0.78 : 1); ctx.fillRect(x, cy - amp, 1, amp * 2);
  }
  const beat = beatLen(d.id), b0 = Math.floor((d.pos - cx / pps) / beat), b1 = Math.ceil((d.pos + (w - cx) / pps) / beat);
  for (let b = Math.max(0, b0); b <= b1; b++) { const x = Math.round(cx + (b * beat - d.pos) * pps) + 0.5; ctx.fillStyle = b % 4 ? 'rgba(255,255,255,.22)' : 'rgba(255,255,255,.55)'; ctx.fillRect(x, 0, 1, b % 4 ? 8 : h); if (b % 4) ctx.fillRect(x, h - 8, 1, 8); }
  for (const c of t.cues) {
    const x = Math.round(cx + (c.pos - d.pos) * pps); if (x < -20 || x > w + 2) continue;
    ctx.fillStyle = c.color; ctx.fillRect(x, 0, 2, h); ctx.fillRect(x, 0, 15, 15);
    ctx.fillStyle = '#000'; ctx.font = '700 11px Ubuntu, sans-serif'; ctx.fillText(String(c.n), x + 4, 12);
  }
  ctx.fillStyle = '#fff'; ctx.fillRect(cx - 1, 0, 2, h);
  ctx.beginPath(); ctx.moveTo(cx - 6, 0); ctx.lineTo(cx + 6, 0); ctx.lineTo(cx, 7); ctx.closePath(); ctx.fill();
  ctx.beginPath(); ctx.moveTo(cx - 6, h); ctx.lineTo(cx + 6, h); ctx.lineTo(cx, h - 7); ctx.closePath(); ctx.fill();
}
function drawOverview(cv, n, th) {
  const ctx = cv._ctx, w = cv._w, h = cv._h, d = E.decks[n];
  ctx.fillStyle = th === 'rd' ? '#05070a' : '#000'; ctx.fillRect(0, 0, w, h);
  if (!d.id) return;
  const t = TR[d.id]; ctx.drawImage(overviewImage(d.id, Math.round(w), Math.round(h), th), 0, 0, w, h);
  const px = (d.pos / t.dur) * w;
  ctx.fillStyle = th === 'rd' ? 'rgba(5,7,10,.62)' : 'rgba(200,200,220,.33)'; ctx.fillRect(0, 0, px, h);
  if (d.loop) { ctx.fillStyle = 'rgba(181,225,92,.3)'; ctx.fillRect((d.loop.s / t.dur) * w, 0, Math.max(2, (d.loop.l / t.dur) * w), h); }
  for (const c of t.cues) { const x = (c.pos / t.dur) * w; ctx.fillStyle = c.color; ctx.fillRect(x, 0, 2, h); if (th === 'rd') ctx.fillRect(x - 3, h - 6, 8, 6); }
  ctx.fillStyle = th === 'rd' ? (n === 1 ? '#4aa8ff' : '#ff8f3f') : '#fff'; ctx.fillRect(px - 1, 0, 2, h);
}

/* ---------- UI state ---------- */
const CU = {};
const RD = {};
function resetUI() {
  Object.assign(CU, { tab: 'decks', settings: false, adv: false, loop: 0, dlg: null, actions: false, loadSub: false, show: false, srcMenu: false, feature: 'TRACKS', sel: 'p2', sampleLoad: false, leSel: false });
  Object.assign(RD, { tab: 'decks', ovl: null, sheet: null, tool: 0, toolTab: 'loop', clear: false, sel: 'p2', list: 'pi:tracks', srcSel: 'usb', srcPath: [], edit: false, srcReturn: null, sample: { src: 'samples', sel: 's3', pad: null }, set: 'playback', toast: null, toastT: 0, hl: [], fxUnit: 1, srcOrder: ['usb', 'pi', 'rec', 'hist', 'folders', 'samples'], srcHidden: {}, srcStart: 'pi' });
}
resetUI();
let dirty = true;
function toast(msg) { RD.toast = msg; RD.toastT = 2.6; dirty = true; }

/* ===================== CURRENT UI ===================== */
const cb = (label, a, v, w, cls = '', h = 48, extra = '') => `<div class="btn ${cls}" style="width:${w - 4}px;height:${h - 4}px;${extra}" data-a="${a}" data-v="${v ?? ''}">${label}</div>`;
function cuTop() {
  const tabs = [['DECKS', 'decks'], ['TRACKS', 'tracks'], ['FX', 'fx'], ['SAMPLER', 'sampler']]
    .map(([t, k]) => cb(t, 'tab', k, 84, 'tab' + (CU.tab === k && !CU.settings ? ' on' : ''))).join('');
  return `<div class="abs topbar row" style="left:0;top:0;width:800px;padding-top:1px" data-hl="cu-top">${tabs}
    <div data-hl="cu-loadeject">${cb('LOAD / EJECT', 'le', '', 132)}</div><div style="flex:1"></div>
    ${cb('SETTINGS', 'settings', '', 96, CU.settings ? 'on' : '')}${cb(E.rec.on ? '■ STOP' : '● REC', 'rec', '', 80, 'rec' + (E.rec.on ? ' on' : ''))}
    <div class="cpu">CPU<br><b>3%</b></div></div>`;
}
function cuDeckInfo(top, n, show = true) {
  const d = E.decks[n], t = d.id ? TR[d.id] : null;
  return `<div class="abs" style="left:${(n - 1) * 400}px;top:${top}px;width:400px;height:82px">
    <div class="titlestrip"><b>${n}</b><span style="overflow:hidden;text-overflow:ellipsis">${t ? esc(t.title) : ''}</span></div>
    <div class="stats"><div class="t" data-live="cut${n}"></div><div class="bpm">${t ? t.bpm.toFixed(2) : '0.00'}</div><div class="r">${d.rate.toFixed(1)}</div><div class="k">${t ? `${t.key} (${t.keyName})` : ''}</div></div></div>`;
}
function cuSettings() {
  const s = E.set, pre = (k, opts, w) => opts.map(o => cb(o, 'set', k + ':' + o, w, s[k] === o ? 'on' : '')).join('');
  const rowS = (lab, inner) => `<div class="row" style="height:48px;border-bottom:1px solid #34445e"><div class="slab">${lab}</div>${inner}</div>`;
  if (CU.adv) return `<div class="abs settings" style="left:0;top:50px;width:800px;height:326px;padding:6px">
    <div style="height:28px;font-size:17px">ADVANCED · DISPLAY / NEXT LAUNCH</div>
    <div class="row">${rowS('FPS', pre('fps', ['30', '45', '60'], 100))}${rowS('READ AHEAD*', pre('ahead', ['2', '8', '24'], 100))}</div>
    <div class="row">${rowS('CACHE MB*', pre('cache', ['OFF', '512', '1024'], 100))}<div class="slab" style="width:300px">* Next launch</div></div>
    <div class="row" style="margin-top:6px">${cb('Back', 'adv', '0', 390)}${cb('Mixxx preferences…', 'noop', '', 390)}</div></div>`;
  return `<div class="abs settings row" style="left:0;top:50px;width:800px;height:326px;padding:4px">
    <div style="width:395px;padding:4px"><div style="height:28px;font-size:17px">PLAYBACK</div>
      ${rowS('KEYLOCK', pre('keylock', ['ST', 'RB Fast', 'RB Fine'], 100))}${rowS('BUFFER', pre('buffer', ['256', '512', '1024'], 100))}
      ${rowS('TEMPO ±', `<div class="btn" style="width:296px;height:44px;justify-content:space-between;padding:0 8px;background:#20334a;font-weight:400">${s.tempo} <span>▾</span></div>`)}
      <div class="row" style="height:48px">${cb('Q 1', 'set', 'q1', 126, s.q1 ? 'on' : '')}${cb('Q 2', 'set', 'q2', 126, s.q2 ? 'on' : '')}${cb('SPLIT CUE', 'set', 'split', 126, s.split ? 'on' : '')}</div></div>
    <div style="width:395px;padding:4px"><div style="height:28px;font-size:17px;margin-top:20px">INTERFACE</div>
      ${cb('Show top bar', 'noop', '', 390)}<div class="slab" style="width:380px">Desktop · Mixxx · Speaker</div><div class="slab" style="width:380px">Settings stays available to restore it.</div>
      ${cb('Advanced…', 'adv', '1', 390)}</div></div>`;
}
function cuLoop(n) {
  const d = E.decks[n], beat = d.id ? beatLen(d.id) : 0.5;
  const sz = (lab, v) => cb(lab, 'loopsz', v, 133.33, d.loop && Math.abs(d.loop.l - v * beat) < 1e-6 ? 'on' : '', 48);
  return `<div class="abs loop" style="left:0;top:50px;width:800px;height:244px" data-hl="cu-loop">
    <div class="loophead"><span style="flex:1">DECK ${n}  •  LOOP  •  WAVEFORM BELOW</span>${cb('Close', 'loop', n, 100)}</div>
    <div class="row">${LOOPS.slice(0, 6).map(([l, v]) => sz(l, v)).join('')}</div>
    <div class="row">${LOOPS.slice(6).map(([l, v]) => sz(l, v)).join('')}</div>
    <div class="row">${cb('½', 'lhalf', n, 200)}${cb('×2', 'ldouble', n, 200)}${cb('Exit', 'lexit', n, 200, d.loop ? 'on' : '')}${cb('Reloop', 'lreloop', n, 200, d.loop ? 'dis' : '')}</div></div>`;
}
function cuTable(top, height, ids, cols) {
  const head = cols.map(c => `<div style="${c.w ? `width:${c.w}px` : 'flex:1'}">${c.h}</div>`).join('');
  const rows = ids.map(id => { const t = TR[id]; return `<div class="trow${CU.sel === id ? ' sel' : ''}" data-a="row" data-v="${id}" style="${trackUsable(id) ? '' : 'opacity:.4'}">${cols.map(c => `<div style="${c.w ? `width:${c.w}px` : 'flex:1;min-width:0'};${c.r ? 'justify-content:flex-end' : ''}">${c.f(t)}</div>`).join('')}</div>`; }).join('');
  return `<div class="abs" style="left:0;top:${top}px;width:800px;height:${height}px;background:#000">
    <div class="thead" style="padding-right:22px">${head}</div>
    <div class="scrollbox" data-keep="cutable" style="height:${height - 34}px">${rows}</div></div>`;
}
const CU_COLS = [{ h: 'TITLE', f: t => esc(t.title) }, { h: 'ARTIST', w: 160, f: t => esc(t.artist) }, { h: 'BPM', w: 72, r: 1, f: () => '' }, { h: 'KEY', w: 80, r: 1, f: t => t.key ? '- ' + t.keyName : '' }];
const CU_SCOLS = [{ h: 'FILENAME', f: t => esc(t.title) }, { h: 'BPM', w: 100, f: () => '' }, { h: 'KEY', w: 100, f: t => t.key }, { h: 'DURATION', w: 108, f: t => fmtLen(t.dur) }];
const CU_FEATS = [['REKORDBOX', 'disc'], ['HISTORY', 'clock'], ['TRACKS', 'list'], ['COMPUTER', 'folder'], ['RECORDINGS', 'mic'], ['PLAYLISTS', 'list'], ['CRATES', 'crate'], ['AUTO DJ', 'disc']];
function cuFeatureIds() {
  switch (CU.feature) {
    case 'MANTACORE': return USB.map(t => t.id);
    case 'RECORDINGS': return REC;
    case 'PLAYLISTS': return PI_PL[0].ids;
    case 'CRATES': return PI_CR[0].ids;
    case 'HISTORY': return ['p2', 'p5', 'p4'];
    case 'AUTO DJ': return [];
    default: return CU.sampleLoad ? SM : PI;
  }
}
function cuTracks() {
  let h = `<div class="abs tool row" style="left:0;top:50px;width:800px">
    <div class="search">SEARCH...<span style="margin-left:auto;margin-right:10px;font-size:12px;color:#c9ced6">▾</span></div>
    <div data-hl="cu-actions">${cb('Actions', 'actions', '', 96, 'navy')}</div><div data-hl="cu-show">${cb(CU.show ? 'Hide' : 'Show', 'show', '', 90, 'navy')}</div></div>`;
  let top = 98;
  if (CU.sampleLoad) {
    h += `<div class="abs row" style="left:0;top:98px;width:800px;height:48px;background:#173357" data-hl="cu-loadto"><div style="width:90px;display:flex;align-items:center;padding-left:4px">LOAD TO</div>
      ${[0, 1, 2, 3].map(i => cb('PAD ' + (i + 1), 'cupad', i, 155, E.pads[i].play ? 'dis' : '')).join('')}${cb('DONE', 'done', '', 90)}</div>`;
    top = 146;
  }
  const bodyH = 376 - top;
  const textFeat = { REKORDBOX: `<h2 style="margin:6px 4px;font-size:28px">Rekordbox</h2><p style="margin:4px;font-size:16px;line-height:1.5">Reads databases exported for Pioneer CDJ / XDJ players using the Rekordbox Export mode.<br>Rekordbox can only export to USB or SD devices with a FAT or HFS file system.<br>Mixxx can read a database from any device that contains the database folders (<code>PIONEER</code> and <code>Contents</code>).<br>Not supported are Rekordbox databases that have been moved to an external device via <i>Preferences &gt; Advanced &gt; Database management</i>.</p>`,
    COMPUTER: `<h2 style="margin:6px 4px;font-size:28px">Computer</h2><p style="margin:4px;font-size:16px">“Computer” lets you navigate, view, and load tracks from folders on your hard disk and external devices.</p>` };
  if (textFeat[CU.feature]) h += `<div class="abs" style="left:0;top:${top}px;width:800px;height:${bodyH - 28}px;background:#000;overflow:hidden">${textFeat[CU.feature]}</div>`;
  else h += cuTable(top, bodyH - 28, cuFeatureIds(), CU.sampleLoad ? CU_SCOLS : CU_COLS);
  h += `<div class="abs titlestrip" style="left:0;top:${376 - 28}px;width:800px"><b>1</b><span style="width:372px;overflow:hidden">${E.decks[1].id ? esc(TR[E.decks[1].id].title) : ''}</span><b>2</b><span>${E.decks[2].id ? esc(TR[E.decks[2].id].title) : ''}</span></div>`;
  if (CU.show) {
    const feats = (usbAvailable() ? [['MANTACORE', 'usb']] : []).concat(CU_FEATS);
    h += `<div class="abs side" style="left:510px;top:${top}px;width:290px;height:${bodyH}px" data-hl="cu-sidebar">
      ${cb('Sources', 'srcmenu', '', 290, 'navy')}${cb('Back', 'feat', 'TRACKS', 290, 'navy')}
      <div class="scrollbox" style="height:${bodyH - 96}px">${feats.map(([f, icn]) => `<div class="sideitem${CU.feature === f ? ' sel' : ''}" data-a="feat" data-v="${f}"><span style="color:#e8833a">${ic(icn, 18)}</span>${f}</div>`).join('')}</div></div>`;
  }
  if (CU.srcMenu) {
    const chk = (t, on, blue) => `<div class="row" style="height:48px;align-items:center;gap:12px;padding-left:12px;${blue ? 'background:#2f7fd6' : ''}"><span class="cb${on ? '' : ' off'}"></span>${t}</div>`;
    h += `<div class="abs row" style="left:190px;top:50px;width:610px;height:430px;box-shadow:0 10px 40px #000" data-hl="cu-srcmenu">
      <div style="width:310px;background:linear-gradient(160deg,#3c8fe6,#2a6fc9);padding-top:4px">${['Tracks', 'Auto DJ', 'Playlists', 'Crates', 'Computer', 'Recordings', 'History', 'Analyse', 'iTunes'].map(t => chk(t, false)).join('')}</div>
      <div style="width:300px;background:#1d2028;font-size:16px">${chk('Rekordbox', true)}${chk('Serato', false, true)}
        <div style="padding:8px 10px;font-size:15px">Source order: drag to reorder</div>
        <div class="row"><div style="flex:1;font-size:15px;line-height:22px;padding-left:12px">Tracks<br><span style="background:#2f7fd6;display:block">Auto DJ</span>Playlists<br>Crates<br>Computer<br>Recordings</div><div style="width:16px;background:#555;border-radius:6px;margin:4px"></div></div>
        <div class="row" style="padding:4px">${cb('Up', 'noop', '', 145)}${cb('Down', 'noop', '', 145)}</div>
        <div style="padding:10px 12px;border-top:1px solid #333">Default source ›</div>
        <div style="padding:10px 12px;cursor:pointer" data-a="srcmenu">Close</div></div></div>`;
  }
  if (CU.actions) {
    h += `<div class="abs menu" style="left:614px;top:98px;width:184px" data-hl="cu-actionsmenu"><div data-a="loadsub">Load <span>›</span></div>
      ${CU.loadSub ? `<div data-a="cuload" data-v="1" style="padding-left:28px">Deck 1</div><div data-a="cuload" data-v="2" style="padding-left:28px">Deck 2</div>` : ''}
      <div data-a="arrange">Arrange columns</div><hr><div data-a="noop">Original full menu <span>›</span></div></div>`;
  }
  return h;
}
function cuSampler() {
  let h = `<div class="abs row" style="left:0;top:50px;width:800px;height:48px">${cb('LOAD SAMPLE', 'loadsample', '', 180)}<div style="display:flex;align-items:center;font-size:14px;padding-left:4px">Select a track, then its pad. Stop a pad to replace it.</div></div>`;
  h += `<div class="abs row" style="left:0;top:98px;width:800px;height:196px" data-hl="cu-pads">`;
  for (let i = 0; i < 4; i++) {
    const p = E.pads[i];
    h += `<div class="sampcard" style="width:200px"><div style="height:48px;margin:4px;font-size:16px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">${p.id ? esc(TR[p.id].title) : ''}</div>
      ${cb('PAD ' + (i + 1), 'cutrig', i, 200, p.id ? (p.play ? 'on' : '') : 'dis')}${cb('STOP', 'custop', i, 200, p.play ? 'on' : '')}</div>`;
  }
  return h + '</div>' + cuDeckInfo(294, 1) + cuDeckInfo(294, 2);
}
function cuFx() {
  const fx = E.fx, slider = (v, k) => `<div class="slider" data-a="cuslid" data-k="${k}"><div class="bar" style="width:${v * 100}%"></div><div class="hd" style="left:calc(${v * 100}% - 8px)"></div></div>`;
  let h = `<div class="abs row" style="left:0;top:50px;width:800px;height:76px;background:#111823;padding:14px 8px 0">
    ${['DECK 1', 'DECK 2', 'MASTER'].map((t, i) => cb(t, 'fxr', i + 1, 164, fx.route === i + 1 ? 'on' : '')).join('')}
    <div class="row" style="width:290px;height:52px;background:#123363;border:1px solid #416395;margin-left:6px;align-items:center"><span style="width:48px;padding-left:4px">MIX</span><div style="flex:1">${slider(fx.mix, 'mix')}</div></div></div>`;
  h += `<div class="abs row" style="left:0;top:126px;width:800px;height:250px;background:#111823">` + fx.slots.map((s, i) =>
    `<div class="fxcard" style="width:261px"><div class="fxsel" data-a="fxsel" data-v="${i}">${s.n < 0 ? 'SELECT EFFECT...' : FX_NAMES[s.n].toUpperCase()}<span style="font-size:11px">▾</span></div>${slider(s.meta, 'meta' + i)}${cb('ON / OFF', 'fxon', i, 257, s.on ? 'on' : '')}</div>`).join('') + '</div>';
  return h;
}
function cuBottom() {
  let h = `<div class="abs row" style="left:0;top:376px;width:800px;height:52px;background:#000">`;
  for (const n of [1, 2]) {
    if (CU.tab === 'decks' && !CU.settings && CU.loop === n) h += `<div class="row" style="width:400px;align-items:center">${cb('−', 'noop', '', 48)}<canvas data-cv="f:${n}" data-th="cu" data-z="0.5" style="width:304px;height:52px"></canvas>${cb('+', 'noop', '', 48)}</div>`;
    else h += `<canvas data-cv="o:${n}" data-th="cu" style="width:400px;height:52px"></canvas>`;
  }
  h += `</div><div class="abs row" style="left:0;top:428px;width:800px;height:52px;background:#111318" data-hl="cu-transport">`;
  for (const n of [1, 2]) {
    const d = E.decks[n];
    if (CU.tab === 'decks') {
      const w = 66.67;
      h += cb('KEY', 'key', n, w, d.key ? 'on' : '', 52) + cb('Q', 'q', n, w, d.q ? 'on' : '', 52) + cb('SYNC', 'sync', n, w, d.sync ? 'on' : '', 52) + cb('LOOP', 'loop', n, w, CU.loop === n ? 'on' : '', 52) + cb('CUE', 'cue', n, w, '', 52) + cb('▶', 'play', n, w, 'play' + (d.play ? ' on' : ''), 52);
    } else if (CU.tab === 'tracks') h += cb('LOAD', 'load', n, 200, d.play ? 'dis' : '', 52) + cb('CUE', 'cue', n, 200, '', 52);
    else h += cb('CUE', 'cue', n, 200, '', 52) + cb('▶', 'play', n, 200, 'play' + (d.play ? ' on' : ''), 52);
  }
  h += '</div>';
  if (E.scan.on) h += `<div class="abs scanbar" style="left:0;top:428px;width:800px" data-hl="cu-scan"><span style="flex:1;white-space:nowrap;overflow:hidden" data-live="cuscan">Scanning: …</span>
    <div style="width:180px;height:14px;background:#3b4b60;border:1px solid #7fa6d1"><div data-live="cuscanbar" style="height:100%;width:0;background:#7fd0ff"></div></div>${cb('Cancel', 'scancancel', '', 120, 'navy', 48)}</div>`;
  return h;
}
function cuDialogs() {
  if (CU.dlg === 'le') {
    const drive = E.usb.present && E.usb.state !== 'safe';
    return `<div class="abs dlg" style="left:28px;top:20px;width:744px;height:440px" data-hl="cu-ledialog"><div class="tb">Load / Eject</div>
      <div class="box" style="height:290px;font-size:14px">${drive ? `<div data-a="lesel" style="padding:4px 8px;cursor:pointer;${CU.leSel ? 'background:#3264a8' : ''}">MANTACORE · 58.6 GiB · Available<br>/media/pi/MANTACORE<br>Mixxx is not using this drive. This does not mean it is safe to remove.<br>No copy has run yet.</div>` : ''}</div>
      <div style="padding:0 12px;height:26px">${drive ? (CU.leSel ? 'Load opens this drive in the library. Eject is not available on this system. Keep the drive connected.' : 'Select a drive.') : 'No eligible USB drives. Internal copies and system disks are excluded.'}</div>
      <div class="row" style="padding:4px 12px;gap:8px"><span class="qbtn" data-a="noop">Refresh</span>${drive && CU.leSel ? '<span class="qbtn" data-a="leload">Load</span>' : ''}<span class="qbtn${drive ? '' : ' dis'}" data-a="${drive ? 'leeject' : 'noop'}">Eject…</span><span style="flex:1"></span><span class="qbtn ok" data-a="dlgclose">Close</span></div></div>`;
  }
  if (CU.dlg === 'ej') return `<div class="abs dlg" style="left:20px;top:40px;width:760px;height:420px" data-hl="cu-ejdialog"><div class="tb">EJECT — one physical USB disk</div>
      <div style="padding:8px 12px">Eject is not available on this system. Keep the drive connected.</div><div class="box" style="height:280px"></div>
      <div class="row" style="padding:4px 12px;gap:8px"><span class="qbtn" data-a="noop">Refresh</span><span class="qbtn" data-a="noop" data-hl="cu-prepare">Prepare selected disk</span><span style="flex:1"></span><span class="qbtn ok" data-a="dlgclose">Close</span></div></div>`;
  if (CU.dlg === 'arrange') {
    const cols = [['Filename', 1], ['BPM', 1], ['Key', 1], ['Duration', 1], ['Preview', 0], ['Artist', 0], ['Title', 0], ['Album', 0]];
    return `<div class="abs dlg" style="left:140px;top:8px;width:520px;height:430px;background:#1d2635"><div class="tb" style="background:#2b4766">Arrange columns</div>
      <div class="box scrollbox" style="height:266px;background:#121820">${cols.map(([c, on]) => `<div class="row" style="height:48px;align-items:center;gap:10px;padding-left:10px;font-size:17px"><span class="cb${on ? '' : ' off'}"></span>${c}</div>`).join('')}</div>
      <div class="row" style="padding:0 6px">${cb('Up', 'noop', '', 252)}${cb('Down', 'noop', '', 252)}</div>
      <div class="row" style="justify-content:flex-end;padding:4px 10px">${cb('Close', 'dlgclose', '', 140)}</div></div>`;
  }
  return '';
}
function renderCU() {
  let h = cuTop();
  if (CU.tab === 'decks') {
    if (CU.settings) h += cuSettings();
    else {
      if (CU.loop) h += cuLoop(CU.loop);
      else for (const n of [1, 2]) {
        const t = E.decks[n].id ? TR[E.decks[n].id] : null;
        h += `<div class="abs row" style="left:0;top:${50 + (n - 1) * 122}px;width:800px;height:122px"><div class="waveinfo"><span>DECK ${n}</span><span>${t ? `${t.key} (${t.keyName})` : ''}</span></div><canvas data-cv="s:${n}" data-th="cu" style="width:700px;height:122px"></canvas></div>`;
      }
      h += cuDeckInfo(294, 1) + cuDeckInfo(294, 2);
    }
  } else if (CU.tab === 'tracks') h += cuTracks();
  else if (CU.tab === 'sampler') h += cuSampler();
  else if (CU.tab === 'fx') h += cuFx();
  h += cuBottom() + cuDialogs();
  return h;
}

/* ===================== REDESIGN ===================== */
const B = (label, a, v, style = '', cls = '', extra = '') => `<div class="b ${cls}" style="${style}" data-a="${a}" data-v="${v ?? ''}" ${extra}>${label}</div>`;
function usbChip() {
  let cls = 'ok', nm = 'MANTACORE', st = 'READY';
  const inUse = E.usb.opened || [1, 2].some(n => deckUses(n));
  if (E.scan.on && E.set.scanShow === 'icon') { cls = 'busy'; nm = E.usb.present ? 'MANTACORE' : 'LIBRARY'; st = '<span data-live="usbpct">SCAN 0%</span>'; }
  else if (!E.usb.present) { cls = 'none'; nm = 'NO USB'; st = 'PLUG IN A DRIVE'; }
  else if (E.usb.state === 'ejecting') { cls = 'busy'; st = 'EJECTING'; }
  else if (E.usb.state === 'safe') { cls = 'safe'; st = 'SAFE TO REMOVE'; }
  else if (inUse) { cls = 'use'; st = 'IN USE'; }
  return `<div class="usb ${cls}" data-a="usb" data-hl="usbchip" style="margin:0 6px;${RD.ovl === 'media' ? 'border-color:var(--acc)' : ''}">
    <span style="display:inline-flex">${ic('usb', 22)}</span><span style="min-width:0"><div class="nm">${nm}</div><div class="st">${st}</div></span></div>`;
}
function rdTop() {
  const tabLit = k => RD.tab === k && (!RD.ovl || (RD.ovl === 'sources' && k === 'tracks') || (RD.ovl === 'sample' && k === 'sampler'));
  const tabs = [['DECKS', 'decks', 84], ['TRACKS', 'tracks', 90], ['FX', 'fx', 70], ['SAMPLER', 'sampler', 100]]
    .map(([t, k, w]) => `<div class="tab${tabLit(k) ? ' on' : ''}" style="width:${w}px" data-a="tab" data-v="${k}" data-hl="tab-${k}">${t}</div>`).join('');
  return `<div class="top">${tabs}<div style="flex:1"></div>${usbChip()}
    ${B(E.rec.on ? `■ <span data-live="rect">0:00</span>` : '<span style="color:var(--bad)">●</span> REC', 'rec', '', 'height:48px;margin:0 3px', 'recb' + (E.rec.on ? ' on' : ''))}
    ${B(ic('gear', 22), 'gear', '', 'width:48px;height:48px;margin:0 3px', 'icon' + (RD.ovl === 'settings' ? ' on' : ''), 'data-hl="gear"')}
    <div class="cpu">CPU<b>3%</b></div></div>`;
}
function keyChip(t) { return t && t.key ? `<span class="keychip" style="background:${camelot(t.key)}">${t.key}<small>${esc(t.keyName)}</small></span>` : ''; }
function rdDeck(n) {
  const d = E.decks[n], t = d.id ? TR[d.id] : null;
  const chips = (d.onPi ? '<span class="pill pi" data-hl="onpi">ON PI</span>' : '') + (t && t.src === 'usb' && !d.onPi ? '<span class="pill">USB</span>' : '') + (d.sync ? `<span class="pill lit${n}">SYNC</span>` : '') + (d.master ? '<span class="pill lit">MASTER</span>' : '') + (d.pfl ? '<span class="pill lit">PFL</span>' : '');
  return `<div class="deck" data-hl="deck${n}"><div class="l1"><span class="badge s bg${n}">${n}</span><span class="ti">${t ? esc(t.title) : '<span style="color:var(--dim)">Empty deck</span>'}</span><span class="ar">${t ? esc(t.artist) : ''}</span>${chips}</div>
    <div class="l2"><div class="tm" data-a="tm" data-v="${n}"><small>${d.tmode === 'el' ? 'ELAPSED' : 'REMAINING'} · TAP</small><span data-live="tm${n}"></span></div>
      <div class="bpm"><span>${t ? t.bpm.toFixed(1) : '—'}</span><small>BPM</small></div>
      <div class="rate"><small>±${E.set.tempo.replace('%', '')}%</small><span>${d.rate >= 0 ? '+' : ''}${d.rate.toFixed(1)}%</span></div>${keyChip(t)}</div></div>`;
}
const rdInfo = top => `<div class="abs info row" style="left:0;top:${top}px;width:800px;height:72px">${rdDeck(1)}${rdDeck(2)}</div>`;
function rdInfoCompact(top) {
  const one = n => { const d = E.decks[n], t = d.id ? TR[d.id] : null; return `<div class="cdeck" data-hl="deck${n}"><span class="badge s bg${n}">${n}</span><span class="ti">${t ? esc(t.title) : '<span style="color:var(--dim)">Empty deck</span>'}</span>${d.onPi ? '<span class="pill pi">ON PI</span>' : ''}<span class="v" data-live="tm${n}" data-a="tm" data-v="${n}" style="cursor:pointer"></span><span class="v" style="color:var(--dim)">${t ? t.bpm.toFixed(1) : ''}</span>${keyChip(t)}</div>`; };
  return `<div class="abs info row" style="left:0;top:${top}px;width:800px;height:40px">${one(1)}${one(2)}</div>`;
}
function rdOverview(top, hgt) {
  let h = `<div class="abs over row" style="left:0;top:${top}px;width:800px;height:${hgt}px">`;
  for (const n of [1, 2]) {
    const bl = n === 2 ? 'border-left:1px solid var(--ln);' : '';
    if (RD.tab === 'decks' && RD.tool === n && !RD.ovl) h += `<div class="row" style="width:400px;height:${hgt - 1}px;gap:2px;align-items:center;${bl}">${B('−', 'noop', '', `width:48px;height:${hgt - 5}px`)}<canvas data-cv="f:${n}" data-th="rd" data-z="0.5" style="width:298px;height:${hgt - 1}px"></canvas>${B('+', 'noop', '', `width:48px;height:${hgt - 5}px`)}</div>`;
    else h += `<canvas data-cv="o:${n}" data-th="rd" style="width:400px;height:${hgt - 1}px;${bl}"></canvas>`;
  }
  h += '</div>';
  if (E.scan.on && E.set.scanShow === 'bar' && !RD.ovl) h += rdScanStrip(top, hgt);
  return h;
}
function rdScanStrip(top, hgt) {
  return `<div class="scan" style="top:${top}px;height:${hgt}px" data-hl="scanstrip"><span style="color:var(--d1)">${ic('usb', 20)}</span>
    <div style="min-width:0;flex:1"><div style="display:flex;gap:8px;align-items:baseline"><b style="font:700 15px/1 var(--f-cond);letter-spacing:.05em">SCANNING</b><span data-live="scanfile" style="font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis"></span><span data-live="scancount" style="color:var(--dim);font:500 13px/1 var(--f-mono);margin-left:auto;white-space:nowrap"></span></div>
    <div class="pbar" style="margin-top:6px"><i data-live="scanbar" style="width:0"></i></div></div>
    ${B('HIDE', 'shide', '', `width:76px;height:${hgt - 6}px`, '', 'data-hl="scanhide"')}${B('CANCEL', 'scancel', '', `width:86px;height:${hgt - 6}px`)}</div>`;
}
function rdTransport(mode) {
  let h = `<div class="abs trans" style="left:0;top:424px;width:800px;height:56px" data-hl="transport">`;
  for (const n of [1, 2]) {
    const d = E.decks[n], st = 'height:48px;';
    h += '<div class="half">';
    if (mode === 'tracks') {
      const t = d.id ? TR[d.id] : null;
      h += `<div style="width:230px;display:flex;align-items:center;gap:8px;min-width:0">${B(ic('load', 16) + 'LOAD ' + n, 'load', n, st + 'width:104px;flex:none', d.play ? 'dis' : (n === 1 ? 'on1' : 'on2'), `data-hl="load${n}"`)}<span style="font-size:12.5px;line-height:1.2;color:var(--dim);overflow:hidden;max-height:31px">${d.play ? 'Playing · stop to load' : t ? esc(t.title) : 'Empty'}</span></div>`;
      h += B('CUE', 'cue', n, st + 'flex:1', 'cue');
    } else {
      h += B(ic('lock', 15) + 'KEY', 'key', n, st + 'width:48px;font-size:13px;flex-direction:column;gap:2px', d.key ? 'on' + n : '');
      h += B('Q', 'q', n, st + 'width:48px', d.q ? 'on' + n : '');
      h += B('SYNC', 'sync', n, st + 'width:60px', d.sync ? 'on' + n : '');
      h += B('LOOP', 'loop', n, st + 'width:60px', RD.tool === n && RD.tab === 'decks' ? 'on' : (d.loop ? 'on' + n : ''), `data-hl="loopbtn${n}"`);
      h += B('CUE', 'cue', n, st + 'width:76px', 'cue');
      h += B(ic('play', 24), 'play', n, st + 'flex:1', 'play' + (d.play ? ' on' : ''));
    }
    h += '</div>';
  }
  return h + '</div>';
}
function rdTool(n) {
  const d = E.decks[n], beat = d.id ? beatLen(d.id) : 0.5, tab = RD.toolTab;
  const tabB = (k, l) => B(l, 'tt', k, 'width:100px;height:44px', tab === k ? 'on' + n : '');
  let body = '';
  const g = 'display:grid;gap:6px;';
  if (tab === 'loop') {
    const sz = ([l, v]) => B(l, 'bl', v, 'height:52px;font-size:18px', d.loop && Math.abs(d.loop.l - v * beat) < 1e-6 ? 'on' + n : '');
    body = `<div style="${g}grid-template-columns:repeat(6,1fr)">${LOOPS.map(sz).join('')}</div>
      <div style="${g}grid-template-columns:repeat(4,1fr);margin-top:6px">${B('½', 'lhalf', n, 'height:52px;font-size:20px')}${B('×2', 'ldouble', n, 'height:52px;font-size:20px')}${B('EXIT', 'lexit', n, 'height:52px', d.loop ? 'on' : '')}${B('RELOOP', 'lreloop', n, 'height:52px', d.loop ? 'dis' : '')}</div>`;
  } else if (tab === 'jump') {
    const js = [1, 2, 4, 8, 16, 32];
    body = `<div style="${g}grid-template-columns:110px repeat(6,1fr)"><div class="lbl" style="display:flex;align-items:center">◀ BACK</div>${js.map(v => B('◀ ' + v, 'bj', -v, 'height:56px;font-size:18px')).join('')}
      <div class="lbl" style="display:flex;align-items:center">FORWARD ▶</div>${js.map(v => B(v + ' ▶', 'bj', v, 'height:56px;font-size:18px')).join('')}</div>
      <div style="color:var(--dim);font-size:13px;margin-top:10px">Beats. Quantize keeps the jump on the grid. Not on the Starlight; the XDJ-AZ has it on its pads.</div>`;
  } else {
    const cues = d.id ? TR[d.id].cues : [];
    body = `<div style="${g}grid-template-columns:repeat(4,1fr)">${[1, 2, 3, 4, 5, 6, 7, 8].map(k => {
      const c = cues.find(x => x.n === k);
      return `<div class="b" data-a="hc" data-v="${k}" style="height:70px;flex-direction:column;align-items:flex-start;padding:0 10px;${c ? `background:${c.color}22;border-color:${c.color}` : 'border-style:dashed'}"><span style="font-size:18px;color:${c ? c.color : 'var(--dim)'}">${k}</span><span style="font:500 12px/1 var(--f-ui);text-transform:none;letter-spacing:0;color:var(--dim)">${c ? fmtLen(c.pos) + (RD.clear ? ' · tap to clear' : '') : 'Tap to set'}</span></div>`;
    }).join('')}</div><div style="color:var(--dim);font-size:13px;margin-top:8px">Pads 1–4 match the Starlight's hot cue pads. 5–8 are screen only.</div>`;
  }
  return `<div class="abs panel" style="left:0;top:48px;width:800px;height:256px;padding:4px 8px" data-hl="toolpanel">
    <div class="row" style="height:48px;align-items:center;gap:6px"><span class="badge bg${n}">${n}</span><b style="font:700 18px/1 var(--f-cond);letter-spacing:.06em;margin-right:8px">DECK ${n}</b>
      ${tabB('loop', 'LOOP')}${tabB('jump', 'JUMP')}${tabB('cues', 'CUES')}<div style="flex:1"></div>
      ${tab === 'cues' ? B('CLEAR', 'hclear', '', 'width:90px;height:44px', RD.clear ? 'on' : '') : ''}${B(ic('x', 18) + 'CLOSE', 'tclose', '', 'width:110px;height:44px')}</div>
    <div style="margin-top:6px">${body}</div></div>`;
}
function rdWaves() {
  let h = '';
  for (const n of [1, 2]) {
    const d = E.decks[n], t = d.id ? TR[d.id] : null;
    h += `<div class="abs row" style="left:0;top:${48 + (n - 1) * 128}px;width:800px;height:128px;${n === 1 ? 'border-bottom:1px solid var(--ln)' : ''}">
      <div class="wcol" style="width:92px"><span class="badge bg${n}">${n}</span>${keyChip(t)}<div style="display:flex;gap:4px">${d.key ? '<span class="pill lit">MT</span>' : '<span class="pill">MT</span>'}${d.q ? '<span class="pill lit">Q</span>' : '<span class="pill">Q</span>'}</div></div>
      <div style="position:relative;width:708px;height:${n === 1 ? 127 : 128}px"><canvas data-cv="s:${n}" data-th="rd" style="width:708px;height:100%"></canvas><div style="position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--d${n})"></div></div></div>`;
  }
  return h;
}
function listOf(key) {
  const [src, kind, name] = key.split(':');
  if (src === 'pi' && kind === 'tracks') return { crumb: ['This Pi', 'Tracks'], ids: PI.filter(id => id !== 'p12') };
  if (src === 'pi' && kind === 'pl') { const p = PI_PL.find(x => x.name === name); return { crumb: ['This Pi', 'Playlists', name], ids: p.ids }; }
  if (src === 'pi' && kind === 'cr') { const p = PI_CR.find(x => x.name === name); return { crumb: ['This Pi', 'Crates', name], ids: p.ids }; }
  if (src === 'usb' && kind === 'all') return { crumb: ['MANTACORE', 'All tracks'], ids: USB };
  if (src === 'usb' && kind === 'pl') { const p = USB_PL.find(x => x.name === name); return { crumb: ['MANTACORE', 'Playlists', name], ids: p.ids }; }
  if (src === 'rec') return { crumb: ['Recordings'], ids: REC };
  if (src === 'hist') return { crumb: ['History', name || 'Today'], ids: ['p2', 'p5', 'p4'] };
  if (src === 'samples') return { crumb: ['Samples'], ids: SM };
  return { crumb: ['This Pi', 'Tracks'], ids: PI };
}
function rdTracks() {
  let L = listOf(RD.list);
  if (L.crumb[0] === 'MANTACORE' && !usbAvailable()) { RD.list = 'pi:tracks'; L = listOf(RD.list); }
  const crumb = L.crumb.map((c, i) => i === L.crumb.length - 1 ? `<b>${esc(c)}</b>` : esc(c)).join(' › ');
  let h = `<div class="abs row" style="left:0;top:48px;width:800px;height:48px;align-items:center;gap:6px;padding:0;background:var(--p1);border-bottom:1px solid var(--ln)">
    ${B(ic('menu', 24), 'menu', '', 'width:48px;height:48px;border-radius:0 6px 6px 0', 'icon ghost', 'data-hl="hamburger" aria-label="Sources"')}
    <div class="crumb" style="width:220px" data-hl="crumb">${L.crumb[0] === 'MANTACORE' ? `<span style="color:var(--go)">${ic('usb', 14)}</span> ` : ''}${crumb}</div>
    <div style="position:relative;flex:1"><span style="position:absolute;left:10px;top:10px;color:var(--dim)">${ic('search', 20)}</span><input class="srch" id="rd-search" placeholder="Search ${fmtN(L.ids.length)} tracks" aria-label="Search tracks"></div>
    ${B(ic('pen', 22), 'pen', '', 'width:48px;height:48px;border-radius:6px 0 0 6px', 'icon' + (RD.sheet === 'actions' ? ' on' : ''), 'data-hl="pen" aria-label="Actions"')}</div>`;
  const rows = L.ids.map(id => {
    const t = TR[id], ok = trackUsable(id);
    return `<div class="lrow${RD.sel === id ? ' sel' : ''}" data-a="row" data-v="${id}" style="${ok ? '' : 'opacity:.35'}">
      <div style="flex:1;min-width:0;font-weight:700;padding-left:12px">${esc(t.title)}</div><div style="width:136px;color:var(--dim)">${esc(t.artist)}</div>
      <div class="num" style="width:66px">${t.bpm ? t.bpm.toFixed(1) : ''}</div><div style="width:90px">${t.key ? `${t.key} ${esc(t.keyName)}` : ''}</div><div class="num" style="width:64px;color:var(--dim)">${fmtLen(t.dur)}</div></div>`;
  }).join('');
  h += `<div class="abs sc" data-keep="rdlist" style="left:0;top:96px;width:800px;height:260px" data-hl="tracklist">
    <div class="lrow hd"><div style="flex:1;padding-left:12px">TITLE</div><div style="width:136px">ARTIST</div><div style="width:66px;text-align:right">BPM</div><div style="width:90px">KEY</div><div style="width:64px;text-align:right">TIME</div></div>${rows}</div>`;
  h += rdTitles(356) + rdOverview(384, 40) + rdTransport('tracks');
  if (RD.sheet === 'actions') {
    h += `<div class="scrim" data-a="shclose" style="background:rgba(3,5,8,.35)"></div><div class="menu" style="right:4px;top:96px;width:300px" data-hl="actionsmenu">
      <div class="mi" data-a="act" data-v="1"><span class="badge s bg1">1</span>Load to Deck 1</div><div class="mi" data-a="act" data-v="2"><span class="badge s bg2">2</span>Load to Deck 2</div>
      <div class="mi" data-a="act" data-v="pad">${ic('wave', 20)}Load to a sampler pad…</div><div class="mi" data-a="act" data-v="arrange">${ic('list', 20)}Arrange columns…</div>
      <div class="mi" data-a="act" data-v="full" style="color:var(--dim)">${ic('more', 20)}Full Mixxx menu<span style="margin-left:auto">${ic('chev', 18)}</span></div></div>`;
  }
  return h;
}
const SRC = {
  usb: { name: 'MANTACORE', icon: 'usb', sub: 'USB · rekordbox · 58.6 GB' },
  pi: { name: 'This Pi', icon: 'pi', sub: 'Tracks · Playlists · Crates' },
  rec: { name: 'Recordings', icon: 'mic', sub: 'Your recorded sets' },
  hist: { name: 'History', icon: 'clock', sub: 'Played tracks by date' },
  folders: { name: 'Folders', icon: 'folder', sub: 'Browse files and drives' },
  samples: { name: 'Samples', icon: 'wave', sub: `${SM.length} sounds` },
};
function srcRows() {
  const p = RD.srcPath, s = RD.srcSel;
  const nav = (icn, name, cnt, v) => `<div class="nrow" data-a="snav" data-v="${esc(v)}"><span style="color:var(--dim)">${ic(icn, 22)}</span><span class="grow">${esc(name)}</span><span class="cnt">${cnt}</span>${ic('chev', 18)}</div>`;
  const open = (icn, name, cnt, key) => `<div class="nrow" data-a="sopen" data-v="${esc(key)}"><span style="color:var(--acc)">${ic(icn, 22)}</span><span class="grow">${esc(name)}</span><span class="cnt">${cnt}</span><span class="b" style="height:36px;padding:0 10px;font-size:13px">OPEN</span></div>`;
  if (s === 'usb') {
    if (!p.length) return nav('list', 'Playlists', USB_PL.length, 'Playlists') + open('list', 'All tracks', '3,050', 'usb:all') + nav('folder', 'Folders', '', 'Folders') + nav('clock', 'rekordbox history', '9', 'History');
    if (p[0] === 'Playlists') return USB_PL.map(x => open('list', x.name, x.n, 'usb:pl:' + x.name)).join('');
    if (p[0] === 'Folders') return ['Contents', 'PIONEER', 'Samples'].map(f => open('folder', f, '', 'usb:all')).join('');
    return ['2026-11-16', '2026-11-09', '2026-11-02'].map(d => open('clock', d, '', 'hist:day:' + d)).join('');
  }
  if (s === 'pi') {
    if (!p.length) return open('list', 'Tracks', '1,240', 'pi:tracks') + nav('list', 'Playlists', PI_PL.length, 'Playlists') + nav('crate', 'Crates', PI_CR.length, 'Crates') + nav('disc', 'Auto DJ', '0', 'Auto DJ');
    if (p[0] === 'Playlists') return PI_PL.map(x => open('list', x.name, x.n, 'pi:pl:' + x.name)).join('');
    if (p[0] === 'Crates') return PI_CR.map(x => open('crate', x.name, x.n, 'pi:cr:' + x.name)).join('');
    return '<div style="padding:16px;color:var(--dim)">Auto DJ is empty.</div>';
  }
  if (s === 'rec') return open('mic', '2026-11-17_00h09m13s', '30:40', 'rec:all') + open('mic', '2026-11-15_22h41m02s', '1:02:11', 'rec:all');
  if (s === 'hist') return ['Today', '2026-11-16', '2026-11-15'].map(d => open('clock', d, '', 'hist:day:' + d)).join('');
  if (s === 'samples') return open('wave', 'All samples', SM.length, 'samples');
  if (p.length) return open('folder', 'Tracks in ' + p[p.length - 1], '', p[0] === 'MANTACORE' ? 'usb:all' : 'pi:tracks') + nav('folder', 'Subfolder', '', 'Subfolder');
  return nav('folder', '/home/pi/Music', '', 'Music') + nav('folder', '/home/pi/Music/Backup', '', 'Backup') + nav('folder', '/home/pi/Samples', '', 'Samples') + (usbAvailable() ? nav('usb', '/media/pi/MANTACORE', '', 'MANTACORE') : '');
}
function rdSources() {
  let order = RD.srcOrder.filter(k => (k !== 'usb' || usbAvailable()) && !RD.srcHidden[k]);
  if (!order.length) { RD.srcHidden = {}; order = RD.srcOrder.filter(k => k !== 'usb' || usbAvailable()); }
  if (!order.includes(RD.srcSel)) RD.srcSel = order[0];
  const tiles = order.map(k => { const s = SRC[k]; return `<div class="tile${RD.srcSel === k && !RD.edit ? ' sel' : ''}" data-a="stile" data-v="${k}"><span style="color:${k === 'usb' ? 'var(--go)' : 'var(--dim)'}">${ic(s.icon, 26)}</span><div style="min-width:0"><div class="tn">${s.name}${RD.srcStart === k ? ' <span style="color:var(--acc)">★</span>' : ''}</div><div class="ts">${s.sub}</div></div><span style="margin-left:auto;color:var(--dim)">${ic('chev', 18)}</span></div>`; }).join('');
  const crumb = [SRC[RD.srcSel].name, ...RD.srcPath].map((c, i, a) => i === a.length - 1 ? `<b>${esc(c)}</b>` : esc(c)).join(' › ');
  let right;
  if (RD.edit) {
    right = `<div style="padding:12px 14px" class="lbl">Show, order, and ★ where Tracks starts</div><div class="sc" style="height:328px">` + RD.srcOrder.map((k, i) => `<div class="nrow" style="cursor:default;gap:6px;padding:0 8px"><span class="grow">${SRC[k].name}${k === 'usb' ? ' <span style="color:var(--dim);font-size:13px">(each drive)</span>' : ''}</span>
      ${B(ic('up', 18), 'sup', i, 'width:48px;height:48px', i ? 'icon' : 'icon dis')}${B(ic('down', 18), 'sdown', i, 'width:48px;height:48px', i < RD.srcOrder.length - 1 ? 'icon' : 'icon dis')}${B('★', 'sstart', k, 'width:48px;height:48px;font-size:20px', RD.srcStart === k ? 'on' : (k === 'usb' ? 'dis' : ''))}<div data-a="svis" data-v="${k}" style="width:72px;height:48px;display:flex;align-items:center;justify-content:center;cursor:pointer"><div class="tog${RD.srcHidden[k] ? '' : ' on'}"></div></div></div>`).join('') + '</div>';
  } else {
    right = `<div class="row" style="height:48px;align-items:center;gap:8px;padding:0 10px 0 4px;border-bottom:1px solid var(--ln)">${RD.srcPath.length ? B(ic('back', 18) + 'BACK', 'sback', '', 'width:96px;height:48px') : ''}<div class="crumb">${crumb}</div></div>
      <div class="sc" style="height:336px">${srcRows()}</div>`;
  }
  return `<div class="ovl" data-hl="sources"><div class="hdr" style="height:48px;padding:0 0 0 0;gap:10px">
      ${B(ic('x', 24), 'sx', '', 'width:48px;height:48px;border-radius:0 6px 6px 0', 'icon on', 'data-hl="hamburger" aria-label="Close sources"')}<h2>Sources</h2>
      <span class="crumb">${RD.srcReturn === 'sample' ? 'Pick a list to load samples from.' : 'Pick a source, then a list. OPEN shows it in Tracks.'}</span><div style="flex:1"></div>
      ${B(RD.edit ? ic('check', 18) + 'DONE' : 'EDIT LIST', 'sedit', '', 'width:128px;height:48px;border-radius:6px 0 0 6px', RD.edit ? 'on' : '', 'data-hl="sedit"')}</div>
    <div class="abs sc" style="left:0;top:48px;width:264px;height:384px;border-right:1px solid var(--ln);background:var(--p1)" data-hl="sourcesrail">${tiles}</div>
    <div class="abs" style="left:264px;top:48px;width:536px;height:384px" data-hl="sourcespane">${right}</div></div>`;
}
function rdMedia() {
  let left;
  if (!E.usb.present) left = `<div class="card2" style="margin:14px;padding:22px;text-align:center;color:var(--dim)"><div>${ic('usb', 40)}</div><div style="font:700 20px/1.3 var(--f-cond);color:var(--tx);margin-top:6px">No USB drive</div>Plug in a drive. A small ping at the bottom asks whether to load it.</div>`;
  else {
    const u = usage(), safe = E.usb.state === 'safe', ej = E.usb.state === 'ejecting', block = u.some(x => x.block);
    const pill = safe ? '<span class="pill pi" style="height:26px;font-size:13px">SAFE TO REMOVE</span>' : ej ? '<span class="pill" style="height:26px;color:var(--warn);border-color:var(--warn)">EJECTING</span>' : (E.usb.opened || u.length) ? '<span class="pill" style="height:26px;color:#9fd0ff;border-color:#4aa8ff">IN USE</span>' : '<span class="pill" style="height:26px;color:var(--go);border-color:var(--go)">READY</span>';
    const uses = safe ? '<div style="color:#b9f5d2;font-size:16px">You can pull the drive out now.</div>' : u.length ? u.map(x => `<div style="font-size:14.5px;color:${x.block ? 'var(--warn)' : 'var(--dim)'}">${x.kind === 'deck' ? `<span class="badge s bg${x.n}" style="display:inline-flex;width:18px;height:18px;font-size:12px">${x.n}</span> Deck ${x.n} ${x.play ? 'is playing' : 'holds'} “${esc(short(x.title))}”${x.block ? ' straight from the drive' : ''}` : `Pad ${x.n} holds “${esc(short(x.title))}”`}</div>`).join('') : `<div style="font-size:14.5px;color:var(--dim)">${E.usb.opened ? 'Open in Sources. Nothing on the decks or pads comes from it.' : 'Not open yet. Mixxx has not read it.'}</div>`;
    left = `<div class="card2" style="margin:12px;padding:14px;display:flex;flex-direction:column;gap:10px" data-hl="mediacard">
      <div class="row" style="gap:12px;align-items:center"><span style="color:${safe ? 'var(--go)' : 'var(--tx)'}">${ic('usb', 40)}</span><div style="flex:1;min-width:0"><div style="font:700 24px/1 var(--f-cond);letter-spacing:.03em">MANTACORE</div><div style="color:var(--dim);font-size:13.5px;margin-top:4px">58.6 GB · rekordbox export found · read-write</div></div>${pill}</div>
      <div class="row" style="gap:6px">${B(ic('eject', 22) + 'EJECT', 'eject', '', 'width:176px;height:56px;font-size:19px', safe || ej || block ? 'dis' : 'pri', 'data-hl="ejectbtn"')}
        ${B(ic('list', 18) + (E.usb.opened ? 'BROWSE' : 'OPEN'), 'mbrowse', '', 'flex:1;height:56px', safe || ej ? 'dis' : '', 'data-hl="browsebtn"')}${B(ic('copy', 18) + 'COPY TO PI', 'mcopy', '', 'flex:1.2;height:56px', safe || ej ? 'dis' : '', 'data-hl="copytopi"')}</div>
      <div style="display:flex;flex-direction:column;gap:5px;min-height:46px">${uses}</div>${block ? '<div style="font-size:13px;color:var(--warn)">Eject waits until that deck stops: its track was too big for Pi memory.</div>' : ''}</div>
      <div style="padding:0 14px;color:var(--dim);font-size:13px;line-height:1.45">The drive mounted by itself. Mixxx reads it only after LOAD on the plug-in ping, OPEN here, or a pick in Sources. EJECT keeps every track or sample in use playing from its copy in Pi memory, then unmounts the drive.</div>`;
  }
  const ho = [];
  for (const n of [1, 2]) { const d = E.decks[n]; if (d.onPi) ho.push(`<div class="nrow" style="height:52px;cursor:default;padding:0 10px"><span class="badge s bg${n}">${n}</span><span class="grow" style="font-size:14.5px">${esc(TR[d.id].title)}</span><span class="pill pi">ON PI</span></div>`); }
  E.pads.forEach((p, i) => { if (p.onPi) ho.push(`<div class="nrow" style="height:52px;cursor:default;padding:0 10px"><span class="pill">PAD ${i + 1}</span><span class="grow" style="font-size:14.5px">${esc(TR[p.id].title)}</span><span class="pill pi">ON PI</span></div>`); });
  const right = `<div class="lbl" style="padding:14px 12px 8px">Playing from Pi memory</div>
    ${ho.length ? ho.join('') : '<div style="padding:0 12px;color:var(--dim);font-size:13.5px">Nothing yet. A track loaded from a drive is copied to Pi memory as it loads, so after EJECT it keeps playing here.</div>'}
    <div style="padding:10px 12px 0;color:var(--dim);font-size:12.5px;line-height:1.4">Each copy is deleted when its deck or pad loads something else or is cleared, and at every start.</div>
    ${E.cleaned.length ? `<div class="lbl" style="padding:12px 12px 6px">Cleaned out</div>${E.cleaned.slice(0, 3).map(c => `<div style="padding:2px 12px;font-size:13px;color:var(--dim)">✓ ${esc(short(c))}</div>`).join('')}` : ''}`;
  return `<div class="ovl" data-hl="media"><div class="hdr" style="height:48px;padding:0 6px 0 0;gap:10px">${B(ic('x', 24), 'mx', '', 'width:48px;height:48px;border-radius:0 6px 6px 0', 'icon')}<h2>USB &amp; media</h2><span class="crumb">Drives are ready when plugged in. Eject before you pull one out.</span></div>
    <div class="abs" style="left:0;top:48px;width:520px;height:384px">${left}</div>
    <div class="abs sc" style="left:520px;top:48px;width:280px;height:384px;border-left:1px solid var(--ln);background:var(--p1)" data-hl="handover">${right}</div></div>`;
}
function rdEjectSheet() {
  const ej = E.usb.state === 'ejecting' || E.usb.state === 'safe';
  let body;
  if (!ej) {
    const u = usage(), block = u.some(x => x.block);
    const what = x => x.kind === 'pad' ? ['stays loaded from its Pi copy', 'var(--go)'] : x.block ? ['plays straight from the drive: stop it first', 'var(--warn)'] : x.unload ? ['will be unloaded', 'var(--dim)'] : [x.play ? 'keeps playing from its Pi copy' : 'stays loaded from its Pi copy', 'var(--go)'];
    body = `<div style="font:700 24px/1.1 var(--f-cond);letter-spacing:.02em">Eject MANTACORE?</div>
      <div style="color:var(--dim);margin:6px 0 10px">${u.length ? 'What uses the drive, and what happens to it:' : 'Nothing on the decks or pads comes from this drive.'}</div>
      <div style="display:flex;flex-direction:column;gap:6px;min-height:110px">${u.map(x => { const [w, c] = what(x); return `<div class="row" style="align-items:center;gap:10px;height:34px;font-size:15.5px">${x.kind === 'deck' ? `<span class="badge s bg${x.n}">${x.n}</span><span style="flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">Deck ${x.n} · ${esc(x.title)}</span>` : `<span class="pill">PAD ${x.n}</span><span style="flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(x.title)}</span>`}<span style="color:${c};white-space:nowrap">${w}</span></div>`; }).join('')}</div>
      <div class="row" style="gap:8px;justify-content:flex-end;margin-top:10px">${B('CANCEL', 'shclose', '', 'width:140px;height:56px')}${B(ic('eject', 22) + 'EJECT', 'ejgo', '', 'width:200px;height:56px;font-size:19px', block ? 'dis' : 'pri')}</div>`;
  } else {
    const n = usageCountCache;
    const steps = ['Stop new reads from MANTACORE', `Keep ${n} item${n === 1 ? '' : 's'} playing from their Pi copies`, 'Close Mixxx’s files on the drive', 'Unmount and check'];
    const st = E.usb.state === 'safe' ? 4 : E.eject.step;
    body = `<div style="font:700 24px/1.1 var(--f-cond)">${E.usb.state === 'safe' ? '<span style="color:var(--go)">Safe to remove MANTACORE</span>' : 'Ejecting MANTACORE…'}</div><div style="margin:12px 0">${steps.map((s, i) => `<div class="step${i < st ? ' done' : i === st ? ' now' : ''}"><span class="dot">${i < st ? '✓' : ''}</span>${s}</div>`).join('')}</div>
      <div class="row" style="justify-content:flex-end">${B('DONE', 'shclose', '', 'width:160px;height:56px', E.usb.state === 'safe' ? 'pri' : 'dis')}</div>`;
  }
  return `<div class="scrim"></div><div class="sheet" style="left:110px;top:64px;width:580px;padding:18px 20px" data-hl="ejectsheet">${body}</div>`;
}
let usageCountCache = 0;
function rdSampler() {
  let h = `<div class="abs row" style="left:0;top:48px;width:800px;height:48px;align-items:center;gap:10px;padding:0 6px 0 0;background:var(--p1);border-bottom:1px solid var(--ln)">
    ${B(ic('plus', 20) + 'LOAD SAMPLE', 'loadsample', '', 'width:196px;height:48px;border-radius:0 6px 6px 0', 'on', 'data-hl="loadsample"')}<span style="color:var(--dim);font-size:13.5px;display:flex;align-items:center;gap:5px"><span style="color:var(--go)">${ic('check', 16)}</span>Bank saved</span>
    <div style="flex:1"></div><span style="color:var(--dim);font-size:12.5px;text-align:right;line-height:1.25">Starlight SAMPLER mode:<br>deck A pads 1–4 · deck B pads 5–8</span></div>
    <div class="abs" style="left:0;top:96px;width:800px;height:208px;display:grid;grid-template-columns:repeat(4,200px);grid-template-rows:104px 104px" data-hl="pads">`;
  E.pads.forEach((p, i) => {
    const lab = `<span class="badge s" style="background:${i < 4 ? 'var(--d1)' : 'var(--d2)'}">${i + 1}</span>${i < 4 ? 'A' : 'B'}${(i % 4) + 1}`;
    const box = 'border:0;border-radius:0;box-shadow:inset 0 0 0 1px var(--ln);';
    if (!p.id) h += `<div class="pad empty" style="${box}" data-hl="pad${i + 1}"><div class="tap" data-a="pempty" data-v="${i}"><div class="pn">${lab}</div><div class="sn" style="color:var(--dim);display:flex;align-items:center;gap:6px;-webkit-line-clamp:1">${ic('plus', 18)}Empty · tap to load</div></div></div>`;
    else {
      const t = TR[p.id];
      h += `<div class="pad${p.play ? ' playing' : ''}" style="${box}${p.play ? 'box-shadow:inset 0 0 0 2px var(--acc);background:#22301a;' : ''}" data-hl="pad${i + 1}"><div class="tap" data-a="ptrig" data-v="${i}" style="flex:none;height:56px"><div class="pn">${lab}${p.onPi ? '<span class="pill pi" style="height:16px;font-size:10px">ON PI</span>' : ''}<span style="margin-left:auto;font:500 12px/1 var(--f-mono)">${fmtLen(t.dur)}</span></div><div class="sn" style="-webkit-line-clamp:1;white-space:nowrap;text-overflow:ellipsis;display:block">${esc(t.title)}</div></div>
        <div class="strip" style="height:48px;padding:0 4px">${B(ic('stop', 14) + 'STOP', 'pstop', i, 'flex:1;height:48px', p.play ? '' : 'dis')}${B(ic('x', 16) + 'CLEAR', 'pclear', i, 'flex:1;height:48px', p.play ? 'dis' : '')}</div></div>`;
    }
  });
  return h + '</div>' + rdInfo(304) + rdOverview(376, 48) + rdTransport();
}
function rdSampleBrowser() {
  const s = RD.sample;
  if (s.src && s.src.startsWith('usb') && !usbAvailable()) s.src = 'samples';
  const ids = s.src === 'samples' ? SM : s.src === 'tracks' ? PI.filter(id => id !== 'p12') : listOf(s.src).ids;
  const lab = s.src === 'samples' ? 'Samples folder' : s.src === 'tracks' ? 'This Pi › Tracks' : listOf(s.src).crumb.join(' › ');
  const rows = ids.map(id => { const t = TR[id], ok = trackUsable(id); return `<div class="lrow${s.sel === id ? ' sel' : ''}" style="${ok ? '' : 'opacity:.35'}" data-a="srow" data-v="${id}"><div style="flex:1;min-width:0;font-weight:700;padding-left:12px">${esc(t.title)}</div><div class="num" style="width:70px">${t.bpm ? t.bpm.toFixed(1) : ''}</div><div class="num" style="width:80px;color:var(--dim)">${fmtLen(t.dur)}</div></div>`; }).join('');
  const chip = (k, l) => B(l, 'ssrc', k, 'width:150px;height:48px', (k === s.src || (k === 'sources' && !['samples', 'tracks'].includes(s.src))) ? 'on' : '');
  return `<div class="ovl" data-hl="samplebrowser"><div class="hdr" style="height:48px;padding:0 6px 0 0;gap:8px">${B(ic('x', 24), 'sbx', '', 'width:48px;height:48px;border-radius:0 6px 6px 0', 'icon')}<h2>Load sample</h2><span class="crumb">${s.pad != null ? `For pad ${s.pad + 1}` : 'Pick a sound, then a pad'}</span><div style="flex:1"></div>
      <div style="position:relative;width:250px"><span style="position:absolute;left:10px;top:10px;color:var(--dim)">${ic('search', 20)}</span><input class="srch" id="rd-ssearch" placeholder="Search" aria-label="Search sounds"></div></div>
    <div class="row" style="height:56px;align-items:center;gap:6px;padding:0 8px;border-bottom:1px solid var(--ln)">${chip('samples', 'SAMPLES')}${chip('tracks', 'TRACKS')}${chip('sources', 'SOURCES…')}<span class="crumb" style="margin-left:8px">${esc(lab)}</span></div>
    <div class="sc" data-keep="rdsamples" style="height:272px"><div class="lrow hd"><div style="flex:1;padding-left:12px">TITLE</div><div style="width:70px;text-align:right">BPM</div><div style="width:80px;text-align:right">TIME</div></div>${rows}</div>
    <div class="row" style="height:56px;align-items:center;gap:10px;padding:0 4px 0 12px;border-top:1px solid var(--ln);background:var(--p1)"><div style="flex:1;color:var(--dim);font-size:13.5px">Tap a sound, then load it to a pad.</div>
      ${B(ic('load', 20) + (s.pad != null ? `LOAD TO PAD ${s.pad + 1}` : 'LOAD TO PAD…'), 'sload', '', 'width:262px;height:48px;font-size:18px', s.sel && trackUsable(s.sel) ? 'pri' : 'dis', 'data-hl="loadtopad"')}</div></div>`;
}
function rdChoosePad() {
  const pads = E.pads.map((p, i) => `<div class="b${p.play ? ' dis' : ''}" data-a="${p.play ? 'noop' : 'cpad'}" data-v="${i}" style="height:96px;flex-direction:column;align-items:flex-start;justify-content:center;padding:0 12px;gap:6px">
      <span style="display:flex;align-items:center;gap:6px"><span class="badge s" style="background:${i < 4 ? 'var(--d1)' : 'var(--d2)'}">${i + 1}</span><span style="color:var(--dim);font-size:13px">${i < 4 ? 'A' : 'B'}${(i % 4) + 1}</span></span>
      <span style="font:500 13px/1.2 var(--f-ui);text-transform:none;letter-spacing:0;color:${p.id ? 'var(--tx)' : 'var(--dim)'};white-space:normal;text-align:left">${p.play ? 'Playing · stop it first' : p.id ? esc(short(TR[p.id].title)) : 'Empty'}</span></div>`).join('');
  return `<div class="scrim" data-a="shclose"></div><div class="sheet" style="left:40px;top:52px;width:720px;padding:16px 18px" data-hl="choosepad">
    <div class="row" style="align-items:center;gap:10px;margin-bottom:12px"><div style="font:700 22px/1.1 var(--f-cond);flex:1">Load to which pad?</div>${B('CANCEL', 'shclose', '', 'width:120px;height:48px')}</div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">${pads}</div>
    <div style="color:var(--dim);font-size:13px;margin-top:10px">Pads 1–4 play from the Starlight's deck A pads in SAMPLER mode, 5–8 from deck B. A playing pad is off. The bank saves as soon as a pad changes.</div></div>`;
}
function rdSettings() {
  const s = E.set, sec = RD.set;
  const seg = (k, opts) => `<div class="seg2">${opts.map(([v, l]) => B(l || v, 'opt', k + ':' + v, 'height:48px;padding:0 14px;min-width:72px', s[k] === v ? 'on' : '')).join('')}</div>`;
  const row = (lab, sub, ctl, hl) => `<div style="display:flex;align-items:center;gap:12px;padding:8px 14px;border-bottom:1px solid #18202b;min-height:66px" ${hl ? `data-hl="${hl}"` : ''}><div style="width:190px;flex:none"><div style="font-weight:700">${lab}</div>${sub ? `<div style="color:var(--dim);font-size:12.5px;margin-top:3px;line-height:1.3">${sub}</div>` : ''}</div><div style="min-width:0">${ctl}</div></div>`;
  let body = '';
  if (sec === 'playback') body = row('Key lock engine', '', seg('keylock', [['ST'], ['RB Fast', 'RB FAST'], ['RB Fine', 'RB FINE']])) + row('Audio buffer', 'Frames', seg('buffer', [['256'], ['512'], ['1024']])) + row('Tempo range', 'Fader range ±', seg('tempo', [['6%'], ['8%'], ['10%'], ['16%'], ['24%']])) + row('Quantize', '', `<div class="seg2">${B('DECK 1', 'opt', 'q1:t', 'height:48px;width:110px', s.q1 ? 'on1' : '')}${B('DECK 2', 'opt', 'q2:t', 'height:48px;width:110px', s.q2 ? 'on2' : '')}</div>`) + row('Split cue', 'Headphones: cue left, master right', B(s.split ? 'ON' : 'OFF', 'opt', 'split:t', 'height:48px;width:96px', s.split ? 'on' : ''));
  else if (sec === 'interface') body = row('Desktop bar', 'Desktop · Mixxx · Speaker · Settings', seg('deskbar', [['hidden', 'HIDDEN'], ['shown', 'SHOWN']])) + row('Deck time', 'Tap the time on a deck to switch', seg('time', [['elapsed', 'ELAPSED'], ['remaining', 'REMAINING']]));
  else if (sec === 'media') body = row('Scan bar', 'Hidden: the % shows on the USB chip', seg('scanShow', [['bar', 'SHOW'], ['icon', 'HIDE']]), 'set-scan') + row('RAM cache', 'MB. Also the room for handover copies. Next launch.', seg('cache', [['OFF'], ['512'], ['1024']]), 'set-cache') + row('Eject', 'Approved 17 Nov: system eject', '<span class="pill" style="height:30px;font-size:13px;color:var(--go);border-color:var(--go)">ON</span>', 'set-eject') + row('Plugging in a drive', 'A small ping at the bottom: LOAD or DISMISS', '<span style="color:var(--dim)">Always</span>');
  else body = row('Waveform FPS', '', seg('fps', [['30'], ['45'], ['60']])) + row('Read ahead', 'Next launch', seg('ahead', [['2'], ['8'], ['24']])) + row('Mixxx preferences', 'Audio routing, controllers', B('OPEN…', 'noop', '', 'height:48px;padding:0 16px'));
  const rail = [['playback', 'PLAYBACK'], ['interface', 'INTERFACE'], ['media', 'MEDIA'], ['advanced', 'ADVANCED']].map(([k, l]) => `<div class="tile${sec === k ? ' sel' : ''}" style="height:56px" data-a="sset" data-v="${k}"><span class="tn">${l}</span></div>`).join('');
  return `<div class="ovl" data-hl="settings"><div class="hdr" style="height:48px;padding:0 10px 0 0;gap:10px">${B(ic('x', 24), 'gear', '', 'width:48px;height:48px;border-radius:0 6px 6px 0', 'icon')}<h2>Settings</h2><span class="crumb">Every change saves within a second.</span><div style="flex:1"></div><span style="color:var(--go);display:flex;align-items:center;gap:5px;font-size:13.5px" data-hl="saved">${ic('check', 16)}Saved</span></div>
    <div class="abs" style="left:0;top:48px;width:180px;height:384px;border-right:1px solid var(--ln);background:var(--p1)">${rail}</div>
    <div class="abs sc" style="left:180px;top:48px;width:620px;height:384px">${body}</div></div>`;
}
function rdFx() {
  const U = RD.fxUnit === 1 ? E.fx : E.fx2, deck = RD.fxUnit === 1 ? 'A' : 'B';
  const sl = (v, k) => `<div class="slid" data-a="slid" data-k="${k}"><div class="fill" style="width:${v * 100}%"></div><div class="knob" style="left:${v * 100}%"></div></div>`;
  let h = `<div class="abs row" style="left:0;top:48px;width:800px;height:56px;align-items:center;gap:6px;padding:0 8px;background:var(--p1);border-bottom:1px solid var(--ln)" data-hl="fxswitch">
    ${B('FX 1 · DECK A PADS', 'fxunit', 1, 'width:206px;height:48px', RD.fxUnit === 1 ? 'on' : '')}${B('FX 2 · DECK B PADS', 'fxunit', 2, 'width:206px;height:48px', RD.fxUnit === 2 ? 'on' : '')}
    <span style="color:var(--dim);font-size:12.5px;line-height:1.25;margin-left:6px">Starlight FX mode: pads 1–3 switch these effects; pad 4 sends the unit to its deck.</span></div>
    <div class="abs row" style="left:0;top:104px;width:800px;height:56px;align-items:center;gap:6px;padding:0 8px">
    <span class="lbl" style="width:52px">ROUTE</span>${[['DECK 1', 1], ['DECK 2', 2], ['MASTER', 3]].map(([l, v]) => B(l + ((v === 1 && deck === 'A') || (v === 2 && deck === 'B') ? '<span style="font-size:11px;color:var(--dim)">PAD 4</span>' : ''), 'fxr', v, 'width:120px;height:48px;flex-direction:column;gap:1px', U.route === v ? (v === 3 ? 'on' : 'on' + v) : '')).join('')}
    <span class="lbl" style="margin-left:10px">MIX</span><div style="flex:1">${sl(U.mix, 'mix')}</div></div>
    <div class="abs row" style="left:0;top:160px;width:800px;height:144px;gap:6px;padding:0 6px 6px">`;
  h += U.slots.map((s, i) => `<div class="card2" style="flex:1;padding:8px;display:flex;flex-direction:column;gap:6px;min-width:0">
      <div class="row" style="align-items:center;justify-content:space-between"><span class="lbl">EFFECT ${i + 1}</span><span style="color:var(--dim);font-size:11.5px">deck ${deck} FX pad ${i + 1}</span></div>
      <div class="row" style="gap:6px">${B(`${FX_NAMES[s.n]}<span style="margin-left:auto">${ic('down', 16)}</span>`, 'fxsel', i, 'flex:1;height:48px;justify-content:flex-start;padding:0 12px;text-transform:none;font-size:17px')}${B(s.on ? 'ON' : 'OFF', 'fxon', i, 'width:64px;height:48px', s.on ? 'on' : '')}</div>
      ${sl(s.meta, 'meta' + i)}</div>`).join('');
  return h + '</div>' + rdInfo(304) + rdOverview(376, 48) + rdTransport();
}
function renderRD() {
  let h = rdTop();
  if (RD.ovl === 'sources') h += rdSources();
  else if (RD.ovl === 'media') h += rdMedia();
  else if (RD.ovl === 'sample') h += rdSampleBrowser();
  else if (RD.ovl === 'settings') h += rdSettings();
  else if (RD.tab === 'decks') h += (RD.tool ? rdTool(RD.tool) : rdWaves()) + rdInfo(304) + rdOverview(376, 48) + rdTransport();
  else if (RD.tab === 'tracks') h += rdTracks();
  else if (RD.tab === 'sampler') h += rdSampler();
  else if (RD.tab === 'fx') h += rdFx();
  if (RD.sheet === 'eject') h += rdEjectSheet();
  if (RD.sheet === 'pad') h += rdChoosePad();
  h += rdBottomStrips();
  if (RD.toast) h += `<div class="toast">${esc(RD.toast)}</div>`;
  return h;
}

function rdBottomStrips() {
  let h = '';
  if (E.usb.present && E.usb.state === 'safe' && E.usb.safeT > 0) h += `<div class="abs safestrip" style="left:0;top:424px;width:800px;height:56px;z-index:46;display:flex;align-items:center;gap:12px;padding:0 4px 0 14px" data-hl="safestrip"><span>${ic('usb', 26)}</span><div style="flex:1"><div style="font:700 20px/1 var(--f-cond);letter-spacing:.04em">MANTACORE · SAFE TO REMOVE</div><div style="font-size:13px;margin-top:3px;opacity:.85">Pull the drive out now.</div></div>${B('OK', 'safeok', '', 'width:96px;height:48px;background:rgba(0,0,0,.25);border-color:rgba(255,255,255,.5);color:#fff')}</div>`;
  else if (E.usb.present && E.usb.state === 'ready' && E.usb.ping > 0) h += `<div class="abs" style="left:0;top:424px;width:800px;height:56px;z-index:46;display:flex;align-items:center;gap:10px;padding:0 4px 0 14px;background:var(--p2);border-top:2px solid var(--go);box-shadow:0 -6px 20px rgba(0,0,0,.5)" data-hl="insertping"><span style="color:var(--go)">${ic('usb', 24)}</span><div style="flex:1;min-width:0"><div style="font:700 18px/1 var(--f-cond);letter-spacing:.04em">MANTACORE PLUGGED IN</div><div style="font-size:13px;color:var(--dim);margin-top:3px">rekordbox export found · 58.6 GB</div></div>${B('DISMISS', 'pingno', '', 'width:120px;height:48px')}${B(ic('load', 18) + 'LOAD', 'pingload', '', 'width:132px;height:48px', 'pri')}</div>`;
  return h;
}

function rdTitles(top) {
  const one = n => { const d = E.decks[n], t = d.id ? TR[d.id] : null; return `<div style="width:400px;display:flex;align-items:center;gap:6px;padding:0 8px;min-width:0;${n === 2 ? 'border-left:1px solid var(--ln)' : ''}"><span class="badge s bg${n}" style="width:20px;height:20px;font-size:13px">${n}</span><span style="font-weight:700;font-size:14.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${t ? esc(t.title) : '<span style="color:var(--dim)">Empty</span>'}</span>${d.onPi ? '<span class="pill pi">ON PI</span>' : ''}</div>`; };
  return `<div class="abs info row" style="left:0;top:${top}px;width:800px;height:28px" data-hl="titles">${one(1)}${one(2)}</div>`;
}

function tickMedia(dt) {
  if (E.usb.ping > 0) { E.usb.ping -= dt; if (E.usb.ping <= 0) { E.usb.ping = 0; dirty = true; } }
  if (E.usb.safeT > 0) { E.usb.safeT -= dt; if (E.usb.safeT <= 0) { E.usb.safeT = 0; dirty = true; } }
}

/* ---------- actions ---------- */
function deckCommon(a, n) {
  const d = E.decks[n];
  if (a === 'key') d.key = !d.key;
  else if (a === 'q') d.q = !d.q;
  else if (a === 'sync') { d.sync = !d.sync; if (d.sync) { const o = E.decks[3 - n]; if (o.id && d.id) d.rate = +(((TR[o.id].bpm * (1 + o.rate / 100)) / TR[d.id].bpm - 1) * 100).toFixed(1); if (Math.abs(d.rate) > 8) d.rate = 0; } else d.rate = 0; }
  else if (a === 'cue') { if (!d.id) return; if (d.play) { d.play = false; d.pos = d.cue; } else d.cue = d.pos; }
  else if (a === 'play') { if (d.id) d.play = !d.play; }
  else if (a === 'tm') d.tmode = d.tmode === 'el' ? 'rem' : 'el';
  else return false;
  return true;
}
function loopAct(a, n, v) {
  const d = E.decks[n]; if (!d.id) return; const beat = beatLen(d.id);
  if (a === 'bl' || a === 'loopsz') d.loop = { s: d.pos, l: +v * beat };
  else if (a === 'lhalf' && d.loop) d.loop.l /= 2;
  else if (a === 'ldouble' && d.loop) d.loop.l *= 2;
  else if (a === 'lexit') d.loop = null;
  else if (a === 'lreloop' && !d.loop) d.loop = { s: Math.max(0, d.pos - 4 * beat), l: 4 * beat };
}
function sliderVal(el, ev) { const r = el.getBoundingClientRect(); return Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width)); }
function setSlider(k, v) { if (k === 'mix') E.fx.mix = v; else E.fx.slots[+k.slice(4)].meta = v; }

function actCU(a, v, el, ev) {
  const n = +v;
  switch (a) {
    case 'tab': Object.assign(CU, { tab: v, settings: false, loop: 0, sampleLoad: false, actions: false, srcMenu: false }); break;
    case 'le': CU.dlg = 'le'; CU.leSel = false; break;
    case 'lesel': CU.leSel = !CU.leSel; break;
    case 'leload': Object.assign(CU, { dlg: null, tab: 'tracks', show: true, feature: 'MANTACORE' }); break;
    case 'leeject': CU.dlg = 'ej'; break;
    case 'dlgclose': CU.dlg = null; break;
    case 'settings': CU.settings = !CU.settings; CU.tab = 'decks'; CU.loop = 0; CU.adv = false; break;
    case 'adv': CU.adv = v === '1'; break;
    case 'set': { const [k, val] = v.split(':'); if (val === undefined) E.set[k] = !E.set[k]; else E.set[k] = val; if (k === 'q1' || k === 'q2') E.decks[k === 'q1' ? 1 : 2].q = E.set[k]; break; }
    case 'rec': E.rec.on = !E.rec.on; E.rec.t = 0; break;
    case 'loop': CU.loop = CU.loop === n ? 0 : n; CU.tab = 'decks'; CU.settings = false; break;
    case 'loopsz': case 'lhalf': case 'ldouble': case 'lexit': case 'lreloop': loopAct(a, a === 'loopsz' ? CU.loop : n, v); break;
    case 'load': loadDeck(n, CU.sel); break;
    case 'row': CU.sel = v; break;
    case 'actions': CU.actions = !CU.actions; CU.loadSub = false; break;
    case 'loadsub': CU.loadSub = !CU.loadSub; break;
    case 'cuload': loadDeck(n, CU.sel); CU.actions = false; break;
    case 'arrange': CU.actions = false; CU.dlg = 'arrange'; break;
    case 'show': CU.show = !CU.show; CU.srcMenu = false; break;
    case 'srcmenu': CU.srcMenu = !CU.srcMenu; break;
    case 'feat': CU.feature = v; break;
    case 'loadsample': CU.sampleLoad = true; CU.tab = 'tracks'; CU.sel = 's3'; break;
    case 'cupad': if (TR[CU.sel]) loadPad(n, CU.sel); break;
    case 'done': CU.sampleLoad = false; CU.tab = 'sampler'; break;
    case 'cutrig': { const p = E.pads[n]; if (p.id) { p.play = true; p.t = 0; } break; }
    case 'custop': E.pads[n].play = false; E.pads[n].t = 0; break;
    case 'scancancel': E.scan.on = false; break;
    case 'fxr': E.fx.route = n; break;
    case 'fxon': E.fx.slots[n].on = !E.fx.slots[n].on; break;
    case 'fxsel': { const s = E.fx.slots[n]; s.n = (s.n + 1) % FX_NAMES.length; break; }
    case 'cuslid': setSlider(el.dataset.k, sliderVal(el, ev)); break;
    default: if (!deckCommon(a, n)) return;
  }
  dirty = true;
}
function actRD(a, v, el, ev) {
  const n = +v;
  switch (a) {
    case 'tab': Object.assign(RD, { tab: v, ovl: null, sheet: null, tool: 0, srcReturn: null }); break;
    case 'usb': RD.ovl = RD.ovl === 'media' ? null : 'media'; RD.sheet = null; break;
    case 'gear': RD.ovl = RD.ovl === 'settings' ? null : 'settings'; RD.sheet = null; break;
    case 'rec': E.rec.on = !E.rec.on; E.rec.t = 0; break;
    case 'loop': RD.tab = 'decks'; RD.ovl = null; RD.tool = RD.tool === n ? 0 : n; RD.toolTab = RD.tool ? RD.toolTab : 'loop'; break;
    case 'tt': RD.toolTab = v; RD.clear = false; break;
    case 'tclose': RD.tool = 0; break;
    case 'bl': case 'lhalf': case 'ldouble': case 'lexit': case 'lreloop': loopAct(a, a === 'bl' ? RD.tool : n, v); break;
    case 'bj': { const d = E.decks[RD.tool]; if (d.id) d.pos = Math.min(TR[d.id].dur, Math.max(0, d.pos + n * beatLen(d.id))); break; }
    case 'hc': { const d = E.decks[RD.tool]; if (!d.id) break; const cues = TR[d.id].cues, c = cues.find(x => x.n === n);
      if (RD.clear && c) cues.splice(cues.indexOf(c), 1); else if (c) d.pos = c.pos; else cues.push({ n, pos: d.pos, color: HC[n - 1] }); break; }
    case 'hclear': RD.clear = !RD.clear; break;
    case 'menu': RD.ovl = 'sources'; RD.sheet = null; RD.edit = false; RD.srcReturn = null; break;
    case 'sx': if (RD.srcReturn === 'sample') { RD.ovl = 'sample'; RD.srcReturn = null; } else RD.ovl = null; break;
    case 'stile': RD.srcSel = v; RD.srcPath = []; RD.edit = false; if (v === 'usb') E.usb.opened = true; break;
    case 'snav': RD.srcPath.push(v); if (v === 'MANTACORE') E.usb.opened = true; break;
    case 'sback': RD.srcPath.pop(); break;
    case 'sopen':
      if (v.startsWith('usb')) E.usb.opened = true;
      if (RD.srcReturn === 'sample') { RD.sample.src = v; RD.ovl = 'sample'; RD.srcReturn = null; RD.sample.sel = listOf(v).ids[0]; }
      else { RD.list = v; RD.ovl = null; RD.tab = 'tracks'; RD.sel = listOf(v).ids[0]; }
      break;
    case 'sedit': RD.edit = !RD.edit; break;
    case 'svis': { const vis = RD.srcOrder.filter(k => !RD.srcHidden[k]); if (!RD.srcHidden[v] && vis.length <= 1) { toast('Keep at least one source'); break; } RD.srcHidden[v] = !RD.srcHidden[v]; toast('Saved'); break; }
    case 'sstart': RD.srcStart = v; toast('Tracks starts here · saved'); break;
    case 'sup': case 'sdown': { const o = RD.srcOrder, j = a === 'sup' ? n - 1 : n + 1; if (j >= 0 && j < o.length) [o[n], o[j]] = [o[j], o[n]]; break; }
    case 'pen': RD.sheet = RD.sheet === 'actions' ? null : 'actions'; break;
    case 'shclose': RD.sheet = null; break;
    case 'row': RD.sel = v; break;
    case 'load': if (!loadDeck(n, RD.sel)) toast(E.decks[n].play ? `Deck ${n} is playing. Stop it to load.` : 'That track is on a drive that is not ready.'); break;
    case 'act':
      RD.sheet = null;
      if (v === '1' || v === '2') loadDeck(n, RD.sel);
      else if (v === 'pad') { RD.sample.sel = RD.sel; RD.sheet = 'pad'; }
      else toast(v === 'arrange' ? 'Arrange columns: today’s dialog, restyled' : 'Opens the full Mixxx track menu');
      break;
    case 'mx': RD.ovl = null; break;
    case 'eject': usageCountCache = usage().filter(x => !x.unload).length; RD.sheet = 'eject'; break;
    case 'ejgo': usageCountCache = usage().filter(x => !x.unload).length; E.usb.state = 'ejecting'; E.eject.step = 0; E.eject.t = 0; break;
    case 'mbrowse': E.usb.opened = true; RD.ovl = 'sources'; RD.srcSel = 'usb'; RD.srcPath = []; RD.edit = false; break;
    case 'mcopy': toast('COPY TO PI opens today’s USB ⇄ Pi copy tool'); break;
    case 'pingload': E.usb.ping = 0; E.usb.opened = true; RD.tab = 'tracks'; RD.ovl = 'sources'; RD.srcSel = 'usb'; RD.srcPath = []; RD.sheet = null; break;
    case 'pingno': E.usb.ping = 0; toast('MANTACORE stays closed. Open it from the USB chip or Sources.'); break;
    case 'safeok': E.usb.safeT = 0; break;
    case 'shide': E.set.scanShow = 'icon'; toast('Scan bar hidden and saved. The % shows on the USB chip.'); break;
    case 'scancel': E.scan.on = false; toast('Scan cancelled'); break;
    case 'loadsample': RD.ovl = 'sample'; RD.sample.pad = null; break;
    case 'pempty': RD.ovl = 'sample'; RD.sample.pad = n; break;
    case 'ptrig': { const p = E.pads[n]; if (p.id) { p.play = true; p.t = 0; } break; }
    case 'pstop': E.pads[n].play = false; E.pads[n].t = 0; break;
    case 'pclear': { const p = E.pads[n]; if (!p.play && p.id) { if (p.onPi) E.cleaned.unshift(`Pad ${n + 1}: ${TR[p.id].title}`); Object.assign(p, { id: null, onPi: false }); toast(`Pad ${n + 1} cleared · bank saved`); } break; }
    case 'sbx': RD.ovl = null; break;
    case 'ssrc': if (v === 'sources') { RD.srcReturn = 'sample'; RD.ovl = 'sources'; RD.edit = false; } else { RD.sample.src = v; } break;
    case 'srow': RD.sample.sel = v; break;
    case 'sload': if (RD.sample.pad != null) { if (loadPad(RD.sample.pad, RD.sample.sel)) { toast(`Loaded to pad ${RD.sample.pad + 1} · bank saved`); RD.ovl = null; RD.tab = 'sampler'; } else toast('Stop that pad first'); } else RD.sheet = 'pad'; break;
    case 'cpad': if (loadPad(n, RD.sample.sel)) { toast(`Loaded to pad ${n + 1} · bank saved`); RD.sheet = null; RD.ovl = null; RD.tab = 'sampler'; } break;
    case 'sset': RD.set = v; break;
    case 'opt': { const [k, val] = v.split(':'); if (val === 't') E.set[k] = !E.set[k]; else E.set[k] = val; if (k === 'q1' || k === 'q2') E.decks[k === 'q1' ? 1 : 2].q = E.set[k]; if (k === 'time') for (const m of [1, 2]) E.decks[m].tmode = val === 'elapsed' ? 'el' : 'rem'; toast('Saved'); break; }
    case 'fxunit': RD.fxUnit = n; break;
    case 'fxr': (RD.fxUnit === 1 ? E.fx : E.fx2).route = n; break;
    case 'fxon': { const s = (RD.fxUnit === 1 ? E.fx : E.fx2).slots[n]; s.on = !s.on; break; }
    case 'fxsel': { const s = (RD.fxUnit === 1 ? E.fx : E.fx2).slots[n]; s.n = (s.n + 1) % FX_NAMES.length; break; }
    case 'slid': { const U = RD.fxUnit === 1 ? E.fx : E.fx2, k = el.dataset.k, val = sliderVal(el, ev); if (k === 'mix') U.mix = val; else U.slots[+k.slice(4)].meta = val; break; }
    case 'noop': break;
    default: if (!deckCommon(a, n)) return;
  }
  dirty = true;
}

/* ---------- sim + jump-to ---------- */
function plugToggle() {
  if (E.usb.present) {
    const clean = E.usb.state === 'safe', unsafe = !clean && usage().length > 0;
    E.usb.present = false; E.usb.ping = 0; E.usb.safeT = 0; E.usb.opened = false;
    for (const n of [1, 2]) { const d = E.decks[n]; if (d.id && TR[d.id].src === 'usb' && !d.onPi && E.set.cache === 'OFF') d.play = false; }
    if (RD.list.startsWith('usb')) RD.list = 'pi:tracks';
    if (CU.feature === 'MANTACORE') CU.feature = 'TRACKS';
    toast(clean ? 'MANTACORE removed' : unsafe ? 'MANTACORE was pulled out without Eject' : 'MANTACORE removed');
  } else {
    Object.assign(E.usb, { present: true, state: 'ready', opened: false, ping: 15, safeT: 0 });
  }
  dirty = true;
}
function cuReset() { Object.assign(CU, { settings: false, adv: false, loop: 0, dlg: null, actions: false, loadSub: false, show: false, srcMenu: false, sampleLoad: false }); }
function rdReset() { Object.assign(RD, { ovl: null, sheet: null, tool: 0, padMenu: null, edit: false }); }
function ensureUsb() { Object.assign(E.usb, { present: true, state: 'ready', opened: true, ping: 0, safeT: 0 }); for (const n of [1, 2]) E.decks[n].onPi = false; E.pads.forEach(p => { p.onPi = false; }); if (E.decks[1].id !== 'u1' && !E.decks[1].play) loadDeck(1, 'u1'); E.decks[1].play = true; }
const GO = {
  decks: ['Decks', () => { CU.tab = 'decks'; RD.tab = 'decks'; }],
  tracks: ['Tracks', () => { CU.tab = 'tracks'; RD.tab = 'tracks'; }],
  sources: ['Sources', () => { CU.tab = 'tracks'; CU.show = true; CU.srcMenu = true; RD.tab = 'tracks'; RD.ovl = 'sources'; RD.srcSel = 'usb'; RD.srcPath = ['Playlists']; E.usb.opened = true; }],
  actions: ['Actions (pen)', () => { CU.tab = 'tracks'; CU.actions = true; RD.tab = 'tracks'; RD.sheet = 'actions'; }],
  sampler: ['Sampler', () => { CU.tab = 'sampler'; RD.tab = 'sampler'; }],
  sampleload: ['Load sample', () => { CU.tab = 'tracks'; CU.sampleLoad = true; RD.tab = 'sampler'; RD.ovl = 'sample'; RD.sample.pad = null; RD.sample.src = 'samples'; }],
  choosepad: ['Choose pad', () => { CU.tab = 'tracks'; CU.sampleLoad = true; RD.tab = 'sampler'; RD.ovl = 'sample'; RD.sample.pad = null; RD.sample.sel = 's6'; RD.sample.src = 'samples'; RD.sheet = 'pad'; }],
  loop: ['Loop panel', () => { CU.tab = 'decks'; CU.loop = 1; RD.tab = 'decks'; RD.tool = 1; RD.toolTab = 'loop'; }],
  fx: ['FX 1', () => { CU.tab = 'fx'; RD.tab = 'fx'; RD.fxUnit = 1; }],
  fx2: ['FX 2 (deck B pads)', () => { CU.tab = 'fx'; RD.tab = 'fx'; RD.fxUnit = 2; }],
  settings: ['Settings', () => { CU.tab = 'decks'; CU.settings = true; RD.ovl = 'settings'; RD.set = 'media'; }],
  insert: ['USB plugged in (ping)', () => { CU.tab = 'decks'; RD.tab = 'decks'; Object.assign(E.usb, { present: true, state: 'ready', opened: false, ping: 15, safeT: 0 }); }],
  media: ['Load / Eject → Media', () => { ensureUsb(); CU.dlg = 'le'; CU.leSel = true; RD.ovl = 'media'; }],
  eject: ['Eject', () => { ensureUsb(); CU.dlg = 'ej'; RD.ovl = 'media'; usageCountCache = usage().filter(x => !x.unload).length; RD.sheet = 'eject'; }],
  handover: ['After eject (handover)', () => { ensureUsb(); finishEject(); CU.tab = 'decks'; RD.tab = 'decks'; }],
  scan: ['Scan bar', () => { E.set.scanShow = 'bar'; startScan(); CU.tab = 'decks'; RD.tab = 'decks'; }],
  scanhidden: ['Scan hidden (USB %)', () => { E.set.scanShow = 'icon'; startScan(); CU.tab = 'decks'; RD.tab = 'decks'; }],
};
let navKey = 'decks';
function derive() {
  if (E.usb.ping > 0 && E.usb.present) return 'insert';
  if (RD.sheet === 'eject') return 'eject';
  if (RD.ovl === 'media') return E.usb.state === 'safe' ? 'handover' : 'media';
  if (RD.ovl === 'sources') return 'sources';
  if (RD.ovl === 'sample') return RD.sheet === 'pad' ? 'choosepad' : 'sampleload';
  if (RD.ovl === 'settings') return 'settings';
  if (RD.sheet === 'pad') return 'choosepad';
  if (RD.sheet === 'actions') return 'actions';
  if (RD.tab === 'decks' && RD.tool) return 'loop';
  if (E.scan.on && RD.tab !== 'tracks') return E.set.scanShow === 'bar' ? 'scan' : 'scanhidden';
  if (RD.tab === 'decks') return ([1, 2].some(n => E.decks[n].onPi) || E.usb.safeT > 0) ? 'handover' : 'decks';
  if (RD.tab === 'fx') return RD.fxUnit === 2 ? 'fx2' : 'fx';
  return RD.tab;
}
function go(key, hl) {
  cuReset(); rdReset(); GO[key][1](); navKey = key;
  RD.hl = hl && hl.rd ? hl.rd : []; CU.hl = hl && hl.cu ? hl.cu : [];
  dirty = true; renderNav(); paint();
}
function renderNav() {
  $('#nav').innerHTML = '<span class="lab">Jump to</span>' + Object.entries(GO).map(([k, [l]]) => `<button class="chip" data-go="${k}" aria-pressed="${navKey === k}">${l}</button>`).join('');
  $('#sim').innerHTML = `<span class="lab">Simulate</span><button class="chip sim" data-sim="usb">${E.usb.present ? 'Pull out USB' : 'Plug in USB'}</button><button class="chip sim" data-sim="scan">${E.scan.on ? 'Stop scan' : 'Start library scan'}</button><button class="chip sim" data-sim="p1">Deck 1 ${E.decks[1].play ? 'pause' : 'play'}</button><button class="chip sim" data-sim="p2">Deck 2 ${E.decks[2].play ? 'pause' : 'play'}</button><button class="chip sim" data-sim="pfl">Starlight PFL 1</button><button class="chip sim" data-sim="reset">Reset demo</button>`;
}
$('#nav').addEventListener('click', e => { const b = e.target.closest('[data-go]'); if (b) go(b.dataset.go); });
$('#sim').addEventListener('click', e => {
  const b = e.target.closest('[data-sim]'); if (!b) return; const s = b.dataset.sim;
  if (s === 'usb') { plugToggle(); navKey = derive(); } else if (s === 'scan') { if (E.scan.on) E.scan.on = false; else startScan(); }
  else if (s === 'p1' || s === 'p2') deckCommon('play', s === 'p1' ? 1 : 2);
  else if (s === 'pfl') E.decks[1].pfl = !E.decks[1].pfl;
  else { resetEngine(); resetUI(); wfCache.clear(); ovCache.clear(); navKey = 'decks'; }
  dirty = true; renderNav(); paint();
});

/* ---------- notes and calls ---------- */
const P = f => `photos/${f}.jpg`;
const NOTES = {
  decks: { t: 'Decks', cur: ['Two scrolling waveforms with a 100 px info column.', 'Deck strip: title, time, white BPM box, rate, key.', 'Bottom: overviews, then KEY · Q · SYNC · LOOP · CUE · ▶ per deck.'], red: ['Same order and layout. Deck colours (1 blue, 2 orange) tie each deck’s waveform, strip, overview and buttons together.', 'Deck strip chips: USB, ON PI, SYNC, MASTER (sync leader) and PFL. Tap the time to switch elapsed and remaining.', 'Every target is 48 px or more.', 'Top bar: the USB chip replaces LOAD / EJECT; a gear replaces SETTINGS.'], star: 'Play, Cue, Sync, Shift+Sync (MASTER) and PFL light the same states here. Hot cues 1–4 show on the waveforms in their colours.' },
  tracks: { t: 'Tracks', photo: 'IMG_0314', q: 'The samples need to have a full length menu you can cover the song tracks, also let\'s have a single load button that then goes into a choose pad', cur: ['Search, Actions and Show/Hide text buttons.', 'When loading samples, a LOAD TO · PAD 1–4 · DONE strip sits over the song list.'], red: ['☰ opens Sources full screen and turns into ✕ in the same spot. ✎ opens Actions.', 'A crumb shows which list you are in.', 'The track table stays Mixxx’s own (today’s columns).', 'LOAD has the deck’s current title beside it, and stays off while that deck plays.', 'Sample loading has its own screen (Load sample).'], star: 'No browse knob or load button on the Starlight, so browsing stays on the touch screen.' },
  sources: { t: 'Sources', photo: 'IMG_0311', q: 'I think we need to completley revisit the design of this as well, Make it better and easier to navigate, when in these bigger menus we can cover the whole screen because its deeper context not just quick and easy. Also the action menu button on tracks should just be a pen icon and the the show should be a hamburger menu that turns into an x when it\'s open', cur: ['Show opens a 290 px panel with Sources and Back buttons and the feature list.', 'Sources opens one mixed panel of checkboxes, order and default source.'], red: ['Full screen under the top bar.', 'Left: grouped tiles (your answer 4). Each drive first, then This Pi, Recordings, History, Folders, Samples. Build A ships one tile per Mixxx source first; the grouping lands in build B.', 'Right: that source’s lists as 56 px rows with counts, a crumb and Back. OPEN shows a list in Tracks.', 'EDIT LIST is its own step: show or hide, Up and Down, ★ where Tracks starts.'] },
  actions: { t: 'Actions (pen)', photo: 'IMG_0311', q: 'Also the action menu button on tracks should just be a pen icon and the the show should be a hamburger menu that turns into an x when it\'s open', cur: ['Actions menu: Load ›, Arrange columns, Original full menu ›.'], red: ['✎ icon, 48×48. Rows 52 px: Load to Deck 1, Load to Deck 2, Load to a sampler pad…, Arrange columns…, Full Mixxx menu ›.'] },
  sampler: { t: 'Sampler', photo: 'IMG_0313', q: 'same sample is nearly impossible to select, let\'s redesign that to be more useable (not eveything needs to be seen when putting in samples, Im down to go back to a similar to the OG sampler that had eight just slightly larger then the load opens a browse menu where you select from library and load to a deck, a separate component from the browse list but similar)', cur: ['Four pads: name, PAD n, STOP.', 'LOAD SAMPLE sends you to Tracks with a LOAD TO strip.'], red: ['Eight 200×104 pads. 1–4 are the Starlight’s deck A pads in SAMPLER mode, 5–8 deck B. The Starlight mapping already plays Sampler 1–8.', 'Tap a pad to play; it lights while it plays. STOP stops it; CLEAR empties it (only while stopped).', 'An empty pad opens Load sample for itself.', 'The bank saves within a second of every change.'], star: 'Pad LEDs and these pads show the same playing state.' },
  sampleload: { t: 'Load sample', photo: 'IMG_0314', q: 'The samples need to have a full length menu you can cover the song tracks, also let\'s have a single load button that then goes into a choose pad', cur: ['Tracks page with a LOAD TO · PAD 1–4 · DONE strip; the song list and both deck rows stay on screen.'], red: ['Its own full screen: SAMPLES, TRACKS, or any list through SOURCES….', 'Mixxx’s track table underneath, so search and scrolling work as in Tracks; it keeps its own place.', 'One LOAD TO PAD… button, then Choose pad. No preview yet (it waits for the headphone routing).'] },
  choosepad: { t: 'Choose pad', photo: 'IMG_0313', q: 'Im down to go back to a similar to the OG sampler that had eight just slightly larger then the load opens a browse menu where you select from library and load', cur: ['PAD 1–4 buttons in the LOAD TO strip; a playing pad is off.'], red: ['All 8 pads, each showing what it holds. Playing pads are off. A tap loads that pad and returns to Sampler.'] },
  loop: { t: 'Loop panel', cur: ['LOOP opens 12 sizes and ½ ×2 Exit Reloop over the waveforms; that deck’s waveform moves to the bottom row with − and +.'], red: ['Same panel with tabs: LOOP, JUMP (beat jump 1–32 back and forward) and CUES (hot cues 1–8, CLEAR).', 'These are XDJ-AZ pad modes the Starlight does not have.'], star: 'Starlight LOOP pads (1, 2, 4, 8 beats) light LOOP and the size here; HOT CUE pads light cues 1–4.' },
  fx: { t: 'FX 1', q: 'Alright but let\'s see if we can keep the 3 effects switcher between deck 1 deck 2 and master then have another mode. The starlight does have effects settings, maybe we just need to map them.', cur: ['Route DECK 1 / DECK 2 / MASTER, MIX slider, three effect cards. Effect unit 1 only.'], red: ['The DECK 1 / DECK 2 / MASTER switcher stays, as you asked.', 'A second mode, FX 2, shows effect unit 2: the one the Starlight’s deck B FX pads drive. Each mode has its own switcher, mix and three effects.', 'A study of the Starlight’s FX mapping comes with the result; no mapping change in this climb.'], star: 'Deck A FX pads 1–3 switch FX 1’s effects; pad 4 sends FX 1 to deck 1. Deck B’s pads do the same for FX 2 and deck 2.' },
  fx2: { t: 'FX 2', q: 'keep the 3 effects switcher between deck 1 deck 2 and master then have another mode.', cur: ['Not shown today: deck B’s FX pads change effects you cannot see.'], red: ['The same page for effect unit 2, with its own switcher, mix and effects.'] },
  settings: { t: 'Settings', q: 'We control the codebase, why can\'t we just save on settings change?', cur: ['Settings replaces the waveforms inside Decks; Advanced… swaps the panel.', 'Mixxx saves settings only when it quits.'], red: ['Full screen: Playback, Interface, Media, Advanced.', 'Each change saves within about a second (atomic write). “Saved” confirms it.', 'Media: Scan bar Show/Hide, RAM cache (also the room for handover copies), Eject on, and the plug-in ping.'] },
  insert: { t: 'Plugging in a drive', q: 'It should have a small ping that ask\'s to load with a load and dismiss button, it shouldn\'t be very intrusive and can cover the bottom actions.', cur: ['Nothing in Mixxx; udiskie desktop pop-ups at the top right, which covered SETTINGS and REC.'], red: ['A small strip over the bottom row: MANTACORE PLUGGED IN, with DISMISS and LOAD.', 'LOAD opens the drive in Sources. DISMISS leaves it closed; the USB chip and Sources can still open it.', 'It closes by itself after 15 s. The desktop pop-ups are off.'] },
  media: { t: 'USB & media', photo: 'IMG_0315', q: 'revisit and redesign the load and eject put some refrences (… load is usually automatic actually - eject is what is done safely)', cur: ['LOAD / EJECT opens a dialog: drive list, Refresh, Load, Eject…, Close.', 'Eject… leads to a second dialog that cannot eject.'], red: ['The USB chip always shows the state: READY, IN USE, SCAN NN%, EJECTING, SAFE TO REMOVE.', 'Media is full screen: one card per drive with EJECT first, then OPEN/BROWSE and COPY TO PI.', 'No Load step: the drive mounts by itself; Mixxx reads it only when you load it from the ping, open it here, or pick it in Sources.'] },
  eject: { t: 'Eject', photo: 'IMG_0316', q: 'Eject and the media controls need a revisit. I wanted it to work like a pioneer dj where you choose when the program can access the files and choose when to eject and keep the last playong/loaded song in storage for handover (get\'s cleaned out after transition out)', cur: ['Eject… opens a second dialog: “Eject is not available on this system” and a “Prepare selected disk” button that does nothing.'], red: ['The sheet lists what uses the drive and what happens to each.', 'Steps: stop new reads → keep the items playing from their Pi copies → close files → unmount and check.', 'A deck playing a track too big for Pi memory blocks Eject until it stops.'] },
  handover: { t: 'Handover', photo: 'IMG_0316', q: '…keep the last playong/loaded song in storage for handover (get\'s cleaned out after transition out)', cur: ['No handover: eject is off.'], red: ['A green SAFE TO REMOVE strip flashes up at the bottom (your answer 2).', 'Deck 1 keeps playing from its copy in Pi memory: see ON PI.', 'Load another track on Deck 1 to see the copy cleaned out (Media › Cleaned out).', 'Pi memory is used only if it costs at most 10% more load than playing from the drive; otherwise the copy is made when you press Eject (your answer 3).'] },
  scan: { t: 'Scan bar', photo: 'IMG_0310', q: 'The scan bar can be improved it was messy and it covered the quick actions, let\'s just show the final file / in the filename instead of the entire path, in the list then have a hide and cancel. With the hide it is okay that it covers but if it is hidden save that setting and put a USB icon with the % of it loading that is done.', cur: ['A bar over the transport row: the full path, a small progress bar and Cancel.'], red: ['A 48 px strip over the overview row, so CUE and ▶ stay reachable.', 'File name only, a %, HIDE and CANCEL.', 'HIDE saves the choice. The USB chip then shows SCAN NN%.'] },
  scanhidden: { t: 'Scan hidden', photo: 'IMG_0310', q: 'if it is hidden save that setting and put a USB icon with the % of it loading that is done.', cur: ['No hide: the bar stays until the scan ends or you cancel.'], red: ['The USB chip shows SCAN NN%. Settings › Media › Scan bar brings the bar back.'] },
};
let CALLS = [
  { q: 'Plugging in a USB drive', ans: 'A small ping with LOAD and DISMISS; not intrusive; may cover the bottom actions.', go: 'insert', hl: ['insertping'] },
  { q: 'Eject', ans: 'Yes, system eject, with a bottom indicator that flashes up when it is safe to remove.', go: 'handover', hl: ['safestrip'] },
  { q: 'Where the handover copy lives', ans: 'Pi memory, if it costs at most 10% more load; otherwise copy when Eject is pressed and wait.', go: 'handover', hl: ['onpi', 'deck1'] },
  { q: 'Sources layout', ans: 'Grouped tiles. “Alright well see how it works.”', go: 'sources', hl: ['sourcesrail'] },
  { q: 'Effects for deck B’s pads', ans: 'Keep the DECK 1 / DECK 2 / MASTER switcher, add another mode; look at the Starlight FX mapping.', go: 'fx2', hl: ['fxswitch'] },
  { q: 'udiskie pop-ups', ans: 'Off. “Absolutely yes.”', go: 'insert', hl: ['usbchip'] },
  { q: 'Clean quit; reboot waits for Mixxx', ans: 'Yes.', go: 'settings', hl: ['saved'] },
  { q: 'Audio routing on the test card', ans: 'Set stereo: Master 1–2, Headphones 3–4.', go: null },
  { q: 'Test drive and flash', ans: 'Eject tests may use MANTACORE (clean unmounts only). Performance on a faster flash drive when you have one. No reflash.', go: null },
  { q: 'DJ-003 writes to rekordbox', ans: 'Stays in the backlog. “Agreed.”', go: null },
];
function renderSide() {
  const n = NOTES[navKey] || NOTES.decks;
  let h = `<div class="card"><h2>${esc(n.t)}</h2>`;
  if (n.q) h += `<div class="quote">“${esc(n.q)}”</div>`;
  if (n.photo) h += `<figure class="photo" style="margin:8px 0 0"><img src="${P(n.photo)}" alt="Owner photo ${n.photo} of the current screen" loading="lazy"><figcaption>${n.photo} · your photo of build 2</figcaption></figure>`;
  h += `<h3>Now</h3><ul>${n.cur.map(x => `<li>${esc(x)}</li>`).join('')}</ul><h3>Redesign</h3><ul>${n.red.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`;
  if (n.star) h += `<h3>Starlight</h3><p style="margin:0">${esc(n.star)}</p>`;
  h += '</div>';
  h += `<div class="card calls"><h2>Your answers (17 Nov)</h2><ol>${CALLS.map((c, i) => `<li><div class="q">${esc(c.q)}</div><div class="opts">${esc(c.ans)}</div>${c.go ? `<button data-call="${i}">Show me</button>` : ''}</li>`).join('')}</ol></div>`;
  $('#side').innerHTML = h;
}
$('#side').addEventListener('click', e => { const b = e.target.closest('[data-call]'); if (!b) return; const c = CALLS[+b.dataset.call]; go(c.go, { rd: c.hl || [], cu: c.hlcu || [] }); if (window.innerWidth < 1100) $('#stage').scrollIntoView({ behavior: 'smooth' }); });
window.MIXPI_CALLS = calls => { CALLS = calls; renderSide(); };

/* ---------- view + scaling ---------- */
const cuEl = $('#cu'), rdEl = $('#rd');
let view = 'both';
try { view = localStorage.getItem('mixpi-view') || 'both'; } catch (e) { /* storage off */ }
function setView(v) {
  view = v; $('#wrap-cur').hidden = v === 'new'; $('#wrap-new').hidden = v === 'cur';
  $$('.seg button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.view === v)));
  try { localStorage.setItem('mixpi-view', v); } catch (e) { /* storage off */ }
  fit();
}
$$('.seg button').forEach(b => b.addEventListener('click', () => setView(b.dataset.view)));
function fit() { for (const [f, s] of [['#fit-cur', cuEl], ['#fit-new', rdEl]]) { const box = $(f), w = box.clientWidth || 800, k = Math.min(1, w / 800); box.style.height = 480 * k + 'px'; s.style.transform = `scale(${k})`; s._k = k; } }
new ResizeObserver(fit).observe($('#stage'));

/* ---------- render ---------- */
let canvases = [], lives = [];
function keepScroll(root) { const m = {}; $$('[data-keep]', root).forEach(e => { m[e.dataset.keep] = e.scrollTop; }); return m; }
function restoreScroll(root, m) { $$('[data-keep]', root).forEach(e => { if (m[e.dataset.keep] != null) e.scrollTop = m[e.dataset.keep]; }); }
function placeHL(root, ids) {
  $$('.hl', root).forEach(x => x.remove());
  const k = root._k || 1, rr = root.getBoundingClientRect();
  for (const id of ids || []) { const el = root.querySelector(`[data-hl="${id}"]`); if (!el) continue; const r = el.getBoundingClientRect(); const d = document.createElement('div'); d.className = 'hl'; d.style.cssText = `left:${(r.left - rr.left) / k - 4}px;top:${(r.top - rr.top) / k - 4}px;width:${r.width / k + 8}px;height:${r.height / k + 8}px`; root.appendChild(d); }
}
let lastSide = '';
function renderAll() {
  const sc = keepScroll(cuEl), sr = keepScroll(rdEl);
  const s1 = $('#rd-search') ? $('#rd-search').value : '';
  cuEl.innerHTML = renderCU(); rdEl.innerHTML = renderRD();
  restoreScroll(cuEl, sc); restoreScroll(rdEl, sr);
  if ($('#rd-search')) $('#rd-search').value = s1;
  canvases = $$('canvas[data-cv]'); canvases.forEach(prepCanvas);
  lives = $$('[data-live]');
  placeHL(cuEl, CU.hl); placeHL(rdEl, RD.hl);
  const key = navKey + '|' + CALLS.length; if (key !== lastSide) { renderSide(); lastSide = key; }
}
function bind(root, fn, which) {
  root.addEventListener('click', e => {
    const t = e.target.closest('[data-a]'); if (!t || !root.contains(t)) return;
    if (t.classList.contains('dis') && t.dataset.a !== 'shclose') return;
    if (which === 'rd') RD.hl = []; else CU.hl = [];
    fn(t.dataset.a, t.dataset.v, t, e); if (which === 'rd') navKey = derive(); renderNav(); paint();
  });
}
bind(cuEl, actCU, 'cu'); bind(rdEl, actRD, 'rd');
rdEl.addEventListener('input', e => {
  const q = e.target.value.trim().toLowerCase(), box = e.target.id === 'rd-search' ? rdEl.querySelector('[data-hl="tracklist"]') : rdEl.querySelector('[data-keep="rdsamples"]');
  if (!box) return; box.querySelectorAll('.lrow[data-v]').forEach(r => { r.hidden = !!q && !TR[r.dataset.v].title.toLowerCase().includes(q); });
});

/* ---------- loop ---------- */
let last = performance.now();
function frame(now) {
  const dt = Math.min(0.1, (now - last) / 1000); last = now;
  for (const n of [1, 2]) {
    const d = E.decks[n]; if (!d.play || !d.id) continue; const t = TR[d.id];
    d.pos += dt * (1 + d.rate / 100);
    if (d.loop && d.pos > d.loop.s + d.loop.l) d.pos -= d.loop.l;
    if (d.pos >= t.dur) { d.pos = t.dur; d.play = false; dirty = true; }
  }
  E.pads.forEach(p => { if (p.play) { p.t += dt; if (p.t >= TR[p.id].dur) { p.play = false; p.t = 0; dirty = true; } } });
  if (E.scan.on) {
    E.scan.pct += dt * 2.4; E.scan.ft += dt; if (E.scan.ft > 0.45) { E.scan.ft = 0; E.scan.fi = (E.scan.fi + 1) % SCAN_FILES.length; }
    if (E.scan.pct >= 100) { E.scan.pct = 100; E.scan.on = false; toast('Scan finished'); renderNav(); }
  }
  if (E.rec.on) E.rec.t += dt;
  tickMedia(dt);
  if (E.usb.state === 'ejecting') { E.eject.t += dt; const st = Math.floor(E.eject.t / 0.7); if (st !== E.eject.step) { E.eject.step = st; dirty = true; } if (st >= 4) { finishEject(); dirty = true; } }
  if (RD.toast) { RD.toastT -= dt; if (RD.toastT <= 0) { RD.toast = null; dirty = true; } }
  paint();
  requestAnimationFrame(frame);
}
function paint() {
  if (dirty) { dirty = false; renderAll(); }
  for (const cv of canvases) { const [k, n] = cv.dataset.cv.split(':'); if (k === 'o') drawOverview(cv, +n, cv.dataset.th); else drawScroll(cv, +n, cv.dataset.th); }
  const done = Math.round((E.scan.total * E.scan.pct) / 100), pctTxt = Math.floor(E.scan.pct) + '%';
  for (const el of lives) {
    const k = el.dataset.live;
    if (k === 'tm1' || k === 'tm2') { const d = E.decks[+k[2]]; el.textContent = d.id ? (d.tmode === 'el' ? fmtTime(d.pos).replace(/(\.\d)\d$/, '$1') : fmtTime(TR[d.id].dur - d.pos, true).replace(/(\.\d)\d$/, '$1')) : '—'; }
    else if (k === 'cut1' || k === 'cut2') { const d = E.decks[+k[3]]; el.textContent = d.id ? fmtTime(TR[d.id].dur - d.pos, true) : '-0:00.00'; }
    else if (k.startsWith('pp')) { const p = E.pads[+k.slice(2)]; el.style.width = p.play ? (p.t / TR[p.id].dur) * 100 + '%' : '0'; }
    else if (k === 'scanfile') el.textContent = SCAN_FILES[E.scan.fi];
    else if (k === 'scancount') el.textContent = `${fmtN(done)} of ${fmtN(E.scan.total)}`;
    else if (k === 'scanbar' || k === 'cuscanbar') el.style.width = E.scan.pct + '%';
    else if (k === 'cuscan') el.textContent = 'Scanning: ' + SCAN_DIRS.slice(0, 18) + '…' + SCAN_DIRS.slice(30) + SCAN_FILES[E.scan.fi].replace(/\.\w+$/, '');
    else if (k === 'usbpct') el.textContent = 'SCAN ' + pctTxt;
    else if (k === 'scanpct2') el.textContent = pctTxt + ' — stops on eject';
    else if (k === 'ring') el.setAttribute('stroke-dashoffset', String(94.25 * (1 - E.scan.pct / 100)));
    else if (k === 'rect') { const s = Math.floor(E.rec.t); el.textContent = Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); }
  }
}
setView(view);
renderNav();
paint();
requestAnimationFrame(frame);
window.MIXPI_GO = go;
/* Annotation layer for the annotated question screenshots. items: {hl, label, x, y} in 800x480 space. */
window.MIXPI_ANNOTATE = (which, items) => {
  const root = which === 'cu' ? cuEl : rdEl, k = root._k || 1, rr = root.getBoundingClientRect();
  const old = root.querySelector('svg.ann'); if (old) old.parentNode.removeChild(old);
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'ann'); svg.setAttribute('width', '800'); svg.setAttribute('height', '480');
  svg.style.cssText = 'position:absolute;left:0;top:0;z-index:200;pointer-events:none;overflow:visible';
  let out = '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#ff3dbb"/></marker></defs>';
  for (const it of items) {
    const el = root.querySelector(`[data-hl="${it.hl}"]`); if (!el) continue;
    const r = el.getBoundingClientRect(), x = (r.left - rr.left) / k - 3, y = (r.top - rr.top) / k - 3, w = r.width / k + 6, h = r.height / k + 6;
    out += `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="7" fill="none" stroke="#ff3dbb" stroke-width="3.5"/>`;
    if (it.label) {
      const tw = it.label.length * 8.2 + 20, lx = it.x, ly = it.y, mid = lx + tw / 2;
      const above = ly + 28 < y, below = ly > y + h;
      const ax = above || below ? Math.max(x + 8, Math.min(x + w - 8, mid)) : (lx < x ? x : x + w);
      const ay = above ? y : below ? y + h : y + h / 2;
      out += `<line x1="${mid}" y1="${ly + 14}" x2="${ax}" y2="${ay}" stroke="#ff3dbb" stroke-width="3" marker-end="url(#ah)"/>`;
      out += `<rect x="${lx}" y="${ly}" width="${tw}" height="28" rx="14" fill="#ff3dbb"/><text x="${mid}" y="${ly + 19}" text-anchor="middle" font-family="Ubuntu, sans-serif" font-weight="700" font-size="15" fill="#fff">${esc(it.label)}</text>`;
    }
  }
  svg.innerHTML = out; root.appendChild(svg);
};
window.MIXPI_STATE = { E, CU, RD, render: () => { dirty = true; paint(); } };
if (/^#s-/.test(location.hash) && GO[location.hash.slice(3)]) go(location.hash.slice(3));
})();
