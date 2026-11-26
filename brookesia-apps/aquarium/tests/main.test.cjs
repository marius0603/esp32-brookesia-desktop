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
const bookButton = views.get('/main/book').placement;
assert.deepEqual(bookButton, { mode: 'absolute', x: 18, y: 16, width: 68, height: 46 });
assert(!views.has('/main/light') && !actions.has('light'));
assert.equal(views.get('/main/sheet').commonProps.hidden, true);
assert(!views.has('/main/sheet/toggle') && !actions.has('toggle'));
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
const reef = fs.readFileSync(path.join(src, 'res/reef-fish.bin'));
assert.equal(reef.subarray(0, 4).toString(), 'AQX1');
assert.equal(reef.length, 4 + 6 * (62 * 28 + 42 * 28 + 24 * 18 + 36 * 24));
assert.equal([...views.keys()].filter(id => /^\/main\/legacy\/fish\d+$/.test(id)).length, 11);
const groups = { gold: [0], moon: [1], school: [2, 3, 4, 5], jelly: [6], shark: [7], ray: [8], clown: [9], turtle: [10] };
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
  if (id === 'launcher_icon' || /^(gold_[lr]|moon_[lr]|jelly|shark_[lr]|ray_[lr]|clown_[lr]|turtle_[lr])[01]$/.test(id)) {
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

const day = '2026-11-26';
const local = time => Date.parse(day + 'T' + time + '+08:00');
const weather = '/littlefs/weather-settings.json';
const shanghai = '/littlefs/weather-cache.json', qingdao = '/littlefs/weather-cache-qingdao.json';
const forecast = (mode, sunrise, sunset) => JSON.stringify({version:2, mode, data:{daily:{
  time:[day], sunrise:[day+'T'+sunrise], sunset:[day+'T'+sunset],
}}});
const files = new Map([
  [weather, '{"mode":"shanghai"}'],
  [shanghai, forecast('shanghai','06:35:00','16:55')],
  [qingdao, forecast('qingdao','06:47','16:44:00')],
  ['/littlefs/aquarium-settings.json', '{"night":true}'],
]);
let now = local('12:00:00'), timer = false, lightTimer = false, batches = 0, rowUpdates = 0, backdropUpdates = 0;
let firmwareRowCache = false;
let nativeStartAvailable = true;
let firmwareNative = false, nativeActive = false, nativeNight = false, nativeTap = '', lightChanges = 0;
const stockSettings = '/littlefs/aquarium-stock.json';
let nativeStock = 0;
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
          data = { aquarium_row_cache: firmwareRowCache, aquarium_stock: firmwareNative };
          break;
        case 'AquariumStart':
          assert(firmwareNative);
          nativeActive = nativeStartAvailable;
          nativeNight = args.Night;
          nativeStock = args.Stock;
          data = nativeStartAvailable;
          break;
        case 'AquariumStock':
          assert(nativeActive);
          nativeStock = args.Stock;
          break;
        case 'AquariumStop': nativeActive = false; break;
        case 'AquariumLight':
          assert(nativeActive);
          nativeNight = args.Night;
          lightChanges++;
          break;
        case 'AquariumTap':
          assert(nativeActive);
          data = nativeTap;
          break;
        case 'StartPeriodic':
          if (args.Name === 'aquarium_light') {
            assert(!lightTimer && args.IntervalMs === 30000);
            lightTimer = true;
            data = 2;
          } else {
            assert(args.Name === 'aquarium' && !timer && args.IntervalMs === 50);
            timer = true;
            data = 1;
          }
          break;
        case 'Stop':
          if (args.TimerId === 2) lightTimer = false;
          else { assert.equal(args.TimerId, 1); timer = false; }
          break;
        case 'FSReadText': data = files.get(args.Path); break;
        case 'FSWriteText':
          assert.equal(args.Path, stockSettings);
          files.set(args.Path, args.Data);
          break;
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
const checkLight = () => app.on_timer(2, 'aquarium_light');
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
    const prior = Array.from({ length: 11 }, (_, index) => fishState(index));
    const paints = Object.fromEntries(Object.keys(groups).map(kind => [kind, rowBinding(kind, 'color')]));
    now += 50;
    app.on_timer();
    for (const [kind, members] of Object.entries(groups)) {
      const changedRows = [];
      for (const member of members) {
        if (!visible('legacy/fish' + member)) continue;
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
assert(timer && lightTimer);
assertBackdrop('day');
for (const name of Object.keys(groups)) {
  for (const member of groups[name]) {
    assert.equal(visible('legacy/fish' + member), ['school', 'shark', 'ray', 'clown', 'turtle'].includes(name));
  }
}
app.on_stop();
files.set(stockSettings, '{"stock":79}');
app.on_start();
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
assert(!visible('sheet/moon/chosen'));
action('moon');
assert(visible('sheet/moon/chosen'));
action('jelly');
assert.match(words.get('/main/sheet/description'), /漂浮/);
action('jelly');
action('dismiss');
assert(!visible('sheet'));
action('waterPress', {x: 240, y: 458});
action('waterRelease', {x: 240, y: 340});
assert(!visible('legacy/ripple'), 'An upward edge swipe is left to the launcher');
action('waterPress', {x: 65, y: 85});
action('waterRelease', {x: 65, y: 140});
assert(!visible('legacy/ripple'), 'A drag is not misread as a tap');

action('book');
assert(visible('sheet'));
assert.equal(words.get('/main/sheet/stockStatus'), '5/5 种 · 已选');
action('shark');
assert.match(words.get('/main/sheet/stockStatus'), /最多 5 种，请先取消一种/);
assert(!visible('sheet/shark/chosen'));
assert.equal(JSON.parse(files.get(stockSettings)).stock, 79);
action('school');
for (const member of groups.school) assert(!visible('legacy/fish' + member));
action('turtle');
assert(visible('legacy/fish10'));
assert(visible('sheet/turtle/chosen'));
assert.equal(JSON.parse(files.get(stockSettings)).stock, 203);
action('dismiss');
now = local('16:54:59');
checkLight();
assertBackdrop('day');
now = local('16:55:00');
checkLight();
assertBackdrop('night');
app.on_pause();
assert(!timer && !lightTimer);
const stopped = batches;
advance(10);
assert.equal(batches, stopped, 'Closing the app stops all drawing work');
app.on_resume();
assert(timer && lightTimer);
assertBackdrop('night');
app.on_stop();
app.on_start();
assertBackdrop('night');
app.on_stop();
assert(!timer && !lightTimer);
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
assert.equal(nativeStock, 203, 'Reload the saved species selection in the native renderer');
assert(!timer && lightTimer, 'Native rendering only needs the lighting timer');
assert(visible('nativeSurface'));
assert(!visible('legacy'));
const nativeBatches = batches;
advance(6);
assert.equal(batches, nativeBatches, 'The native animation submits no JavaScript frame updates');
nativeTap = 'jelly';
tap(120, 153);
assert.match(words.get('/main/sheet/description'), /伞盖/);
action('turtle');
action('ray');
assert.equal(nativeStock, 107);
assert.equal(JSON.parse(files.get(stockSettings)).stock, nativeStock);
action('dismiss');
now = local('06:34:59');
checkLight();
assert(nativeNight);
now = local('06:35:00');
checkLight();
assert(!nativeNight);
assert.equal(lightChanges, 1);
checkLight();
assert.equal(lightChanges, 1, 'Unchanged lighting leaves the native frame untouched');
app.on_pause();
assert(!nativeActive && !lightTimer);
now = local('16:50:00');
files.set(weather, '{"mode":"qingdao"}');
app.on_resume();
assert(nativeActive && nativeNight, 'Qingdao uses its own sunset on resume');
files.set(weather, '{"mode":"shanghai"}');
checkLight();
assert(nativeActive && !nativeNight);
now = 100000;
checkLight();
assert(!nativeNight, 'An unset device clock preserves the current scene');
files.set(shanghai, forecast('shanghai','23:80','23:99'));
now = local('12:00:00');
checkLight();
assert(!nativeNight, 'Malformed cached boundaries fall back to local solar time');
files.delete(shanghai);
now = local('02:00:00');
checkLight();
assert(nativeNight, 'Local solar calculation works without a cache');
now = local('12:00:00');
checkLight();
assert(!nativeNight);
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
console.log('Aquarium passed: native lifecycle, fallback rows, lighting, and the five-species catalog limit.');
