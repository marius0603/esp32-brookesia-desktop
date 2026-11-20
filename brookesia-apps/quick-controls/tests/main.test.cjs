const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const calls = [];
const settings = {battery_status: 0x14e, brightness_percent: 64, resume_volume: 38};
const responses = {
  'DeviceModes.GetState': settings,
  'Wifi.GetGeneralState': 'Connected',
  'PhoneProvisioning.GetState': {mode: 'remote', active: false},
  'Display.GetOutputs': [{id: 4, backlight: {}}],
  'SystemCore.GetActiveApp': {app_id: 18, manifest: {id: 'local.quickcontrols'}},
  'SystemTimer.StartPeriodic': 6,
};
const context = vm.createContext({brookesia: {
  start_service: name => name,
  call_function(service, method, args) {
    const name = service + '.' + method;
    const values = JSON.parse(args);
    calls.push({name, values});
    if (name === 'SystemTimer.Stop') return JSON.stringify({success: false, error: 'Already cleared'});
    return JSON.stringify({success: true, data: responses[name]});
  }
}});

vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../src/app/main.js'), 'utf8'), context);
const app = context.brookesia_app;
assert.equal(app.on_start(), true);
app.on_action('brightness', '/main/brightness/slider', '{"value":0}');
app.on_action('volume', '/main/volume/slider', '{"value":54}');
app.on_action('wifi');
app.on_action('remote');
app.on_action('quiet');
app.on_action('back');

const received = new Map(calls.map(call => [call.name, call.values]));
assert.deepEqual(received.get('Display.SetBacklightBrightness'), {OutputId: 4, Brightness: 3});
assert.deepEqual(received.get('AudioPlayback.SetVolume'), {Volume: 54});
assert.deepEqual(received.get('Wifi.TriggerGeneralAction'), {Action: 'Disconnect'});
assert.ok(received.has('PhoneProvisioning.StartRemote'));
assert.deepEqual(received.get('DeviceModes.SetDoNotDisturb'), {Enabled: true});
assert.deepEqual(received.get('SystemCore.RequestCloseApp'), {AppId: 18});
assert.equal(app.on_stop(), true);
assert.equal(app.on_stop(), true);
assert.equal(calls.filter(call => call.name === 'SystemTimer.Stop').length, 1);
console.log('Quick controls dispatch and timer cleanup passed');
