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
const lightButton = views.get('/main/light').placement;
const bookButton = views.get('/main/book').placement;
assert.equal(bookButton.x, lightButton.x);
assert.equal(bookButton.width, lightButton.width);
assert.equal(bookButton.height, lightButton.height);
assert.equal(bookButton.y, lightButton.y + lightButton.height + 6);
assert.equal(views.get('/main/sheet').commonProps.hidden, true);
assert.equal(views.get('/main/legacy/bubble').bindings['placement.y'], 'y');
const legacy = views.get('/main/legacy');
assert.equal(legacy.commonProps.hidden, true);
const surface = views.get('/main/nativeSurface');
assert.equal(surface.frameViewProps.colorFormat, 'RGB565');
assert.equal(surface.commonProps.hidden, true);
assert(screen.children.indexOf(surface) < screen.children.indexOf(views.get('/main/water')));
const packedScene = fs.readFileSync(path.join(src, 'res/scene.bin'));
assert.equal(packedScene.subarray(0, 4).toString(), 'AQF1');
assert.equal(packedScene.length, 4 + 4 * 160 * 160 + 6 * (50 * 39 + 38 * 40 + 25 * 14 + 30 * 33));
const grass = fs.readFileSync(path.join(src, 'res/grass.bin'));
assert.equal(grass.subarray(0, 4).toString(), 'AQG1');
const mask = grass.subarray(16, 16 + 54 * 66 + 41 * 61);
assert(mask.every(ink => ink <= 3));
assert(mask.some(ink => ink > 0));
assert.equal(grass.length, 16 + mask.length + 4 * mask.filter(Boolean).length);
assert.equal([...views.keys()].filter(id => /^\/main\/legacy\/fish\d$/.test(id)).length, 7);
const groups = { gold: [0], moon: [1], school: [2, 3, 4, 5], jelly: [6] };
for (const [i, kind] of Object.keys(groups).entries()) {
  const rows = views.get('/main/legacy/' + kind + 'Rows');
  assert.equal(legacy.children[i], rows);
  assert.equal(rows.placement.x, 0);
  assert.equal(rows.placement.width, 480);
  assert.equal(rows.style.bgOpacity, 0);
  assert.equal(rows.commonProps.clickable, false);
}
for (let band = 0; band < 8; band++) {
  const {y, width, height} = views.get('/main/legacy/backdrop' + band).placement;
  assert.deepEqual([y, width, height], [band * 60, 480, 60]);
}
for (const [id, resource] of images) {
  const file = fs.readFileSync(path.join(src, 'res/images', resource.src));
  assert(file.length > 100);
  assert(resource.preload);
  if (id === 'launcher_icon' || /^(gold_[lr]|moon_[lr]|jelly)[01]$/.test(id)) {
    assert.equal(path.extname(resource.src), '.png');
    assert.equal(file.subarray(1, 4).toString(), 'PNG');
    assert.equal(file.readUInt32BE(16), resource.width);
    assert.equal(file.readUInt32BE(20), resource.height);
    assert.equal(file[25], 6, 'RGBA preserves the transparent tail edge');
  } else {
    const hasAlpha = !/^(day|night)\d$/.test(id);
    const compressed = !hasAlpha;
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

let now = 100000, stored = '', timer = false, batches = 0, rowUpdates = 0, backdropUpdates = 0;
let firmwareRowCache = false;
let nativeStartAvailable = true;
let firmwareNative = false, nativeActive = false, nativeNight = false, nativeTap = '';
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
        case 'GetState':
          assert.equal(service, 'DeviceModes');
          data = { aquarium_row_cache: firmwareRowCache, aquarium_native_render: firmwareNative };
          break;
        case 'AquariumStart':
          assert(firmwareNative);
          nativeActive = nativeStartAvailable;
          nativeNight = args.Night;
          data = nativeStartAvailable;
          break;
        case 'AquariumStop': nativeActive = false; break;
        case 'AquariumLight':
          assert(nativeActive);
          nativeNight = args.Night;
          break;
        case 'AquariumTap':
          assert(nativeActive);
          data = nativeTap;
          break;
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
                if (update.Path.endsWith('Rows')) rowUpdates++;
                positions.set(update.Path + ':' + update.Key, update.Value);
                if (update.Key === 'text') words.set(update.Path, update.Value);
              }
            } else {
              assert.equal(command.Name, 'SetViewSrc');
              assert(views.has(p.Path) && images.has(p.Src));
              if (p.Path.startsWith('/main/legacy/backdrop')) backdropUpdates++;
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
const fishState = (i = 0) => {
  const id = '/main/legacy/fish' + i;
  return { x: Number(positions.get(id + ':x')), y: Number(positions.get(id + ':y')), pose: sources.get(id) };
};
const x = () => fishState().x;
const y = () => fishState().y;
const rowBinding = (kind, key) => positions.get('/main/legacy/' + kind + 'Rows:' + key);
function advance(count) {
  for (let i = 0; i < count; i++) {
    const prior = Array.from({ length: 7 }, (_, index) => fishState(index));
    const paints = Object.fromEntries(Object.keys(groups).map(kind => [kind, rowBinding(kind, 'color')]));
    now += 50;
    app.on_timer();
    for (const [kind, members] of Object.entries(groups)) {
      const changedRows = [];
      for (const member of members) {
        const current = fishState(member);
        const last = prior[member];
        if (current.x !== last.x || current.y !== last.y || current.pose !== last.pose) {
          const height = views.get('/main/legacy/fish' + member).placement.height;
          changedRows.push([Math.min(current.y, last.y), Math.max(current.y, last.y) + height]);
        }
      }
      if (changedRows.length) {
        const top = Math.min(...changedRows.map(row => row[0]));
        const bottom = Math.max(...changedRows.map(row => row[1]));
        assert.equal(Number(rowBinding(kind, 'y')), top);
        assert.equal(Number(rowBinding(kind, 'h')), bottom - top);
        assert.notEqual(rowBinding(kind, 'color'), paints[kind], 'Every moving species invalidates full rows');
      } else assert.equal(rowBinding(kind, 'color'), paints[kind]);
    }
  }
}
const visible = view => positions.get('/main/' + view + ':hidden') === 'false';
function assertBackdrop(mode) {
  for (let band = 0; band < 8; band++) assert.equal(sources.get('/main/legacy/backdrop' + band), mode + band);
}
app.on_start();
assert(timer);
assertBackdrop('day');
assert.equal(stored, '');
const originalGold = fishState(), initialJelly = fishState(6);
const initialBubble = Number(positions.get('/main/legacy/bubble:y'));
advance(7);
assert(Number(positions.get('/main/legacy/bubble:y')) < initialBubble, 'Legacy bubble rises');
assert.equal(Number(rowBinding('bubble', 'y')), Number(positions.get('/main/legacy/bubble:y')));
assert(x() > originalGold.x);
assert.notEqual(fishState().pose, originalGold.pose, 'Fish alternates tail poses');
assert.notEqual(fishState(6).y, initialJelly.y, 'Jellyfish bobs vertically');
assert.notEqual(fishState(6).pose, initialJelly.pose, 'Jellyfish pulses its bell');
const openedJelly = fishState(6);
tap(openedJelly.x + 30, openedJelly.y + 33);
assert(visible('sheet'));
assert.match(words.get('/main/sheet/description'), /伞盖/);
action('dismiss');

const beforeTap = x();
tap(100, 167);
assert(visible('legacy/ripple'));
advance(9);
assert(x() < beforeTap, 'Nearby curious fish approaches the disturbance');
advance(80);
assert(!visible('legacy/ripple'));

tap(x() + 75, y() + 58);
assert(visible('sheet'));
assert.match(words.get('/main/sheet/description'), /好奇/);
action('moon');
assert.match(words.get('/main/sheet/description'), /慢热/);
action('jelly');
assert.match(words.get('/main/sheet/description'), /漂浮/);
action('dismiss');
assert(!visible('sheet'));
action('waterPress', {x: 240, y: 458});
action('waterRelease', {x: 240, y: 340});
assert(!visible('legacy/ripple'), 'An upward edge swipe is left to the launcher');
action('waterPress', {x: 65, y: 85});
action('waterRelease', {x: 65, y: 140});
assert(!visible('legacy/ripple'), 'A drag is not misread as a tap');

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
firmwareRowCache = true;
const fallbackUpdates = rowUpdates;
app.on_start();
const xWithCache = x();
const staticBackdrop = backdropUpdates;
now += 100;
app.on_timer();
assert(x() > xWithCache);
assertBackdrop('night');
assert.equal(backdropUpdates, staticBackdrop, 'Swimming leaves background assets untouched');
assert.equal(rowUpdates, fallbackUpdates, 'The firmware cache owns full-row output');
app.on_stop();
firmwareNative = true;
app.on_start();
assert(nativeActive && nativeNight);
assert(!timer, 'The native animation does not start a JavaScript frame timer');
assert(visible('nativeSurface'));
assert(!visible('legacy'));
const nativeBatches = batches;
advance(6);
assert.equal(batches, nativeBatches, 'The native animation submits no JavaScript frame updates');
nativeTap = 'jelly';
tap(120, 153);
assert.match(words.get('/main/sheet/description'), /伞盖/);
action('dismiss');
action('light');
assert(!nativeNight);
assert.equal(words.get('/main/light/label'), '日景');
app.on_pause();
assert(!nativeActive);
app.on_resume();
assert(nativeActive && !nativeNight);
app.on_stop();
assert(!nativeActive);
nativeStartAvailable = false;
app.on_start();
assert(timer && !visible('legacy') && !visible('nativeSurface'));
nativeStartAvailable = true;
now += 300;
app.on_timer();
assert(nativeActive && !timer && !visible('legacy') && visible('nativeSurface'));
app.on_stop();
nativeStartAvailable = false;
app.on_start();
for (let i = 0; i < 10; i++) {
  now += 300;
  app.on_timer();
}
assert(timer && visible('legacy') && !visible('nativeSurface'));
assertBackdrop('day');
app.on_stop();
console.log('Aquarium passed: native lifecycle and controls, cached and fallback rows, seven creatures and catalog.');
