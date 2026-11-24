const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const src = path.join(__dirname, '../src');
const source = fs.readFileSync(path.join(src, 'app/main.js'), 'utf8');
const screen = JSON.parse(fs.readFileSync(path.join(src, 'res/screens/main.json'), 'utf8'));
const views = new Map(screen.children.map(view => ['/main/' + view.id, view]));
const touch = views.get('/main/touch');
const images = JSON.parse(fs.readFileSync(path.join(src, 'res/images/index.json'), 'utf8')).images;
const ids = new Set(images.map(image => image.id));
const at = time => Date.parse('2026-11-24T' + time + '+08:00');

assert.equal(screen.style.bgColor, '#000000');
assert.equal(views.size, 5);
assert.equal(touch.placement.height, 440);
assert.equal(images.length, 13);
for (const image of images.filter(asset => asset.id !== 'launcher_icon')) {
  const native = fs.readFileSync(path.join(src, 'res/images', image.src));
  assert.equal(native[0], 0x19);
  assert.equal(native[1], 0x12);
  assert.equal(native.readUInt16LE(4), image.width);
  assert.equal(native.readUInt16LE(6), image.height);
  assert.equal(image.preload, true);
}

function device(initial, config) {
  let now = initial, batches = 0;
  const positions = new Map(), sprites = new Map(), timers = new Set();
  class Clock extends Date { static now() { return now; } }
  const context = vm.createContext({
    Date: Clock,
    brookesia: {
      start_service: name => name,
      call_function(service, name, json) {
        const args = JSON.parse(json);
        let data;
        switch (name) {
          case 'FSReadText': data = JSON.stringify(config); break;
          case 'SubscribeAction': assert(touch.events.some(event => event.action === args.Action)); break;
          case 'StartPeriodic':
            data = 1;
            assert(!timers.has(data));
            timers.add(data);
            assert(args.IntervalMs >= 40);
            break;
          case 'Stop':
            if (!timers.delete(args.TimerId)) {
              return JSON.stringify({ success: false, error_message: 'Failed to stop timer' });
            }
            break;
          case 'ExecuteBatch':
            assert.equal(service, 'SystemGui');
            ++batches;
            for (const command of args.Commands) {
              const params = command.Params;
              if (command.Name === 'SetBindings') {
                for (const update of params.Updates) {
                  assert(Object.values(views.get(update.Path).bindings).includes(update.Key));
                  positions.set(update.Path + ':' + update.Key, Number(update.Value));
                }
              } else {
                assert.equal(command.Name, 'SetViewSrc');
                assert(views.has(params.Path) && ids.has(params.Src));
                sprites.set(params.Path, params.Src);
              }
            }
            data = { Success: true };
            break;
          default: throw Error('Unexpected service action ' + name);
        }
        return JSON.stringify({ success: true, data });
      },
    },
  });
  vm.runInContext(source, context);
  const app = context.brookesia_app;
  app.on_start();
  return {
    app, timers,
    batches: () => batches,
    eye: () => sprites.get('/main/left'),
    x: () => positions.get('/main/left:x'),
    y: () => positions.get('/main/left:y'),
    action: (which, x = 170, y = 180) => app.on_action('face' + which, '/main/touch', JSON.stringify({ x, y })),
    advance(ms) { now += ms; app.on_timer(); },
    go(time) { now = at(time); app.on_timer(); },
  };
}

const pet = device(at('10:00:00'), {});
assert.equal(pet.eye(), 'eye_open');
const first = pet.batches();
pet.advance(900);
assert.equal(pet.batches(), first, 'An unchanged frame must avoid GUI calls');
pet.action('Press'); pet.action('Release');
assert.equal(pet.eye(), 'eye_happy');
pet.advance(200);
pet.action('Press'); pet.action('Release');
assert.equal(pet.eye(), 'eye_surprised');
pet.advance(1100);
assert.equal(pet.eye(), 'eye_open');
pet.action('Press');
pet.advance(540);
assert.equal(pet.eye(), 'eye_calm');
pet.action('Release');
assert.equal(pet.eye(), 'eye_calm');
pet.advance(550);
assert.equal(pet.eye(), 'eye_open');
pet.action('Press'); pet.action('Move', 291, 89);
for (let i = 0; i < 4; i++) pet.advance(45);
assert.equal(pet.x(), 110);
assert.equal(pet.y(), 120);
pet.action('Release', 291, 89);
for (let i = 0; i < 4; i++) pet.advance(45);
assert.equal(pet.x(), 70);
assert.equal(pet.y(), 150);
pet.action('Press'); pet.action('Move', 64, 250);
pet.advance(45);
assert(pet.x() < 70);
pet.action('Cancel');
assert.equal(pet.x(), 70);
pet.action('Press', 240, 455); pet.action('Move', 240, 325); pet.action('Release', 240, 325);
assert.equal(pet.eye(), 'eye_open', 'System return strip cannot start a pet gesture');
pet.go('11:00:00');
pet.advance(3800);
assert.equal(pet.eye(), 'eye_blink');
pet.advance(180);
assert.equal(pet.eye(), 'eye_open');
pet.go('22:00:00');
assert.equal(pet.eye(), 'eye_sleep');
pet.action('Press'); pet.action('Release');
assert.equal(pet.eye(), 'eye_sleep');
pet.go('06:59:59');
assert.equal(pet.eye(), 'eye_sleep');
pet.go('07:00:00');
assert.equal(pet.eye(), 'eye_open');
pet.app.on_pause();
assert.equal(pet.timers.size, 0);
const paused = pet.batches();
pet.action('Press'); pet.advance(1000);
assert.equal(pet.batches(), paused);
pet.app.on_resume();
assert.equal(pet.timers.size, 1);
pet.app.on_resume();
assert.equal(pet.timers.size, 1);
pet.timers.clear(); // The native app manager can tear down timers before on_stop.
pet.app.on_stop();
assert.equal(pet.timers.size, 0);
pet.app.on_resume();
assert.equal(pet.timers.size, 1);
pet.app.on_stop();
assert.equal(pet.timers.size, 0);

const custom = device(at('10:01:00'), { utc_offset_minutes: 480, sleep: { start: 600, end: 620 } });
assert.equal(custom.eye(), 'eye_sleep', 'Previous custom sleep windows still work');
custom.go('10:20:00');
assert.equal(custom.eye(), 'eye_open');
const unsynced = device(0, {});
assert.equal(unsynced.eye(), 'eye_open');
console.log('Pet passed: sprite assets, tap, double tap, hold, drag, cancellation, return strip, blink, sleep and app lifecycle.');
