(function () {
'use strict';

const actions = ['back', 'wifi', 'remote', 'quiet', 'lock', 'brightness', 'volume'];
let gui, core, modes, wifi, display, audio, phone, timer;
let refreshTimer = 0;
let outputId = null;
let active = false;
let previous = {};

function call(service, name, args = {}) {
  const reply = JSON.parse(brookesia.call_function(service, name, JSON.stringify(args)));
  if (!reply.success) throw new Error(reply.error || name);
  return reply.data;
}

function binding(path, key, value) {
  return {Path: '/main/' + path, Key: key, Value: String(value)};
}

function update(values) {
  const changes = values.filter(({Path, Key, Value}) => previous[Path + ':' + Key] !== Value);
  if (!changes.length) return;
  call(gui, 'SetBindings', {Updates: changes});
  for (const {Path, Key, Value} of changes) previous[Path + ':' + Key] = Value;
}

function toggle(values, id, on, label) {
  values.push(binding(id, 'fill', on ? '#D5F588' : '#1D2922'),
    binding(id + '/title', 'ink', on ? '#172213' : '#F3F6ED'),
    binding(id + '/state', 'ink', on ? '#3F572B' : '#A7B2A9'),
    binding(id + '/state', 'text', label));
}

function valuesForLevel(values, id, value, initialize) {
  if (!Number.isFinite(value) || value < 0) return;
  values.push(binding(id + '/value', 'text', value + '%'));
  if (initialize) values.push(binding(id + '/slider', 'value', value));
}

function render(initialize) {
  const settings = call(modes, 'GetState');
  const connected = call(wifi, 'GetGeneralState');
  const provision = call(phone, 'GetState');
  const remote = provision.mode === 'remote' && (provision.starting || provision.active);
  const power = settings.battery_status & 255;
  const values = [binding('battery', 'text', Number.isFinite(power) && power <= 100 && power >= 0 ? power + '%' : '--')];
  toggle(values, 'wifi', connected === 'Connected', connected === 'Connected' ? '已连接' :
    connected === 'Connecting' ? '正在连接' : '未连接');
  toggle(values, 'remote', remote, remote ? (provision.ble_connected ? '已连接' : '等待连接') :
    provision.active || provision.starting ? '手机配网中' : '已关闭');
  toggle(values, 'quiet', settings.do_not_disturb,
    settings.manual_do_not_disturb ? '已开启' : settings.do_not_disturb ? '定时勿扰' : '已关闭');
  toggle(values, 'lock', settings.screen_locked, settings.screen_locked ? '已锁定' : '未锁定');
  valuesForLevel(values, 'brightness', settings.brightness_percent, initialize);
  valuesForLevel(values, 'volume', settings.resume_volume, initialize);
  update(values);
}

function report(message) {
  update([binding('status', 'text', message)]);
}

function stopRefresh() {
  active = false;
  if (!refreshTimer) return;
  const id = refreshTimer;
  refreshTimer = 0;
  // The runtime may already have cleared app timers before dispatching stop.
  try { call(timer, 'Stop', {TimerId: id}); } catch (_) {}
}

function startRefresh() {
  active = true;
  previous = {};
  render(true);
  if (!refreshTimer) refreshTimer = call(timer, 'StartPeriodic', {Name: 'quick.controls', IntervalMs: 2500});
}

function goBack() {
  const current = call(core, 'GetActiveApp');
  if (current?.manifest?.id === 'local.quickcontrols') {
    call(core, 'RequestCloseApp', {AppId: current.app_id});
  }
}

function handle(name, payload) {
  switch (name) {
  case 'back':
    goBack();
    return;
  case 'wifi': {
    const state = call(wifi, 'GetGeneralState');
    const action = state === 'Connected' || state === 'Connecting' ? 'Disconnect' : 'Connect';
    if (action === 'Connect' && (state === 'Idle' || state === 'Inited')) {
      call(wifi, 'TriggerGeneralAction', {Action: 'Start'});
    }
    call(wifi, 'TriggerGeneralAction', {Action: action});
    break;
  }
  case 'remote': {
    const state = call(phone, 'GetState');
    const running = state.active || state.starting;
    if (running && state.mode !== 'remote') {
      report('手机配网正在进行');
      return;
    }
    call(phone, running ? 'Stop' : 'StartRemote');
    break;
  }
  case 'quiet': {
    const state = call(modes, 'GetState');
    call(modes, 'SetDoNotDisturb', {Enabled: !state.manual_do_not_disturb});
    break;
  }
  case 'lock':
    call(modes, 'LockScreen');
    return;
  case 'brightness':
  case 'volume': {
    const value = JSON.parse(payload || '{}').value;
    if (!Number.isFinite(value)) return;
    const level = Math.round(Math.max(name === 'brightness' ? 3 : 0, Math.min(100, value)));
    if (name === 'brightness') {
      if (outputId === null) throw new Error('屏幕亮度暂不可用');
      call(display, 'SetBacklightBrightness', {OutputId: outputId, Brightness: level});
    } else {
      call(audio, 'SetVolume', {Volume: level});
    }
    const values = [];
    valuesForLevel(values, name, level, true);
    update(values);
    break;
  }
  }
  report('');
  render(false);
}

globalThis.brookesia_app = {
  on_start() {
    gui = brookesia.start_service('SystemGui');
    core = brookesia.start_service('SystemCore');
    modes = brookesia.start_service('DeviceModes');
    wifi = brookesia.start_service('Wifi');
    display = brookesia.start_service('Display');
    audio = brookesia.start_service('AudioPlayback');
    phone = brookesia.start_service('PhoneProvisioning');
    timer = brookesia.start_service('SystemTimer');
    outputId = call(display, 'GetOutputs').find(output => output.backlight)?.id ?? null;
    for (const action of actions) call(gui, 'SubscribeAction', {Action: action});
    startRefresh();
    return true;
  },
  on_action(name, path, payload) {
    try { handle(name, payload); } catch (_) { report('操作未完成，请重试'); }
    return true;
  },
  on_timer(id, name) {
    if (active && name === 'quick.controls') {
      try { render(false); } catch (_) { report('暂时无法读取设备状态'); }
    }
    return true;
  },
  on_pause() { stopRefresh(); return true; },
  on_resume() { startRefresh(); return true; },
  on_stop() { stopRefresh(); return true; }
};
})();
