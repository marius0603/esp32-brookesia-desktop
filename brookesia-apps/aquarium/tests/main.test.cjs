const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const src = path.join(__dirname, '../src');
const read = name => JSON.parse(fs.readFileSync(path.join(src, name), 'utf8'));
const images = new Map(read('res/images/index.json').images.map(image => [image.id, image]));
const screen = read('res/screens/main.json');
const views = new Map(), actions = new Set();
function visit(node, parent = '') {
  const id = parent + '/' + node.id;
  views.set(id, node);
  for (const event of node.events || []) actions.add(event.action);
  for (const child of node.children || []) visit(child, id);
}
visit(screen);
assert.equal(views.get('/main/water').placement.height, 440);
assert.equal(views.get('/main/sheet').commonProps.hidden, true);
assert.equal([...views.keys()].filter(id => /^\/main\/fish\d$/.test(id)).length, 6);
for (let band = 0; band < 4; band++) {
  const {y, width, height} = views.get('/main/backdrop' + band).placement;
  assert.deepEqual([y, width, height], [band * 120, 480, 120]);
}
for (const [id, resource] of images) {
  const file = fs.readFileSync(path.join(src, 'res/images', resource.src));
  assert(file.length > 100);
  if (id === 'launcher_icon') {
    assert.equal(file.subarray(1, 4).toString(), 'PNG');
    assert.equal(file.readUInt32BE(16), resource.width);
    assert.equal(file.readUInt32BE(20), resource.height);
  } else {
    const hasAlpha = !/^(day|night)\d$/.test(id);
    const compressed = !hasAlpha || /^(gold|moon)_[lr]1$/.test(id);
    assert(resource.preload);
    assert.equal(file[0], 0x19);
    assert.equal(file[1], hasAlpha ? 0x14 : 0x12);
    assert.equal(file.readUInt16LE(2), compressed ? 8 : 0);
    assert.equal(file.readUInt16LE(4), resource.width);
    assert.equal(file.readUInt16LE(6), resource.height);
    assert.equal(file.readUInt16LE(8), resource.width * 2);
    const pixels = resource.width * resource.height * (hasAlpha ? 3 : 2);
    if (compressed) {
      assert.equal(file.readUInt32LE(16), file.length - 24);
      assert.equal(file.readUInt32LE(20), pixels);
    } else assert.equal(file.length, 12 + pixels);
  }
}

let now = 100000, stored = '', timer = false, batches = 0;
const positions = new Map(), sources = new Map(), words = new Map();
class Clock extends Date { static now() { return now; } }
const context = vm.createContext({
  Date: Clock,
  brookesia: {
    start_service: name => name,
    call_function(service, name, json) {
      const args = JSON.parse(json);
      let data = null;
      switch (name) {
        case 'SubscribeAction': assert(actions.has(args.Action)); break;
        case 'StartPeriodic':
          assert(!timer && args.IntervalMs === 50);
          timer = true;
          data = 1;
          break;
        case 'Stop': timer = false; break;
        case 'FSReadText': data = stored; break;
        case 'FSWriteText': stored = args.Data; break;
        case 'ExecuteBatch':
          assert.equal(service, 'SystemGui');
          batches++;
          for (const command of args.Commands) {
            const p = command.Params;
            if (command.Name === 'SetBindings') {
              for (const update of p.Updates) {
                assert(Object.values(views.get(update.Path).bindings).includes(update.Key));
                positions.set(update.Path + ':' + update.Key, update.Value);
                if (update.Key === 'text') words.set(update.Path, update.Value);
              }
            } else {
              assert.equal(command.Name, 'SetViewSrc');
              assert(views.has(p.Path) && images.has(p.Src));
              sources.set(p.Path, p.Src);
            }
          }
          data = { Success: true };
          break;
        default: throw Error('Unexpected service function ' + name);
      }
      return JSON.stringify({ success: true, data });
    },
  },
});
vm.runInContext(fs.readFileSync(path.join(src, 'app/main.js'), 'utf8'), context);
const app = context.brookesia_app;
const action = (name, value) => app.on_action(name, '/main/water', JSON.stringify(value));
const tap = (x, y) => { action('waterPress', { x, y }); action('waterRelease', { x, y }); };
const advance = count => { for (let i = 0; i < count; i++) { now += 50; app.on_timer(); } };
const x = () => Number(positions.get('/main/fish0:x'));
const y = () => Number(positions.get('/main/fish0:y'));
const visible = view => positions.get('/main/' + view + ':hidden') === 'false';
function assertBackdrop(mode) {
  for (let band = 0; band < 4; band++) assert.equal(sources.get('/main/backdrop' + band), mode + band);
}
app.on_start();
assert(timer);
assertBackdrop('day');
assert.equal(stored, '');
const original = x(), initialSource = sources.get('/main/fish0');
advance(7);
assert(x() > original);
assert.notEqual(sources.get('/main/fish0'), initialSource, 'Fish alternates tail poses');

const beforeTap = x();
tap(100, 167);
assert(visible('ripple'));
advance(9);
assert(x() < beforeTap, 'Nearby curious fish approaches the disturbance');
advance(80);
assert(!visible('ripple'));

tap(x() + 75, y() + 58);
assert(visible('sheet'));
assert.match(words.get('/main/sheet/description'), /好奇/);
action('moon');
assert.match(words.get('/main/sheet/description'), /慢热/);
action('dismiss');
assert(!visible('sheet'));
action('waterPress', {x: 240, y: 458});
action('waterRelease', {x: 240, y: 340});
assert(!visible('ripple'), 'An upward edge swipe is left to the launcher');
action('waterPress', {x: 65, y: 85});
action('waterRelease', {x: 65, y: 140});
assert(!visible('ripple'), 'A drag is not misread as a tap');

action('light');
assertBackdrop('night');
assert.equal(words.get('/main/light/label'), '夜景');
assert.deepEqual(JSON.parse(stored), { night: true });
app.on_pause();
assert(!timer);
const stopped = batches;
advance(10);
assert.equal(batches, stopped, 'Closing the app stops all drawing work');
app.on_resume();
assert(timer);
assertBackdrop('night');
app.on_stop();
app.on_start();
assertBackdrop('night');
app.on_stop();
assert(!timer);
console.log('Aquarium passed: six fish, animation, water response, fish book, night preference and lifecycle.');
