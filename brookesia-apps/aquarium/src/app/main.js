(function () {
'use strict';

const WEATHER_SETTINGS = '/littlefs/weather-settings.json';
const STOCK_SETTINGS = '/littlefs/aquarium-stock.json';
const SOLAR_CITIES = {
  shanghai: { latitude: 31.2304, longitude: 121.4737, cache: '/littlefs/weather-cache.json' },
  qingdao: { latitude: 36.0671, longitude: 120.3826, cache: '/littlefs/weather-cache-qingdao.json' },
};
const CITY_OFFSET_HOURS = 8;
const DAY_MS = 24 * 60 * 60 * 1000;
const LIGHT_INTERVAL_MS = 30000;
const RETURN_EDGE = 440;
const BACKDROP_BANDS = 8;
const BUBBLE_DIAMETER = 7;
const NATIVE_RETRY_MS = 300;
const NATIVE_RETRY_LIMIT_MS = 3000;
const NOTES = {
  gold: '好奇 · 喜欢靠近水波',
  moon: '慢热 · 常停在水草附近',
  school: '合群 · 会和同伴一起转向',
  jelly: '随水漂浮 · 伞盖会缓慢收放',
  shark: '巡游 · 喜欢开阔水域',
  ray: '滑翔 · 扇动宽大的胸鳍',
  clown: '活跃 · 常在礁石附近游动',
  turtle: '慢游 · 用前鳍划水',
};
const KINDS = Object.keys(NOTES);
const ALL_STOCK = (1 << KINDS.length) - 1;
const MAX_SPECIES = 5;
const kindBit = kind => 1 << KINDS.indexOf(kind);
const DEFAULT_STOCK = kindBit('school') | kindBit('shark') | kindBit('ray') | kindBit('clown') | kindBit('turtle');
const speciesCount = mask => KINDS.filter(kind => (mask & kindBit(kind)) !== 0).length;
const SPECIES = {
  gold: { width: 150, height: 117, speed: 30, top: 60, bottom: 378 },
  moon: { width: 114, height: 120, speed: 18, top: 75, bottom: 370 },
  school: { width: 50, height: 28, speed: 32, top: 66, bottom: 365 },
  jelly: { width: 60, height: 66, top: 77, bottom: 337 },
  shark: { width: 186, height: 84, speed: 41, top: 68, bottom: 245 },
  ray: { width: 126, height: 84, speed: 21, top: 162, bottom: 376 },
  clown: { width: 48, height: 36, speed: 24, top: 145, bottom: 346 },
  turtle: { width: 72, height: 48, speed: 15, top: 184, bottom: 377 },
};
const START = [
  ['gold', 234, 204, 1], ['moon', 315, 315, -1],
  ['school', 333, 129, 1], ['school', 372, 156, 1], ['school', 402, 120, 1], ['school', 363, 96, 1],
  ['jelly', 123, 153, 1],
  ['shark', 144, 111, 1], ['ray', 168, 330, -1], ['clown', 264, 339, 1], ['turtle', 282, 363, -1],
];
const ACTIONS = ['waterPress', 'waterRelease', 'waterCancel', 'book', 'dismiss', ...KINDS];
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
let gui, timer, storage, modes;
let nativeAvailable = false, nativeRendering = false;
let nativeRetryAt = 0;
let cachedRows = false;
let timerId = 0, lightTimer = 0, paused = true, night = false, panel = false, selected = 'gold';
let stock = DEFAULT_STOCK, stockError = '';
const inTank = kind => (stock & kindBit(kind)) !== 0;
let fish = [], touch = null, ripple = null, lastTick = 0, started = 0, rendered = {};

function call(service, name, params = {}) {
  const result = JSON.parse(brookesia.call_function(service, name, JSON.stringify(params)));
  if (!result.success) throw new Error(result.error || result.error_message || name);
  return result.data;
}

function readJson(path) {
  try { return JSON.parse(call(storage, 'FSReadText', { Path: path })); }
  catch (_) { return null; }
}

function cachedNight(cache, city, localTime) {
  const daily = cache?.data?.daily;
  if (cache?.version !== 2 || cache.mode !== city || !Array.isArray(daily?.time)) return null;
  const date = localTime.slice(0, 10);
  const i = daily.time.indexOf(date);
  if (i < 0) return null;
  const rise = daily.sunrise?.[i], set = daily.sunset?.[i];
  const valid = time => typeof time === 'string' && time.slice(0, 10) === date &&
    /^\d{4}-\d\d-\d\dT(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$/.test(time);
  if (!valid(rise) || !valid(set)) return null;
  const seconds = time => time.length === 16 ? time + ':00' : time;
  if (seconds(rise) >= seconds(set)) return null;
  return localTime < seconds(rise) || localTime >= seconds(set);
}

// NOAA solar position equations, including the apparent sunrise/sunset zenith.
// https://gml.noaa.gov/grad/solcalc/solareqns.PDF
function estimatedNight(localMs, localDate, city) {
  const minutes = (localMs % DAY_MS) / 60000;
  const year = localDate.getUTCFullYear();
  const jan1 = Date.UTC(year, 0, 1);
  const yearDays = (Date.UTC(year + 1, 0, 1) - jan1) / DAY_MS;
  const angle = 2 * Math.PI * ((localMs - jan1) / DAY_MS - 0.5) / yearDays;
  const equationOfTime = 229.18 * (0.000075 + 0.001868 * Math.cos(angle) - 0.032077 * Math.sin(angle) -
    0.014615 * Math.cos(2 * angle) - 0.040849 * Math.sin(2 * angle));
  const declination = 0.006918 - 0.399912 * Math.cos(angle) + 0.070257 * Math.sin(angle) -
    0.006758 * Math.cos(2 * angle) + 0.000907 * Math.sin(2 * angle) -
    0.002697 * Math.cos(3 * angle) + 0.00148 * Math.sin(3 * angle);
  const radians = Math.PI / 180;
  const latitude = city.latitude * radians;
  const solarMinutes = minutes + equationOfTime + 4 * city.longitude - CITY_OFFSET_HOURS * 60;
  const hourAngle = (solarMinutes / 4 - 180) * radians;
  const cosineZenith = Math.sin(latitude) * Math.sin(declination) +
    Math.cos(latitude) * Math.cos(declination) * Math.cos(hourAngle);
  return cosineZenith < Math.cos(90.833 * radians);
}

function syncLighting(now) {
  // The board may start with an unset clock while its RTC or Wi-Fi time sync loads.
  if (now < Date.UTC(2024, 0, 1) || now >= Date.UTC(2100, 0, 1)) return false;
  const mode = readJson(WEATHER_SETTINGS)?.mode === 'qingdao' ? 'qingdao' : 'shanghai';
  const city = SOLAR_CITIES[mode];
  const localMs = now + CITY_OFFSET_HOURS * 3600000;
  const localDate = new Date(localMs);
  const cached = cachedNight(readJson(city.cache), mode, localDate.toISOString().slice(0, 19));
  const next = cached ?? estimatedNight(localMs, localDate, city);
  if (night === next) return false;
  if (nativeRendering) {
    try { call(modes, 'AquariumLight', { Night: next }); }
    catch (_) { return false; }
  }
  night = next;
  return true;
}

function draw(now) {
  const elapsed = Math.max(0, now - started);
  const updates = [], commands = [], next = { ...rendered };
  const rowBounds = {};
  const pathOf = node => '/main/' + node;
  function changed(node, key, value) {
    const address = node + ':' + key;
    next[address] = value;
    return rendered[address] !== value;
  }
  function bind(node, key, value) {
    if (!changed(node, key, value)) return false;
    updates.push({ Path: pathOf(node), Key: key, Value: String(value) });
    return true;
  }
  function image(node, src) {
    if (!changed(node, 'src', src)) return false;
    commands.push({ Name: 'SetViewSrc', Params: { Path: pathOf(node), Src: src } });
    return true;
  }
  function markRows(kind, y, oldY, height) {
    const bounds = rowBounds[kind];
    rowBounds[kind] = {
      top: Math.min(y, oldY, bounds?.top ?? Infinity),
      bottom: Math.max(Math.max(y, oldY) + height, bounds?.bottom ?? -Infinity),
    };
  }
  bind('nativeSurface', 'hidden', !nativeRendering);
  const legacyVisible = !nativeRendering && !nativeRetryAt;
  bind('legacy', 'hidden', !legacyVisible);
  if (legacyVisible) {
    for (let band = 0; band < BACKDROP_BANDS; band++) image('legacy/backdrop' + band, (night ? 'night' : 'day') + band);
    const y = 388 - Math.floor(elapsed / (night ? 68 : 43)) % 305;
    const oldY = rendered['legacy/bubble:y'] ?? y;
    if (bind('legacy/bubble', 'y', y) && !cachedRows) {
      rowBounds.bubble = { top: Math.min(y, oldY), bottom: Math.max(y, oldY) + BUBBLE_DIAMETER };
    }
  }
  bind('sheet', 'hidden', !panel);
  bind('sheet/description', 'text', NOTES[selected]);
  bind('sheet/stockStatus', 'text', stockError ||
    speciesCount(stock) + '/' + MAX_SPECIES + ' 种 · ' + (inTank(selected) ? '已选' : '未选'));
  for (const name of KINDS) {
    const stocked = inTank(name);
    bind('sheet/' + name, 'color', stocked ? '#23564F' : '#103740');
    bind('sheet/' + name, 'edge', stocked ? '#A0D2B2' : '#467D78');
    bind('sheet/' + name + '/chosen', 'hidden', !stocked);
  }
  const rippleAge = legacyVisible && ripple ? now - ripple.at : Infinity;
  bind('legacy/ripple', 'hidden', rippleAge >= 680);
  if (rippleAge < 680) {
    const diameter = 16 + Math.floor(rippleAge / 9);
    bind('legacy/ripple', 'w', diameter);
    bind('legacy/ripple', 'h', diameter);
    bind('legacy/ripple', 'x', Math.round(ripple.x - diameter / 2));
    bind('legacy/ripple', 'y', Math.round(ripple.y - diameter / 2));
  }
  if (legacyVisible) fish.forEach((item, i) => {
    const sprite = SPECIES[item.kind];
    const node = 'legacy/fish' + i;
    const y = Math.round(item.y - sprite.height / 2);
    const oldY = rendered[node + ':y'] ?? y;
    const visible = inTank(item.kind);
    const visibilityChanged = bind(node, 'hidden', !visible);
    if (!visible) {
      if (!cachedRows && visibilityChanged) markRows(item.kind, oldY, oldY, sprite.height);
      return;
    }
    const movedX = bind(node, 'x', Math.round(item.x - sprite.width / 2));
    const movedY = bind(node, 'y', y);
    const jelly = item.kind === 'jelly';
    const period = jelly || item.kind === 'turtle' ? (night ? 820 : 570) : (night ? 370 : 265);
    const phase = Math.floor((elapsed + i * 43) / period) % 2;
    const source = jelly ? 'jelly' + phase : item.kind + '_' + (item.facing > 0 ? 'r' : 'l') + phase;
    const changedPose = image(node, source);
    if (!cachedRows && (visibilityChanged || movedX || movedY || changedPose)) markRows(item.kind, y, oldY, sprite.height);
  });
  // CO5300 can leave seams on partial-width writes. Repaint complete rows
  // behind moving sprites, grouping the school to avoid overlapping updates.
  for (const [kind, bounds] of Object.entries(rowBounds)) {
    const node = 'legacy/' + kind + 'Rows';
    bind(node, 'y', bounds.top);
    bind(node, 'h', bounds.bottom - bounds.top);
    bind(node, 'color', rendered[node + ':color'] === '#000000' ? '#243C50' : '#000000');
  }
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
  const pace = night ? 0.57 : 1;
  fish.forEach((item, i) => {
    if (!inTank(item.kind)) return;
    const sprite = SPECIES[item.kind];
    const margin = sprite.width / 2 + 7;
    if (item.kind === 'jelly') {
      const drift = Math.sin(time * .34 + .6) * 6;
      const buoyancy = (item.home + Math.sin(time * .66) * 27 - item.y) * 1.4;
      item.x = clamp(item.x + drift * delta * pace, margin, 480 - margin);
      item.y = clamp(item.y + buoyancy * delta * pace, sprite.top, sprite.bottom);
      return;
    }
    if (item.kind === 'clown') {
      const reefX = 270 + Math.sin(time * .48) * 60;
      const reefY = item.home + Math.sin(time * 1.55) * 12;
      const vx = clamp((reefX - item.x) * 1.6, -sprite.speed, sprite.speed);
      item.x += vx * delta * pace;
      item.y += (reefY - item.y) * 1.35 * delta * pace;
      if (Math.abs(vx) > 6) item.facing = vx < 0 ? -1 : 1;
      return;
    }
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
  if (nativeRetryAt) {
    if (now < nativeRetryAt) return;
    startNative(now);
    if (nativeRendering) stopTimer();
    lastTick = now;
    draw(now);
    return;
  }
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
  stockError = '';
  panel = true;
}

function toggleStock(kind) {
  selected = kind;
  const next = stock ^ kindBit(kind);
  if (speciesCount(next) > MAX_SPECIES) {
    stockError = '最多 5 种，请先取消一种';
    return;
  }
  if (nativeRendering) {
    try { call(modes, 'AquariumStock', { Stock: next }); }
    catch (_) { stockError = '请稍后重试'; return; }
  }
  stock = next;
  stockError = '';
  try { call(storage, 'FSWriteText', {Path: STOCK_SETTINGS, Data: JSON.stringify({stock})}); }
  catch (_) { stockError = '本次选择未保存'; }
}

function tap(point, now) {
  if (panel) {
    panel = false;
    return;
  }
  if (nativeRendering) {
    const target = call(modes, 'AquariumTap', { X: point.x, Y: point.y });
    if (target && Object.prototype.hasOwnProperty.call(NOTES, target)) openBook(target);
    return;
  }
  const chosen = fish.find(item => {
    if (!inTank(item.kind)) return false;
    const sprite = SPECIES[item.kind];
    return Math.abs(item.x - point.x) < sprite.width * .28 &&
      Math.abs(item.y - point.y) < sprite.height * .31;
  });
  if (chosen) openBook(chosen.kind);
  else ripple = { x: clamp(point.x, 12, 468), y: clamp(point.y, 20, 412), at: now };
}

function action(name, payload, now) {
  if (paused) return;
  if (name === 'book') openBook();
  if (name === 'dismiss') panel = false;
  if (panel && Object.prototype.hasOwnProperty.call(NOTES, name)) toggleStock(name);
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

function startNative(now) {
  try { nativeRendering = call(modes, 'AquariumStart', { Night: night, Stock: stock }) === true; }
  catch (_) { nativeRendering = false; }
  nativeRetryAt = !nativeRendering && now - started < NATIVE_RETRY_LIMIT_MS ? now + NATIVE_RETRY_MS : 0;
}

function resume() {
  if (!paused) return;
  paused = false;
  panel = false;
  started = lastTick = Date.now();
  rendered = {};
  syncLighting(started);
  if (nativeAvailable) startNative(started);
  draw(started);
  if (!nativeRendering) timerId = call(timer, 'StartPeriodic', { Name: 'aquarium', IntervalMs: 50 });
  lightTimer = call(timer, 'StartPeriodic', { Name: 'aquarium_light', IntervalMs: LIGHT_INTERVAL_MS });
}

function stopTimer() {
  if (!timerId) return;
  const existing = timerId;
  timerId = 0;
  // SystemCore can dispose the timer before on_stop.
  try { call(timer, 'Stop', { TimerId: existing }); } catch (_) {}
}

function pause() {
  paused = true;
  nativeRetryAt = 0;
  touch = ripple = null;
  if (nativeRendering) {
    nativeRendering = false;
    try { call(modes, 'AquariumStop'); } catch (_) {}
  }
  stopTimer();
  if (lightTimer) {
    const existing = lightTimer;
    lightTimer = 0;
    try { call(timer, 'Stop', { TimerId: existing }); } catch (_) {}
  }
}

globalThis.brookesia_app = {
  on_start() {
    gui = brookesia.start_service('SystemGui');
    timer = brookesia.start_service('SystemTimer');
    storage = brookesia.start_service('Storage');
    const saved = readJson(STOCK_SETTINGS)?.stock;
    stock = Number.isInteger(saved) && saved >= 0 && saved <= ALL_STOCK && speciesCount(saved) <= MAX_SPECIES ?
      saved : DEFAULT_STOCK;
    try {
      modes = brookesia.start_service('DeviceModes');
      const state = call(modes, 'GetState');
      cachedRows = state.aquarium_row_cache === true;
      nativeAvailable = state.aquarium_stock === true;
    } catch (_) { cachedRows = nativeAvailable = false; }
    fish = START.map(([kind, x, y, facing]) => ({ kind, x, y, home: y, facing, cruise: facing }));
    for (const action of ACTIONS) call(gui, 'SubscribeAction', { Action: action });
    resume();
    return true;
  },
  on_timer(id, name) {
    if (paused) return true;
    const now = Date.now();
    if (name === 'aquarium_light') {
      if (syncLighting(now) && !nativeRendering) draw(now);
    } else if (!nativeRendering) tick(now);
    return true;
  },
  on_action(name, path, payload) { action(name, payload, Date.now()); return true; },
  on_pause() { pause(); return true; },
  on_resume() { resume(); return true; },
  on_stop() { pause(); return true; },
};
})();
