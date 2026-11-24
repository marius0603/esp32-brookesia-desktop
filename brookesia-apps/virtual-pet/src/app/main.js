(function () {
'use strict';

const SLEEP_CONFIG = '/sdcard/pets/xiaoli/schedule.json';
const ACTIONS = ['facePress', 'faceMove', 'faceRelease', 'faceCancel'];
const TICK_MS = 45;
const HOLD_MS = 530;
const DRAG_PX = 12;
const DOUBLE_TAP_MS = 300;
const EDGE_START = 440;
const POSES = {
  idle: { eye: 'open', eyeY: 150, mouth: 'idle', mouthY: 320, crownY: 30 },
  blink: { eye: 'blink', eyeY: 200, mouth: 'idle', mouthY: 320, crownY: 30 },
  happy: { eye: 'happy', eyeY: 180, mouth: 'happy', mouthY: 300, crownY: 30 },
  calm: { eye: 'calm', eyeY: 200, mouth: 'calm', mouthY: 310, crownY: 50 },
  surprised: { eye: 'surprised', eyeY: 120, mouth: 'surprised', mouthY: 300, crownY: 20 },
  sleep: { eye: 'sleep', eyeY: 210, mouth: 'sleep', mouthY: 320, crownY: 50 },
};

let gui, timer, tickId = 0, paused = true;
let sleep = { start: 1320, end: 420 };
let press, reaction = '', reactionUntil = 0, lastTap = -Infinity;
let gazeX = 0, gazeY = 0, targetX = 0, targetY = 0;
let blinkAt = 0, previousTime = 0, rendered = {}, sleeping = false;

function call(handle, name, args = {}) {
  const result = JSON.parse(brookesia.call_function(handle, name, JSON.stringify(args)));
  if (!result.success) throw new Error(result.error || result.error_message || name);
  return result.data;
}

function readSleep() {
  try {
    const storage = brookesia.start_service('Storage');
    const config = JSON.parse(call(storage, 'FSReadText', { Path: SLEEP_CONFIG }));
    const valid = value => Number.isInteger(value) && value >= 0 && value < 1440;
    if (config.utc_offset_minutes === 480 && valid(config.sleep?.start) && valid(config.sleep?.end) &&
        config.sleep.start !== config.sleep.end) return config.sleep;
  } catch (_) {}
  return { start: 1320, end: 420 };
}

function inSleepWindow(now) {
  if (now < 1704067200000 || now >= 4102444800000) return false;
  const minute = (Math.floor(now / 60000) + 480) % 1440;
  return sleep.start < sleep.end ? minute >= sleep.start && minute < sleep.end :
    minute >= sleep.start || minute < sleep.end;
}

function draw(mode) {
  const pose = POSES[mode];
  const next = {
    crownY: gazeY < 0 && mode === 'idle' ? 20 : pose.crownY,
    eye: 'eye_' + pose.eye,
    eyeY: pose.eyeY + gazeY * 10,
    leftX: 70 + gazeX * 10,
    rightX: 280 + gazeX * 10,
    mouth: 'mouth_' + pose.mouth,
    mouthX: 200 + Math.trunc(gazeX / 2) * 10,
    mouthY: pose.mouthY + Math.trunc(gazeY / 2) * 10,
  };
  const updates = [];
  const commands = [];
  for (const [field, node, key] of [
    ['crownY', 'crown', 'y'], ['leftX', 'left', 'x'], ['rightX', 'right', 'x'],
    ['eyeY', 'left', 'y'], ['eyeY', 'right', 'y'],
    ['mouthX', 'mouth', 'x'], ['mouthY', 'mouth', 'y'],
  ]) {
    if (rendered[field] !== next[field]) {
      updates.push({ Path: '/main/' + node, Key: key, Value: String(next[field]) });
    }
  }
  if (updates.length) commands.push({ Name: 'SetBindings', Params: { Updates: updates } });
  for (const [field, node] of [['eye', 'left'], ['eye', 'right'], ['mouth', 'mouth']]) {
    if (rendered[field] !== next[field]) {
      commands.push({ Name: 'SetViewSrc', Params: { Path: '/main/' + node, Src: next[field] } });
    }
  }
  if (!commands.length) return;
  const result = call(gui, 'ExecuteBatch', { Commands: commands });
  if (!result.Success) throw new Error('Pet display update failed');
  rendered = next;
}

function clearPress() {
  press = null;
  targetX = targetY = 0;
}

function reset(now) {
  clearPress();
  reaction = '';
  reactionUntil = 0;
  lastTap = -Infinity;
  gazeX = gazeY = 0;
  blinkAt = now + 3800;
}

function setReaction(value, now, duration) {
  reaction = value;
  reactionUntil = now + duration;
}

function tick(now) {
  if (paused) return;
  if (now < previousTime || now - previousTime > 60000) reset(now);
  previousTime = now;
  const shouldSleep = inSleepWindow(now);
  if (sleeping !== shouldSleep) {
    sleeping = shouldSleep;
    reset(now);
  }
  if (sleeping) {
    draw('sleep');
    return;
  }
  if (press && !press.dragged && !press.held && now - press.at >= HOLD_MS) {
    press.held = true;
    lastTap = -Infinity;
    setReaction('calm', now, Infinity);
  }
  gazeX += Math.sign(targetX - gazeX);
  gazeY += Math.sign(targetY - gazeY);
  if (now >= blinkAt + 145) blinkAt = now + 4600;
  const looking = Boolean(press?.dragged || gazeX || gazeY);
  const mode = looking ? 'idle' : now < reactionUntil ? reaction : now >= blinkAt ? 'blink' : 'idle';
  draw(mode);
}

function move(point) {
  const dx = point.x - press.x;
  const dy = point.y - press.y;
  if (!press.dragged && Math.hypot(dx, dy) < DRAG_PX) return;
  const x = Math.min(4, Math.max(-4, Math.round(dx / 15)));
  const y = Math.min(3, Math.max(-3, Math.round(dy / 15)));
  press.dragged = true;
  reactionUntil = 0;
  lastTap = -Infinity;
  targetX = x;
  targetY = y;
}

function act(name, payload, now) {
  if (paused) return;
  if (inSleepWindow(now)) {
    tick(now);
    return;
  }
  if (name === 'faceCancel') {
    clearPress();
    reactionUntil = 0;
    lastTap = -Infinity;
    tick(now);
    return;
  }
  let point;
  try { point = typeof payload === 'string' ? JSON.parse(payload) : payload; } catch (_) {}
  const valid = Number.isFinite(point?.x) && Number.isFinite(point?.y);
  if (name === 'facePress') {
    // Leave the lower edge for the system's swipe-to-return gesture.
    if (valid && point.y < EDGE_START) press = { ...point, at: now, held: false, dragged: false };
    return;
  }
  if (!press) return;
  if (name === 'faceMove') {
    if (valid) move(point);
    return;
  }
  if (name !== 'faceRelease') return;
  if (valid) move(point);
  const { held, dragged, at } = press;
  clearPress();
  if (!dragged) {
    if (held || now - at >= HOLD_MS) {
      setReaction('calm', now, 520);
      lastTap = -Infinity;
    } else if (now - lastTap <= DOUBLE_TAP_MS) {
      setReaction('surprised', now, 1050);
      lastTap = -Infinity;
    } else {
      setReaction('happy', now, 1350);
      lastTap = now;
    }
  }
  tick(now);
}

function resume() {
  if (!paused) return;
  const now = Date.now();
  paused = false;
  previousTime = now;
  rendered = {};
  reset(now);
  tick(now);
  tickId = call(timer, 'StartPeriodic', { Name: 'pet', IntervalMs: TICK_MS });
}

function pause() {
  paused = true;
  clearPress();
  if (tickId) {
    const stopped = tickId;
    tickId = 0;
    // SystemCore may have already removed the timer before dispatching on_stop.
    try { call(timer, 'Stop', { TimerId: stopped }); } catch (_) {}
  }
}

globalThis.brookesia_app = {
  on_start() {
    gui = brookesia.start_service('SystemGui');
    timer = brookesia.start_service('SystemTimer');
    brookesia.start_service('SNTP');
    sleep = readSleep();
    for (const action of ACTIONS) call(gui, 'SubscribeAction', { Action: action });
    resume();
    return true;
  },
  on_timer() { tick(Date.now()); return true; },
  on_action(name, path, payload) { act(name, payload, Date.now()); return true; },
  on_pause() { pause(); return true; },
  on_resume() { resume(); return true; },
  on_stop() { pause(); return true; },
};
})();
