#include "aquarium.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <memory>

#include "esp_heap_caps.h"
#include "esp_lv_adapter.h"
#include "esp_timer.h"
#include "lvgl.h"
#include "src/misc/cache/instance/lv_image_cache.h"

extern "C" bool brookesia_board_aquarium_visible();
extern "C" bool brookesia_board_screen_asleep();

namespace {
constexpr int width = 480, height = 480, background_width = width / 3;
constexpr int animation_ms = 40, behavior_ms = 120;
constexpr int background_bytes = background_width * background_width * 2;
constexpr const char *asset_path = "/sdcard/apps/local.aquarium/res/scene.bin";
constexpr uint32_t ram_caps = MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT;

struct Species {
    const char *name;
    int w, h, scale;
    float speed, top, bottom;
};
constexpr Species species[] = {
    {"gold", 50, 39, 3, 30, 60, 378}, {"moon", 38, 40, 3, 18, 75, 370},
    {"school", 25, 14, 2, 32, 66, 365}, {"jelly", 30, 33, 2, 0, 77, 337},
};
constexpr size_t asset_bytes = 4 + 2 * background_bytes +
    6 * (50 * 39 + 38 * 40 + 25 * 14 + 30 * 33);

struct Rect {
    int x, y, right, bottom;
    bool operator==(const Rect &) const = default;
    bool empty() const { return right <= x || bottom <= y; }
    int size() const { return empty() ? 0 : (right - x) * (bottom - y); }
};
Rect intersect(Rect a, Rect b)
{
    return {std::max(a.x,b.x),std::max(a.y,b.y),std::min(a.right,b.right),std::min(a.bottom,b.bottom)};
}
Rect unite(Rect a, Rect b)
{
    if (a.empty()) return b;
    if (b.empty()) return a;
    return {std::min(a.x,b.x),std::min(a.y,b.y),std::max(a.right,b.right),std::max(a.bottom,b.bottom)};
}

struct Fish {
    int kind;
    float x, y, home;
    int direction;
    float vx = 0, vy = 0;
};
constexpr std::array initial{
    Fish{0,234,204,204,1}, Fish{1,315,315,315,-1},
    Fish{2,333,129,129,1}, Fish{2,372,156,156,1},
    Fish{2,402,120,120,1}, Fish{2,363,96,96,1}, Fish{3,123,153,153,1},
};
struct Pose {
    Rect area{};
    int image = 0;
    bool mirror = false;
    bool operator==(const Pose &) const = default;
};

struct LvglLock {
    const bool held = esp_lv_adapter_lock(1000) == ESP_OK;
    ~LvglLock() { if (held) esp_lv_adapter_unlock(); }
};

using Pixels = std::unique_ptr<uint16_t, decltype(&heap_caps_free)>;
using Assets = std::unique_ptr<uint8_t, decltype(&heap_caps_free)>;
struct Scene {
    lv_obj_t *surface = nullptr;
    lv_timer_t *animation = nullptr, *behavior = nullptr;
    Pixels pixels{nullptr, heap_caps_free};
    Assets assets{nullptr, heap_caps_free};
    lv_image_dsc_t image{};
    std::array<Fish, initial.size()> fish = initial;
    std::array<Pose, initial.size()> previous{};
    Rect previous_ripple{};
    int ripple_x = 0, ripple_y = 0;
    int64_t started = 0, last_motion = 0, ripple_at = 0;
    uint64_t painted_pixels = 0;
    uint32_t frames = 0, decisions = 0, last_paint_us = 0;
    bool night = false, dirty_all = true;
} scene;

uint16_t blend(uint16_t below, uint16_t above, int alpha)
{
    if (alpha == 255) return above;
    if (alpha == 0) return below;
    const int inverse = 255 - alpha;
    return ((int((below >> 11) * inverse + (above >> 11) * alpha) / 255) << 11) |
           ((int(((below >> 5) & 63) * inverse + ((above >> 5) & 63) * alpha) / 255) << 5) |
           int(((below & 31) * inverse + (above & 31) * alpha) / 255);
}

void clean(bool deleting = false)
{
    if (scene.animation) lv_timer_delete(scene.animation);
    if (scene.behavior) lv_timer_delete(scene.behavior);
    scene.animation = scene.behavior = nullptr;
    if (scene.pixels) {
        if (scene.surface && !deleting) {
            lv_obj_add_flag(scene.surface, LV_OBJ_FLAG_HIDDEN);
            lv_image_set_src(scene.surface, nullptr);
        }
        lv_image_cache_drop(&scene.image);
        scene.pixels.reset();
        scene.assets.reset();
    }
}

bool foreground()
{
    return scene.surface && brookesia_board_aquarium_visible() && !brookesia_board_screen_asleep();
}

float left_edge(size_t i, const Species &spec)
{
    return i == 2 ? 102 : spec.w * spec.scale * .5f + 7;
}

void decide(int64_t now)
{
    const float t = (now - scene.started) * .000001f;
    const bool attract = scene.ripple_at && now - scene.ripple_at < 3100000;
    const Fish leader = scene.fish[2];
    constexpr float school_y[] = {27, -10, -34};
    for (size_t i = 0; i < scene.fish.size(); ++i) {
        auto &fish = scene.fish[i];
        const auto &spec = species[fish.kind];
        if (fish.kind == 3) {
            fish.vx = std::sin(t * .34f + .6f) * 6;
            fish.vy = (fish.home + std::sin(t * .66f) * 27 - fish.y) * 1.4f;
            continue;
        }
        const float side = left_edge(i, spec);
        if (fish.x <= side) fish.direction = 1;
        if (fish.x >= width - side) fish.direction = -1;
        fish.vx = fish.direction * spec.speed;
        float next_y = fish.home + std::sin(t * (fish.kind == 1 ? .59f : .83f) + i) * (scene.night ? 11 : 23);
        if (fish.kind == 2 && i > 2) {
            const float target = leader.x + leader.direction * float(i - 2) * 19;
            fish.vx = std::clamp(leader.direction * spec.speed + (target - fish.x) * .9f, -46.f, 46.f);
            next_y = leader.y + school_y[i - 3] + std::sin(t + i) * 7;
        }
        const float dx = scene.ripple_x - fish.x, dy = scene.ripple_y - fish.y;
        if (attract && dx * dx + dy * dy < 315 * 315) {
            if (fish.kind != 1) {
                const float offset = fish.kind == 0 ? -27 : (int(i) - 3) * 21;
                fish.vx = std::clamp((dx + offset) * 1.6f, -88.f, 88.f);
                next_y = scene.ripple_y + (fish.kind == 0 ? 11 : (int(i) - 3) * 19);
            } else if (std::abs(dx) < 110) {
                fish.vx = dx > 0 ? -36 : 36;
                next_y = 345;
            }
        }
        fish.vy = std::clamp((next_y - fish.y) * 1.35f, -45.f, 45.f);
    }
    ++scene.decisions;
}

void behavior_tick(lv_timer_t *)
{
    if (foreground()) decide(esp_timer_get_time());
}

const uint8_t *sprite_data(int kind, int frame)
{
    const auto *pixels = scene.assets.get() + 4 + 2 * background_bytes;
    for (int i = 0; i < kind; ++i) pixels += species[i].w * species[i].h * 6;
    return pixels + frame * species[kind].w * species[kind].h * 3;
}

void draw_sprite(Rect dirty, const Pose &pose, int kind)
{
    const Rect area = intersect(dirty, pose.area);
    if (area.empty()) return;
    const auto &spec = species[kind];
    const auto *source = reinterpret_cast<const uint16_t *>(sprite_data(kind, pose.image));
    const auto *alpha = reinterpret_cast<const uint8_t *>(source + spec.w * spec.h);
    for (int y = area.y; y < area.bottom; ++y) {
        const int base = (y - pose.area.y) / spec.scale * spec.w;
        auto *dst = scene.pixels.get() + y * width;
        for (int x = area.x; x < area.right;) {
            const int u = (x - pose.area.x) / spec.scale;
            const int at = base + (pose.mirror ? spec.w - 1 - u : u);
            const int end = std::min(area.right, pose.area.x + (u + 1) * spec.scale);
            const auto opacity = alpha[at];
            if (opacity == 255) std::fill(dst + x, dst + end, source[at]);
            else if (opacity) {
                for (int col = x; col < end; ++col) dst[col] = blend(dst[col], source[at], opacity);
            }
            x = end;
        }
    }
}

void draw_ring(Rect dirty, int x, int y, int radius, uint16_t color)
{
    const Rect area = intersect(dirty, {x-radius,y-radius,x+radius+1,y+radius+1});
    const int inner = (radius - 2) * (radius - 2), outer = radius * radius;
    for (int row = area.y; row < area.bottom; ++row) {
        const int dy = (row - y) * (row - y);
        auto *dst = scene.pixels.get() + row * width;
        for (int col = area.x; col < area.right; ++col) {
            const int distance = (col - x) * (col - x) + dy;
            if (distance >= inner && distance <= outer) dst[col] = color;
        }
    }
}

void repaint(Rect dirty, const std::array<Pose, initial.size()> &poses, int ripple_radius)
{
    constexpr Rect screen{0,0,width,height};
    dirty = intersect(dirty, screen);
    if (dirty.empty()) return;
    const auto *background = reinterpret_cast<const uint16_t *>(scene.assets.get() + 4 +
        (scene.night ? background_bytes : 0));
    for (int y = dirty.y; y < dirty.bottom; ++y) {
        const auto *src = background + y / 3 * background_width;
        auto *dst = scene.pixels.get() + y * width;
        for (int x = dirty.x; x < dirty.right; ++x) dst[x] = src[x / 3];
    }
    draw_ring(dirty, 397, 348, 3, 0x8637);
    if (ripple_radius) draw_ring(dirty, scene.ripple_x, scene.ripple_y, ripple_radius, 0xA75B);
    for (size_t i = 0; i < poses.size(); ++i) draw_sprite(dirty, poses[i], scene.fish[i].kind);
    scene.painted_pixels += uint32_t((dirty.right - dirty.x) * (dirty.bottom - dirty.y));
    lv_area_t canvas{};
    lv_obj_get_coords(scene.surface, &canvas);
    const lv_area_t area{canvas.x1 + dirty.x, canvas.y1 + dirty.y,
                         canvas.x1 + dirty.right - 1, canvas.y1 + dirty.bottom - 1};
    lv_obj_invalidate_area(scene.surface, &area);
}

void animate(int64_t now)
{
    const float pace = scene.night ? .57f : 1.f;
    const float delta = std::clamp((now - scene.last_motion) * .000001f, 0.f, .14f) * pace;
    scene.last_motion = now;
    const auto elapsed_ms = (now - scene.started) / 1000;
    std::array<Pose, initial.size()> poses{};
    std::array<Rect, initial.size() + 1> dirty{};
    for (size_t i = 0; i < scene.fish.size(); ++i) {
        auto &fish = scene.fish[i];
        const auto &spec = species[fish.kind];
        const float edge = left_edge(i, spec);
        fish.x = std::clamp(fish.x + fish.vx * delta, edge, width - edge);
        fish.y = std::clamp(fish.y + fish.vy * delta, spec.top, spec.bottom);
        const int w = spec.w * spec.scale, h = spec.h * spec.scale;
        const int x = std::lround(fish.x - w * .5f), y = std::lround(fish.y - h * .5f);
        const int period = fish.kind == 3 ? (scene.night ? 820 : 570) : (scene.night ? 370 : 265);
        const bool mirror = fish.kind != 3 && (std::abs(fish.vx) > 6 ? fish.vx < 0 : scene.previous[i].mirror);
        poses[i] = {{x,y,x+w,y+h}, int((elapsed_ms + i * 43) / period % 2), mirror};
        if (poses[i] != scene.previous[i]) dirty[i] = unite(poses[i].area, scene.previous[i].area);
    }
    const auto ripple_age = scene.ripple_at ? now - scene.ripple_at : 680000;
    const int radius = ripple_age < 680000 ? 8 + int(ripple_age / 18000) : 0;
    const Rect ripple = radius ? Rect{scene.ripple_x-radius,scene.ripple_y-radius,
                                     scene.ripple_x+radius+1,scene.ripple_y+radius+1} : Rect{};
    if (scene.previous_ripple != ripple) dirty.back() = unite(scene.previous_ripple, ripple);
    if (scene.dirty_all) {
        repaint({0,0,width,height}, poses, radius);
        scene.dirty_all = false;
    } else {
        if (std::all_of(dirty.begin(), dirty.end(), [](Rect r){ return r.empty(); })) return;
        for (size_t i = 0; i < dirty.size(); ++i) {
            auto &rect = dirty[i];
            if (rect.empty()) continue;
            for (size_t j = i + 1; j < dirty.size(); ++j) {
                if (intersect(rect, dirty[j]).empty()) continue;
                const auto combined = unite(rect, dirty[j]);
                if (combined.size() <= rect.size() + dirty[j].size()) {
                    rect = combined;
                    dirty[j] = {};
                }
            }
            repaint(rect, poses, radius);
        }
    }
    scene.previous = poses;
    scene.previous_ripple = ripple;
    scene.last_paint_us = esp_timer_get_time() - now;
    ++scene.frames;
}

void animation_tick(lv_timer_t *)
{
    if (foreground()) animate(esp_timer_get_time());
}
}

extern "C" bool brookesia_board_attach_native_frame(const char *name, lv_obj_t *surface)
{
    if (std::strcmp(name, "local.aquarium.surface") != 0) return false;
    if (scene.surface == surface) return true;
    if (scene.surface) clean();
    scene.surface = surface;
    lv_obj_add_event_cb(surface, [](lv_event_t *event) {
        if (lv_event_get_target(event) != scene.surface) return;
        clean(true);
        scene.surface = nullptr;
    }, LV_EVENT_DELETE, nullptr);
    return true;
}

namespace aquarium {
bool start(bool night)
{
    Assets assets(static_cast<uint8_t *>(heap_caps_malloc(asset_bytes, ram_caps)), heap_caps_free);
    auto *file = assets ? std::fopen(asset_path, "rb") : nullptr;
    if (!file) return false;
    const bool valid = std::fread(assets.get(), 1, asset_bytes, file) == asset_bytes &&
                       std::fgetc(file) == EOF && std::memcmp(assets.get(), "AQF1", 4) == 0;
    std::fclose(file);
    if (!valid) return false;
    LvglLock lock;
    if (!lock.held || !scene.surface) return false;
    clean();
    scene.pixels.reset(static_cast<uint16_t *>(heap_caps_malloc(width * height * 2, ram_caps)));
    if (!scene.pixels) return false;
    scene.assets = std::move(assets);
    scene.fish = initial;
    scene.previous = {};
    for (size_t i = 0; i < scene.fish.size(); ++i) scene.previous[i].mirror = scene.fish[i].direction < 0;
    scene.night = night;
    scene.dirty_all = true;
    scene.previous_ripple = {};
    scene.ripple_at = 0;
    scene.started = scene.last_motion = esp_timer_get_time();
    scene.frames = scene.decisions = scene.last_paint_us = 0;
    scene.painted_pixels = 0;
    scene.image = {};
    scene.image.header.magic = LV_IMAGE_HEADER_MAGIC;
    scene.image.header.cf = LV_COLOR_FORMAT_RGB565;
    scene.image.header.w = width;
    scene.image.header.h = height;
    scene.image.header.stride = width * 2;
    scene.image.data_size = width * height * 2;
    scene.image.data = reinterpret_cast<const uint8_t *>(scene.pixels.get());
    decide(scene.started);
    animate(scene.started);
    lv_image_set_src(scene.surface, &scene.image);
    scene.animation = lv_timer_create(animation_tick, animation_ms, nullptr);
    scene.behavior = lv_timer_create(behavior_tick, behavior_ms, nullptr);
    if (scene.animation && scene.behavior) {
        lv_obj_remove_flag(scene.surface, LV_OBJ_FLAG_HIDDEN);
        // The now-opaque native surface replaces the old decoded scenery.
        // Leave room for the display driver's full-row shadow.
        if (heap_caps_get_largest_free_block(ram_caps) < width * height * 2) lv_image_cache_drop(nullptr);
        return true;
    }
    clean();
    return false;
}

bool stop()
{
    LvglLock lock;
    if (!lock.held) return false;
    clean();
    return true;
}

bool light(bool night)
{
    LvglLock lock;
    if (!lock.held || !scene.pixels) return false;
    scene.night = night;
    scene.dirty_all = true;
    return true;
}

const char *tap(int x, int y)
{
    LvglLock lock;
    if (!lock.held || !foreground() || !scene.pixels) return nullptr;
    for (const auto &fish : scene.fish) {
        const auto &spec = species[fish.kind];
        if (std::abs(fish.x - x) < spec.w * spec.scale * .28f &&
            std::abs(fish.y - y) < spec.h * spec.scale * .31f) return spec.name;
    }
    scene.ripple_x = std::clamp(x,12,468);
    scene.ripple_y = std::clamp(y,20,412);
    scene.ripple_at = esp_timer_get_time();
    lv_timer_ready(scene.behavior);
    return "";
}

boost::json::object profile()
{
    LvglLock lock;
    if (!lock.held) return {};
    return {{"active",bool(scene.pixels)}, {"frames",scene.frames}, {"decisions",scene.decisions},
            {"last_paint_us",scene.last_paint_us}, {"pixels",scene.painted_pixels}};
}
}
