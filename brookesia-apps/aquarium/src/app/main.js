(function () {
'use strict';

const SETTINGS = '/littlefs/aquarium-settings.json';
const RETURN_EDGE = 440;
const NOTES = {
  gold: '好奇 · 喜欢靠近水波',
  moon: '慢热 · 常停在水草附近',
  school: '合群 · 会和同伴一起转向',
};
const SPECIES = {
  gold: { width: 150, height: 117, speed: 30, top: 60, bottom: 378 },
  moon: { width: 114, height: 120, speed: 18, top: 75, bottom: 370 },
  school: { width: 50, height: 28, speed: 32, top: 66, bottom: 365 },
};
const START = [
  ['gold', 234, 204, 1], ['moon', 315, 315, -1],
  ['school', 333, 129, 1], ['school', 372, 156, 1], ['school', 402, 120, 1], ['school', 363, 96, 1],
];
const ACTIONS = ['waterPress', 'waterRelease', 'waterCancel', 'light', 'book', 'dismiss', ...Object.keys(NOTES)];
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
let gui, timer, storage;
let timerId = 0, paused = true, night = false, panel = false, selected = 'gold';
let fish = [], touch = null, ripple = null, lastTick = 0, started = 0, rendered = {};

function call(service, name, params = {}) {
  const result = JSON.parse(brookesia.call_function(service, name, JSON.stringify(params)));
  if (!result.success) throw new Error(result.error || result.error_message || name);
  return result.data;
}

function readLight() {
  try { return JSON.parse(call(storage, 'FSReadText', { Path: SETTINGS })).night === true; }
  catch (_) { return false; }
}

function draw(now) {
  const elapsed = Math.max(0, now - started);
  const updates = [], commands = [], next = {};
  const pathOf = node => '/main/' + node;
  function changed(node, key, value) {
    const address = node + ':' + key;
    next[address] = value;
    return rendered[address] !== value;
  }
  function bind(node, key, value) {
    if (changed(node, key, value)) updates.push({ Path: pathOf(node), Key: key, Value: String(value) });
  }
  function image(node, src) {
    if (changed(node, 'src', src)) commands.push({ Name: 'SetViewSrc', Params: { Path: pathOf(node), Src: src } });
  }
  for (let band = 0; band < 4; band++) image('backdrop' + band, (night ? 'night' : 'day') + band);
  bind('light/label', 'text', night ? '夜景' : '日景');
  bind('sheet', 'hidden', !panel);
  bind('sheet/description', 'text', NOTES[selected]);
  for (const name of Object.keys(NOTES)) {
    bind('sheet/' + name, 'color', name === selected ? '#23564F' : '#103740');
  }
  bind('bubble', 'y', 388 - Math.floor(elapsed / (night ? 68 : 43)) % 305);
  const rippleAge = ripple ? now - ripple.at : Infinity;
  bind('ripple', 'hidden', rippleAge >= 680);
  if (rippleAge < 680) {
    const diameter = 16 + Math.floor(rippleAge / 9);
    bind('ripple', 'w', diameter);
    bind('ripple', 'h', diameter);
    bind('ripple', 'x', Math.round(ripple.x - diameter / 2));
    bind('ripple', 'y', Math.round(ripple.y - diameter / 2));
  }
  fish.forEach((item, i) => {
    const sprite = SPECIES[item.kind];
    const node = 'fish' + i;
    bind(node, 'x', Math.round(item.x - sprite.width / 2));
    bind(node, 'y', Math.round(item.y - sprite.height / 2));
    const phase = Math.floor((elapsed + i * 43) / (night ? 370 : 265)) % 2;
    image(node, item.kind + '_' + (item.facing > 0 ? 'r' : 'l') + phase);
  });
  if (updates.length) commands.unshift({ Name: 'SetBindings', Params: { Updates: updates } });
  if (commands.length) {
    const result = call(gui, 'ExecuteBatch', { Commands: commands });
    if (!result.Success) throw new Error('Aquarium display update failed');
    rendered = next;
  }
}

function swim(now, delta) {
  const time = (now - started) / 1000;
  const leader = fish[2];
  const leaderX = leader.x, leaderY = leader.y, schoolDirection = leader.cruise;
  const attract = ripple && now - ripple.at < 3100;
  fish.forEach((item, i) => {
    const sprite = SPECIES[item.kind];
    const margin = sprite.width / 2 + 7;
    const pace = night ? 0.57 : 1;
    let vx = item.cruise * sprite.speed;
    let destY = item.home + Math.sin(time * (item.kind === 'moon' ? .59 : .83) + i) * (night ? 11 : 23);
    if (item.kind === 'school' && i > 2) {
      const targetX = leaderX + schoolDirection * (i - 2) * 19;
      vx = clamp(schoolDirection * sprite.speed + (targetX - item.x) * .9, -46, 46);
      destY = leaderY + [0, 27, -10, -34][i - 2] + Math.sin(time + i) * 7;
    }
    if (attract && Math.hypot(item.x - ripple.x, item.y - ripple.y) < 315) {
      if (item.kind === 'gold' || item.kind === 'school') {
        const offset = item.kind === 'gold' ? -27 : (i - 3) * 21;
        vx = clamp((ripple.x + offset - item.x) * 1.6, -88, 88);
        destY = ripple.y + (item.kind === 'gold' ? 11 : (i - 3) * 19);
      } else if (Math.abs(item.x - ripple.x) < 110) {
        vx = item.x < ripple.x ? -36 : 36;
        destY = 345;
      }
    }
    const edge = item === leader ? 102 : margin;
    if (item.x <= edge) item.cruise = 1;
    if (item.x >= 480 - edge) item.cruise = -1;
    if ((item === leader || item.kind !== 'school') && !attract) vx = item.cruise * sprite.speed;
    item.x = clamp(item.x + vx * delta * pace, edge, 480 - edge);
    item.y = clamp(item.y + clamp((destY - item.y) * 1.35, -45, 45) * delta * pace, sprite.top, sprite.bottom);
    if (Math.abs(vx) > 6) item.facing = vx < 0 ? -1 : 1;
  });
}

function tick(now) {
  if (paused) return;
  if (now < lastTick || now - lastTick > 5000) {
    ripple = null;
    touch = null;
    started = lastTick = now;
  }
  swim(now, Math.min(0.20, (now - lastTick) / 1000));
  lastTick = now;
  if (ripple && now - ripple.at >= 3100) ripple = null;
  draw(now);
}

function openBook(kind) {
  if (kind) selected = kind;
  panel = true;
}

function tap(point, now) {
  if (panel) {
    panel = false;
    return;
  }
  const chosen = fish.find(item => {
    const sprite = SPECIES[item.kind];
    return Math.abs(item.x - point.x) < sprite.width * .28 &&
      Math.abs(item.y - point.y) < sprite.height * .31;
  });
  if (chosen) openBook(chosen.kind);
  else ripple = { x: clamp(point.x, 12, 468), y: clamp(point.y, 20, 412), at: now };
}

function action(name, payload, now) {
  if (paused) return;
  if (name === 'light') {
    night = !night;
    draw(now);
    try { call(storage, 'FSWriteText', { Path: SETTINGS, Data: JSON.stringify({ night }) }); } catch (_) {}
    return;
  }
  if (name === 'book') openBook();
  if (name === 'dismiss') panel = false;
  if (Object.prototype.hasOwnProperty.call(NOTES, name)) openBook(name);
  if (name === 'waterCancel') touch = null;
  if (name === 'waterPress' || name === 'waterRelease') {
    let point;
    try { point = typeof payload === 'string' ? JSON.parse(payload) : payload; } catch (_) {}
    const inside = Number.isFinite(point?.x) && Number.isFinite(point?.y) && point.x >= 0 &&
      point.x < 480 && point.y >= 0 && point.y < RETURN_EDGE;
    if (name === 'waterPress') {
      touch = inside ? point : null;
      return;
    }
    if (inside && touch && Math.hypot(point.x - touch.x, point.y - touch.y) <= 22) tap(point, now);
    touch = null;
  }
  draw(now);
}

function resume() {
  if (!paused) return;
  paused = false;
  panel = false;
  started = lastTick = Date.now();
  rendered = {};
  draw(started);
  timerId = call(timer, 'StartPeriodic', { Name: 'aquarium', IntervalMs: 50 });
}

function pause() {
  paused = true;
  touch = ripple = null;
  if (timerId) {
    const existing = timerId;
    timerId = 0;
    // SystemCore can dispose the timer before on_stop.
    try { call(timer, 'Stop', { TimerId: existing }); } catch (_) {}
  }
}

globalThis.brookesia_app = {
  on_start() {
    gui = brookesia.start_service('SystemGui');
    timer = brookesia.start_service('SystemTimer');
    storage = brookesia.start_service('Storage');
    night = readLight();
    fish = START.map(([kind, x, y, facing]) => ({ kind, x, y, home: y, facing, cruise: facing }));
    for (const action of ACTIONS) call(gui, 'SubscribeAction', { Action: action });
    resume();
    return true;
  },
  on_timer() { tick(Date.now()); return true; },
  on_action(name, path, payload) { action(name, payload, Date.now()); return true; },
  on_pause() { pause(); return true; },
  on_resume() { resume(); return true; },
  on_stop() { pause(); return true; },
};
})();
