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
constexpr int band_height = 60, canvas_bands = height / band_height;
constexpr size_t band_bytes = width * band_height * sizeof(uint16_t);
constexpr int animation_ms = 40, behavior_ms = 120;
constexpr int background_bytes = background_width * background_width * 2;
constexpr const char *asset_path = "/sdcard/apps/local.aquarium/res/scene.bin";
constexpr const char *grass_path = "/sdcard/apps/local.aquarium/res/grass.bin";
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
    constexpr bool empty() const { return right <= x || bottom <= y; }
    constexpr int size() const { return empty() ? 0 : (right - x) * (bottom - y); }
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

// These crops use the original 160 by 160 artwork coordinates.
constexpr std::array grass_boxes{Rect{0,93,54,159}, Rect{119,99,160,160}};
constexpr size_t grass_header = 4 + 6 * sizeof(uint16_t);
constexpr size_t grass_cells = grass_boxes[0].size() + grass_boxes[1].size();
struct GrassRow {
    int first = 0, end = 0, bend = 0;
};
struct Bubble {
    int x, y, radius;
    Rect bounds() const { return {x-radius,y-radius,x+radius+1,y+radius+1}; }
    bool operator==(const Bubble &) const = default;
};
constexpr size_t bubble_count = 3;
constexpr int64_t food_us = 3400000, feed_cooldown_us = 5000000;
constexpr int food_x = width / 2;
constexpr int food_dx[] = {-23, -14, -5, 4, 13, 22, 28};

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
struct CanvasBand {
    lv_obj_t *view = nullptr;
    Pixels pixels{nullptr, heap_caps_free};
    lv_image_dsc_t image{};
};
struct Scene {
    lv_obj_t *surface = nullptr;
    lv_timer_t *animation = nullptr, *behavior = nullptr;
    std::array<CanvasBand, canvas_bands> canvas{};
    Assets assets{nullptr, heap_caps_free};
    Assets grass{nullptr, heap_caps_free};
    std::array<std::array<GrassRow, background_width>, grass_boxes.size()> grass_rows{};
    std::array<Bubble, bubble_count> bubbles{};
    std::array<Rect, std::size(food_dx)> pellets{};
    std::array<Fish, initial.size()> fish = initial;
    std::array<Pose, initial.size()> previous{};
    Rect previous_ripple{};
    int ripple_x = 0, ripple_y = 0;
    int64_t started = 0, last_motion = 0, ripple_at = 0;
    int64_t food_at = 0, last_feed = 0;
    uint64_t painted_pixels = 0;
    uint32_t frames = 0, decisions = 0, last_paint_us = 0;
    uint32_t grass_moves = 0, bubble_moves = 0;
    uint32_t feed_count = 0;
    bool night = false, dirty_all = true;
} scene;

uint16_t *row_pixels(int y)
{
    return scene.canvas[y / band_height].pixels.get() + (y % band_height) * width;
}

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
    scene.food_at = 0;
    scene.pellets = {};
    if (scene.surface && !deleting) lv_obj_add_flag(scene.surface, LV_OBJ_FLAG_HIDDEN);
    for (auto &band : scene.canvas) {
        if (band.view && !deleting) lv_obj_delete(band.view);
        if (band.pixels) lv_image_cache_drop(&band.image);
        band = {};
    }
    scene.assets.reset();
    scene.grass.reset();
}

bool build_canvas()
{
    for (int i = 0; i < canvas_bands; ++i) {
        auto &band = scene.canvas[i];
        if (heap_caps_get_largest_free_block(ram_caps) < band_bytes) lv_image_cache_drop(nullptr);
        band.pixels.reset(static_cast<uint16_t *>(heap_caps_malloc(band_bytes, ram_caps)));
        if (!band.pixels) return false;
        band.view = lv_image_create(scene.surface);
        if (!band.view) return false;
        lv_obj_set_pos(band.view, 0, i * band_height);
        lv_obj_set_size(band.view, width, band_height);
        lv_obj_remove_flag(band.view, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_remove_flag(band.view, LV_OBJ_FLAG_SCROLLABLE);
        band.image.header.magic = LV_IMAGE_HEADER_MAGIC;
        band.image.header.cf = LV_COLOR_FORMAT_RGB565;
        band.image.header.w = width;
        band.image.header.h = band_height;
        band.image.header.stride = width * 2;
        band.image.data_size = band_bytes;
        band.image.data = reinterpret_cast<const uint8_t *>(band.pixels.get());
    }
    return true;
}

Assets read_grass()
{
    Assets result{nullptr, heap_caps_free};
    const std::unique_ptr<FILE, decltype(&std::fclose)> file(std::fopen(grass_path, "rb"), std::fclose);
    if (!file || std::fseek(file.get(), 0, SEEK_END) != 0) return result;
    const auto bytes = std::ftell(file.get());
    if (bytes < long(grass_header + grass_cells) || bytes > long(grass_header + grass_cells * 5) ||
        std::fseek(file.get(), 0, SEEK_SET) != 0) return result;
    result.reset(static_cast<uint8_t *>(heap_caps_malloc(bytes, ram_caps)));
    if (!result || std::fread(result.get(), 1, bytes, file.get()) != size_t(bytes) ||
        std::memcmp(result.get(), "AQG1", 4) != 0) return Assets{nullptr, heap_caps_free};
    const auto *mask = result.get() + grass_header;
    const auto ink = std::count_if(mask, mask + grass_cells, [](uint8_t value) { return value != 0; });
    if (!ink || bytes != long(grass_header + grass_cells + ink * 4) ||
        std::any_of(mask, mask + grass_cells, [](uint8_t value) { return value > 3; })) {
        result.reset();
    }
    return result;
}

void mount_grass()
{
    scene.grass_rows = {};
    if (!scene.grass) return;
    const auto *mask = scene.grass.get() + grass_header;
    const auto *underpaint = mask + grass_cells;
    auto *day = scene.assets.get() + 4;
    for (size_t group = 0; group < grass_boxes.size(); ++group) {
        const auto box = grass_boxes[group];
        for (int y = box.y; y < box.bottom; ++y) {
            auto &row = scene.grass_rows[group][y];
            row.first = box.right;
            for (int x = box.x; x < box.right; ++x) {
                if (!*mask++) continue;
                row.first = std::min(row.first, x);
                row.end = x + 1;
                auto *base = day + (y * background_width + x) * 2;
                std::memcpy(base, underpaint, 2);
                std::memcpy(base + background_bytes, underpaint + 2, 2);
                underpaint += 4;
            }
        }
    }
}

Rect move_grass(size_t group, float sway)
{
    const auto box = grass_boxes[group];
    const float height = box.bottom - box.y - 1;
    Rect changed{};
    for (int y = box.y; y < box.bottom; ++y) {
        auto &row = scene.grass_rows[group][y];
        if (row.first >= row.end) continue;
        const float height_fraction = (box.bottom - 1 - y) / height;
        const int bend = std::lround(sway * height_fraction * height_fraction);
        if (bend == row.bend) continue;
        changed = unite(changed, {(row.first + std::min(bend, row.bend)) * 3, y * 3,
                                  (row.end + std::max(bend, row.bend)) * 3, (y + 1) * 3});
        row.bend = bend;
    }
    return changed;
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
    const bool feeding = scene.food_at && now - scene.food_at < food_us;
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
        if (feeding) {
            const float offset = float(int(i) - 3) * 15;
            fish.vx = std::clamp((food_x + offset - fish.x) * 1.6f, -90.f, 90.f);
            next_y = 95 + (now - scene.food_at) * .00005f + float(i % 3) * 12;
        } else if (attract && dx * dx + dy * dy < 315 * 315) {
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
        auto *dst = row_pixels(y);
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

void draw_ring(Rect dirty, int x, int y, int radius, uint16_t color, int stroke = 2)
{
    const Rect area = intersect(dirty, {x-radius,y-radius,x+radius+1,y+radius+1});
    const int inner = (radius - stroke) * (radius - stroke), outer = radius * radius;
    for (int row = area.y; row < area.bottom; ++row) {
        const int dy = (row - y) * (row - y);
        auto *dst = row_pixels(row);
        for (int col = area.x; col < area.right; ++col) {
            const int distance = (col - x) * (col - x) + dy;
            if (distance >= inner && distance <= outer) dst[col] = color;
        }
    }
}

void draw_grass(Rect dirty)
{
    if (!scene.grass) return;
    const auto *palette = reinterpret_cast<const uint16_t *>(scene.grass.get() + 4) + (scene.night ? 3 : 0);
    const auto *mask = scene.grass.get() + grass_header;
    for (size_t group = 0; group < grass_boxes.size(); ++group) {
        const auto box = grass_boxes[group];
        const int stride = box.right - box.x;
        for (int y = std::max(dirty.y, box.y * 3); y < std::min(dirty.bottom, box.bottom * 3); ++y) {
            const int source_y = y / 3;
            const auto &row = scene.grass_rows[group][source_y];
            const int left = std::max(dirty.x, (row.first + row.bend) * 3);
            const int right = std::min(dirty.right, (row.end + row.bend) * 3);
            const auto *src = mask + (source_y - box.y) * stride;
            auto *dst = row_pixels(y);
            for (int x = left; x < right;) {
                const int world_x = x / 3;
                const int end = std::min(right, (world_x + 1) * 3);
                const auto ink = src[world_x - row.bend - box.x];
                if (ink) std::fill(dst + x, dst + end, palette[ink - 1]);
                x = end;
            }
        }
        mask += box.size();
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
        auto *dst = row_pixels(y);
        for (int x = dirty.x; x < dirty.right; ++x) dst[x] = src[x / 3];
    }
    for (const auto &bubble : scene.bubbles) {
        const auto color = scene.night ? 0x4BD0 : 0x7DF5;
        draw_ring(dirty, bubble.x, bubble.y, bubble.radius, color, 1);
    }
    for (const auto &pellet : scene.pellets) {
        const auto area = intersect(pellet, dirty);
        if (area.empty()) continue;
        for (int y = area.y; y < area.bottom; ++y) {
            std::fill(row_pixels(y) + area.x, row_pixels(y) + area.right,
                      scene.night ? uint16_t{0xD64F} : uint16_t{0xFE37});
        }
    }
    if (ripple_radius) draw_ring(dirty, scene.ripple_x, scene.ripple_y, ripple_radius, 0xA75B);
    for (size_t i = 0; i < poses.size(); ++i) draw_sprite(dirty, poses[i], scene.fish[i].kind);
    draw_grass(dirty);
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
    std::array<Rect, initial.size() + 2 + 2 * bubble_count + grass_boxes.size()> dirty{};
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
    size_t next = initial.size();
    if (scene.previous_ripple != ripple) dirty[next] = unite(scene.previous_ripple, ripple);
    ++next;
    const float t = elapsed_ms * .001f;
    bool bubbles_moved = false;
    for (size_t i = 0; i < scene.bubbles.size(); ++i) {
        const Bubble bubble{397 + int(i) * 8 + int(std::lround(5 * std::sin(t * .9f + i * 1.7f))),
                            396 - int((elapsed_ms / (43 + i * 9) + i * 83) % 304), 2 + int(i % 2)};
        const auto old = scene.bubbles[i];
        if (bubble != old) {
            dirty[next] = bubble.bounds();
            if (old.radius) dirty[next + 1] = old.bounds();
            bubbles_moved = true;
        }
        scene.bubbles[i] = bubble;
        next += 2;
    }
    scene.bubble_moves += bubbles_moved;
    if (scene.grass) {
        dirty[next] = move_grass(0, 4.8f * std::sin(t * 1.17f));
        dirty[next + 1] = move_grass(1, -5.1f * std::sin(t * .93f));
        scene.grass_moves += !dirty[next].empty() || !dirty[next + 1].empty();
    }
    const auto age = now - scene.food_at;
    for (size_t i = 0; i < scene.pellets.size(); ++i) {
        Rect pellet{};
        const auto delay = int64_t(i) * 120000;
        if (scene.food_at && age >= delay && age < food_us - delay) {
            const float fall = (age - delay) * .000001f;
            const int x = food_x + food_dx[i] + int(std::sin(fall * 4 + i) * 5);
            const int y = 62 + int(fall * (44 + i * 2));
            pellet = {x, y, x + 3, y + 3};
        }
        if (pellet != scene.pellets[i]) dirty.back() = unite(dirty.back(), unite(pellet, scene.pellets[i]));
        scene.pellets[i] = pellet;
    }
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
    auto grass = read_grass();
    LvglLock lock;
    if (!lock.held || !scene.surface) return false;
    clean();
    if (!build_canvas()) {
        clean();
        return false;
    }
    scene.assets = std::move(assets);
    scene.grass = std::move(grass);
    mount_grass();
    scene.fish = initial;
    scene.previous = {};
    for (size_t i = 0; i < scene.fish.size(); ++i) scene.previous[i].mirror = scene.fish[i].direction < 0;
    scene.night = night;
    scene.dirty_all = true;
    scene.previous_ripple = {};
    scene.bubbles = {};
    scene.ripple_at = 0;
    scene.started = scene.last_motion = esp_timer_get_time();
    scene.frames = scene.decisions = scene.last_paint_us = 0;
    scene.grass_moves = scene.bubble_moves = 0;
    scene.painted_pixels = 0;
    decide(scene.started);
    animate(scene.started);
    for (auto &band : scene.canvas) lv_image_set_src(band.view, &band.image);
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
    if (!lock.held || !scene.animation) return false;
    scene.night = night;
    scene.dirty_all = true;
    return true;
}

const char *tap(int x, int y)
{
    LvglLock lock;
    if (!lock.held || !foreground() || !scene.animation) return nullptr;
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

FeedResult feed()
{
    LvglLock lock;
    if (!lock.held || !foreground() || !scene.animation) return FeedResult::NotOpen;
    const auto now = esp_timer_get_time();
    if (scene.last_feed && now - scene.last_feed < feed_cooldown_us) return FeedResult::Cooldown;
    scene.last_feed = scene.food_at = now;
    ++scene.feed_count;
    lv_timer_ready(scene.behavior);
    lv_timer_ready(scene.animation);
    return FeedResult::Accepted;
}

boost::json::object profile()
{
    LvglLock lock;
    if (!lock.held) return {};
    return {{"active",scene.animation != nullptr}, {"frames",scene.frames}, {"decisions",scene.decisions},
            {"last_paint_us",scene.last_paint_us}, {"pixels",scene.painted_pixels},
            {"grass_active",bool(scene.grass)}, {"grass_moves",scene.grass_moves}, {"bubble_moves",scene.bubble_moves},
            {"feed_count",scene.feed_count}, {"food_visible",std::any_of(scene.pellets.begin(), scene.pellets.end(),
                [](Rect pellet) { return !pellet.empty(); })}};
}
}
