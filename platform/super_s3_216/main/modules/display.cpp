/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: CC0-1.0
 */
#include <algorithm>
#include <array>
#include <atomic>
#include <bitset>
#include <cstring>
#include <memory>
#include <string>
#include <utility>
#include <vector>
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_lv_adapter.h"
#include "lvgl.h"
#include "src/core/lv_obj_draw_private.h"
#include "src/core/lv_obj_scroll_private.h"
#include "src/draw/snapshot/lv_snapshot.h"
#include "src/misc/cache/instance/lv_image_cache.h"

#include "boost/json/array.hpp"
#include "boost/json/object.hpp"
#include "boost/json/value.hpp"

#include "private/utils.hpp"
#include "brookesia/gui_lvgl.hpp"
#include "brookesia/lib_utils/describe_helpers.hpp"
#include "brookesia/service_helper/media/display.hpp"
#include "brookesia/service_manager/helper/base.hpp"
#include "brookesia/service_manager/service/manager.hpp"
#include "display.hpp"
#include "audio_ownership.hpp"
#include "device_modes/resource_monitor.hpp"
#include "device_modes/resource_math.hpp"

extern "C" int brookesia_board_user_volume();
extern "C" bool brookesia_board_volume_muted();
extern "C" int brookesia_board_battery_status();
extern "C" bool brookesia_board_desktop_visible();
extern "C" bool brookesia_board_weather_visible();
extern "C" unsigned brookesia_panel_wide_desktop_draws();
extern "C" bool brookesia_board_screen_asleep();
extern "C" int brookesia_board_desktop_theme();

using namespace esp_brookesia;
using DisplayHelper = service::helper::Display;
using LvglDisplaySource = gui::lvgl::DisplaySource;

namespace {

constexpr uint32_t DISPLAY_SERVICE_TIMEOUT_MS = 1000;

std::atomic<bool> square_status_active{false};
std::atomic<uint32_t> square_status_fill{0x101714}, square_status_edge{0x304036}, square_status_ink{0xA7B2A9};
std::atomic<unsigned> square_wifi_state{0};

// The system layer survives application changes and full-screen app layouts.
// Read only the shared settings: querying the codec here could block the GUI.
lv_obj_t *make_status_badge(lv_obj_t *parent)
{
    auto *label=lv_label_create(parent);
    lv_obj_remove_flag(label,LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_text_font(label,&lv_font_montserrat_16,0);
    lv_obj_set_style_text_color(label,lv_color_hex(0xfff0d4),0);
    lv_obj_set_style_bg_color(label,lv_color_hex(0x3b2b29),0);
    lv_obj_set_style_bg_opa(label,LV_OPA_TRANSP,0);
    lv_obj_set_style_pad_hor(label,0,0);
    lv_obj_set_style_pad_ver(label,2,0);
    return label;
}

void update_status_bar(lv_timer_t *)
{
    static lv_obj_t *bar = nullptr;
    static std::array<lv_obj_t *, 5> badges{};
    static constexpr std::array<int, 5> square_x{28, 136, 245, 338, 431};
    static constexpr std::array<int, 5> square_width{94, 95, 80, 83, 24};
    static constexpr std::array<int, 5> legacy_x{8, 108, 210, 284, 431};
    static constexpr std::array<int, 5> legacy_width{84, 86, 58, 66, 24};
    static int previous_volume = -2, previous_battery = -1, previous_cpu = -2, previous_ram = -2;
    static int previous_theme = -1;
    static unsigned previous_wifi = 0;
    static bool was_square = false;
    static uint32_t previous_ink = 0, previous_fill = 0, previous_edge = 0;

    if (!brookesia_board_desktop_visible() || brookesia_board_screen_asleep()) {
        if (bar) lv_obj_add_flag(bar, LV_OBJ_FLAG_HIDDEN);
        return;
    }
    const bool square = square_status_active.load();
    const int theme = square ? -1 : brookesia_board_desktop_theme();
    const uint32_t ink = square ? square_status_ink.load() : theme == 1 ? 0xa7f2ff : 0xfff0d4;
    const uint32_t fill = square_status_fill.load(), edge = square_status_edge.load();
    const bool new_bar = bar == nullptr;
    if (new_bar) {
        bar = lv_obj_create(lv_layer_sys());
        lv_obj_remove_style_all(bar);
        lv_obj_remove_flag(bar, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_remove_flag(bar, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_set_size(bar, lv_pct(100), 40);
        lv_obj_align(bar, LV_ALIGN_TOP_LEFT, 0, 0);
        for (auto &label : badges) {
            label = make_status_badge(bar);
            lv_label_set_long_mode(label, LV_LABEL_LONG_CLIP);
        }
        lv_label_set_text(badges[4], LV_SYMBOL_WIFI);
    }
    if (new_bar || square != was_square || theme != previous_theme || ink != previous_ink ||
            fill != previous_fill || edge != previous_edge) {
        lv_obj_set_style_bg_color(bar, lv_color_hex(fill), 0);
        lv_obj_set_style_bg_opa(bar, square ? LV_OPA_COVER : LV_OPA_TRANSP, 0);
        lv_obj_set_style_border_side(bar, LV_BORDER_SIDE_BOTTOM, 0);
        lv_obj_set_style_border_width(bar, square ? 1 : 0, 0);
        lv_obj_set_style_border_color(bar, lv_color_hex(edge), 0);
        for (size_t i = 0; i < badges.size(); ++i) {
            lv_obj_set_style_text_color(badges[i], lv_color_hex(ink), 0);
            lv_obj_set_width(badges[i], (square ? square_width : legacy_width)[i]);
            lv_obj_align(badges[i], LV_ALIGN_TOP_LEFT, (square ? square_x : legacy_x)[i], 9);
        }
        previous_theme = theme;
        previous_ink = ink;
        previous_fill = fill;
        previous_edge = edge;
        was_square = square;
        previous_wifi = 0;
    }
    const int requested = brookesia_board_user_volume();
    const bool muted = brookesia_board_volume_muted();
    const int volume = muted ? 0 : requested;
    const int key = volume + (muted ? 101 : 0);
    if (previous_volume != key) {
        if (volume < 0) lv_label_set_text_fmt(badges[2], "%s --", LV_SYMBOL_VOLUME_MID);
        else lv_label_set_text_fmt(badges[2], "%s %d%%", volume == 0 ? LV_SYMBOL_MUTE : LV_SYMBOL_VOLUME_MID, volume);
        previous_volume = key;
    }
    const int battery = brookesia_board_battery_status();
    const int level = battery & 255;
    if (previous_battery != battery) {
        char percent[12];
        if (level <= 100) lv_snprintf(percent, sizeof(percent), "%d%%", level);
        else lv_snprintf(percent, sizeof(percent), "%s", level == 102 && (battery & 512) ? "USB" : "--");
        const char *icon = battery & 256 ? LV_SYMBOL_CHARGE : level > 100 || level <= 10 ? LV_SYMBOL_BATTERY_EMPTY :
                           level <= 35 ? LV_SYMBOL_BATTERY_1 : level <= 65 ? LV_SYMBOL_BATTERY_2 :
                           level <= 90 ? LV_SYMBOL_BATTERY_3 : LV_SYMBOL_BATTERY_FULL;
        lv_label_set_text_fmt(badges[3], "%s %s", icon, percent);
        previous_battery = battery;
    }
    const auto resources = resource_monitor::snapshot();
    const int cpu = resource_math::rounded_percent(resources.cpu_basis_points);
    const int ram = resource_math::rounded_percent(resources.ram_basis_points);
    if (previous_cpu != cpu) {
        if (cpu < 0) lv_label_set_text(badges[0], "CPU --");
        else lv_label_set_text_fmt(badges[0], "CPU %d%%", cpu);
        previous_cpu = cpu;
    }
    if (previous_ram != ram) {
        if (ram < 0) lv_label_set_text(badges[1], "RAM --");
        else lv_label_set_text_fmt(badges[1], "RAM %d%%", ram);
        previous_ram = ram;
    }
    const unsigned wifi = square ? square_wifi_state.load() : 0;
    if (new_bar || previous_wifi != wifi || !wifi) {
        if (wifi) {
            lv_obj_remove_flag(badges[4], LV_OBJ_FLAG_HIDDEN);
            lv_obj_set_style_text_opa(badges[4], wifi == 2 ? LV_OPA_COVER : LV_OPA_50, 0);
        } else {
            lv_obj_add_flag(badges[4], LV_OBJ_FLAG_HIDDEN);
        }
        previous_wifi = wifi;
    }
    if (lv_obj_has_flag(bar, LV_OBJ_FLAG_HIDDEN)) lv_obj_remove_flag(bar, LV_OBJ_FLAG_HIDDEN);
    if (square && lv_obj_get_child(lv_layer_sys(), -1) != bar) lv_obj_move_foreground(bar);
}

// Count actual render cycles, excluding idle LVGL refresh timer wakeups.
// These logs are suppressed by the normal USB session log redirection.
struct RenderStats {
    int64_t started_us = 0;
    int64_t total_us = 0;
    int64_t max_us = 0;
    uint32_t count = 0;
};
RenderStats render_stats;
struct RefreshStats {
    int64_t started = 0, last_us = 0, max_us = 0, wait_started = 0, wait_us = 0;
    int64_t flush_started_us = 0, flush_us = 0, last_flush_us = 0;
    uint32_t count = 0, strips = 0, last_strips = 0, pixels = 0, last_pixels = 0;
} refresh_stats;

uint32_t launcher_settled_refreshes = 0;
uint32_t weather_full_row_invalidations = 0;
uint32_t weather_cached_flushes = 0;
constexpr int WEATHER_WIDTH = 480;
constexpr int WEATHER_HEIGHT = 480;
constexpr size_t WEATHER_ROW_BYTES = WEATHER_WIDTH * 2;

// The LVGL port and display events use the same adapter lock. Only source
// handovers come from another task, so they post a reset for the next LVGL call.
std::atomic<bool> weather_output_changed{false};
struct WeatherRows {
    lv_obj_t *screen = nullptr;
    std::unique_ptr<uint8_t, decltype(&heap_caps_free)> pixels{nullptr, heap_caps_free};
    std::bitset<WEATHER_HEIGHT> valid_rows;
    bool allocation_attempted = false;
    bool deferred_for_audio = false;
    bool repaint = false;
} weather_rows;

bool sync_weather_rows(lv_display_t *display)
{
    auto *screen = brookesia_board_weather_visible() &&
                   lv_display_get_horizontal_resolution(display) == WEATHER_WIDTH &&
                   lv_display_get_vertical_resolution(display) == WEATHER_HEIGHT &&
                   lv_display_get_color_format(display) == LV_COLOR_FORMAT_RGB565
                   ? lv_display_get_screen_active(display) : nullptr;
    const bool output_changed = weather_output_changed.exchange(false);
    if (screen != weather_rows.screen) {
        weather_rows = {};
        weather_rows.screen = screen;
    } else if (output_changed && screen) {
        weather_rows.valid_rows.reset();
        weather_rows.repaint = true;
    }
    return screen != nullptr;
}

bool rendering_weather_frame = false;

void round_weather_refresh(lv_event_t *event)
{
    // LVGL also emits INVALIDATE_AREA for its internal draw-buffer height probe.
    // Expanding that probe to a full screen can leave the flush loop with zero rows.
    if (rendering_weather_frame) return;
    auto *display = static_cast<lv_display_t *>(lv_event_get_target(event));
    auto *area = static_cast<lv_area_t *>(lv_event_get_param(event));
    if (!sync_weather_rows(display) || !area) return;
    if (weather_rows.repaint) {
        // A source handover or failed present may have left stale pixels.
        *area = {0, 0, WEATHER_WIDTH - 1, WEATHER_HEIGHT - 1};
        ++weather_full_row_invalidations;
    } else if (!weather_rows.valid_rows.all() && (area->x1 != 0 || area->x2 != WEATHER_WIDTH - 1)) {
        // Prime the shadow from complete rows. This is also the low-memory path.
        area->x1 = 0;
        area->x2 = WEATHER_WIDTH - 1;
        ++weather_full_row_invalidations;
    }
}

// Keep the real buttons in the scroll tree for hit testing and click actions.
struct LauncherTile {
    lv_draw_buf_t buffer{};
    std::unique_ptr<uint8_t, decltype(&heap_caps_free)> pixels{nullptr, heap_caps_free};
    int x = 0;
    int y = 0;
};

struct LauncherSnapshot {
    lv_obj_t *items = nullptr;
    lv_obj_t *layer = nullptr;
    std::vector<LauncherTile> tiles;
    size_t bytes = 0;
    bool showing = false;
    bool attempted = false;
};
LauncherSnapshot launcher_snapshot;
lv_obj_t *launcher_pager = nullptr;
std::atomic<bool> launcher_assets_changed{true};
std::atomic_uint launcher_app_start_depth{0};
uint32_t launcher_cached_scrolls = 0;
uint32_t launcher_cache_build_us = 0;
constexpr size_t LAUNCHER_CACHE_LIMIT = 1152 * 1024;

bool launcher_is_visible()
{
    return launcher_pager && brookesia_board_desktop_visible() && !brookesia_board_screen_asleep() &&
           lv_obj_get_screen(launcher_pager) == lv_display_get_screen_active(lv_obj_get_display(launcher_pager));
}

bool launcher_pointer_pressed()
{
    for (auto *input = lv_indev_get_next(nullptr); input; input = lv_indev_get_next(input)) {
        if (lv_indev_get_type(input) == LV_INDEV_TYPE_POINTER && lv_indev_get_state(input) == LV_INDEV_STATE_PRESSED) {
            return true;
        }
    }
    return false;
}

void show_launcher_snapshot(bool show)
{
    if (show == launcher_snapshot.showing || !launcher_snapshot.layer) return;
    if (show) {
        lv_obj_set_style_opa_layered(launcher_snapshot.items, LV_OPA_TRANSP, LV_PART_MAIN);
        lv_obj_remove_flag(launcher_snapshot.layer, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_add_flag(launcher_snapshot.layer, LV_OBJ_FLAG_HIDDEN);
        lv_obj_remove_local_style_prop(launcher_snapshot.items, LV_STYLE_OPA_LAYERED, LV_PART_MAIN);
    }
    launcher_snapshot.showing = show;
}

void release_launcher_snapshot()
{
    show_launcher_snapshot(false);
    if (!launcher_snapshot.tiles.empty()) {
        lv_obj_clean(launcher_snapshot.layer);
        for (auto &tile : launcher_snapshot.tiles) lv_image_cache_drop(&tile.buffer);
        launcher_snapshot.tiles.clear();
        launcher_snapshot.bytes = 0;
    }
    launcher_snapshot.attempted = false;
}

void maintain_launcher_snapshot(lv_timer_t *)
{
    if (launcher_assets_changed.exchange(false)) {
        release_launcher_snapshot();
        return;
    }
    if (!launcher_is_visible()) {
        if (!launcher_snapshot.tiles.empty()) release_launcher_snapshot();
        return;
    }
    if (launcher_app_start_depth.load() != 0 || !launcher_snapshot.items || launcher_snapshot.attempted ||
            launcher_pointer_pressed() ||
            lv_obj_is_scrolling(launcher_pager) || local_audio::audiobook_busy || local_audio::radio_busy) {
        return;
    }
    auto *items = launcher_snapshot.items;
    lv_obj_update_layout(items);
    const auto width = lv_obj_get_width(items);
    const auto height = lv_obj_get_height(items);
    const auto child_count = lv_obj_get_child_count(items);
    if (width <= lv_obj_get_width(launcher_pager) || height <= 0 || !child_count) return;

    const auto started = esp_timer_get_time();
    const size_t spare = 1024 * 1024;
    const size_t available = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    if (available <= spare) return;
    const size_t budget = std::min(LAUNCHER_CACHE_LIMIT, available - spare);
    lv_area_t item_area, pager_area;
    lv_obj_get_coords(items, &item_area);
    lv_obj_get_coords(launcher_pager, &pager_area);

    std::vector<LauncherTile> tiles;
    tiles.reserve(child_count);
    size_t total_bytes = 0;
    for (uint32_t index = 0; index < child_count; ++index) {
        auto *button = lv_obj_get_child(items, index);
        if (lv_obj_has_flag(button, LV_OBJ_FLAG_HIDDEN)) continue;
        const auto extension = lv_obj_get_ext_draw_size(button);
        const auto tile_width = lv_obj_get_width(button) + 2 * extension;
        const auto tile_height = lv_obj_get_height(button) + 2 * extension;
        if (tile_width <= 0 || tile_height <= 0) return;
        const size_t bytes = size_t(tile_width) * tile_height * 4;
        if (bytes > budget - total_bytes) {
            launcher_snapshot.attempted = true;
            return;
        }

        auto &tile = tiles.emplace_back();
        tile.pixels.reset(static_cast<uint8_t *>(
            heap_caps_aligned_alloc(64, bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)));
        if (!tile.pixels ||
                lv_draw_buf_init(&tile.buffer, tile_width, tile_height, LV_COLOR_FORMAT_ARGB8888,
                                 tile_width * 4, tile.pixels.get(), bytes) != LV_RESULT_OK ||
                lv_snapshot_take_to_draw_buf(button, LV_COLOR_FORMAT_ARGB8888, &tile.buffer) != LV_RESULT_OK) {
            launcher_snapshot.attempted = true;
            return;
        }
        lv_area_t area;
        lv_obj_get_coords(button, &area);
        tile.x = area.x1 - item_area.x1 - extension;
        tile.y = area.y1 - item_area.y1 - extension;
        total_bytes += bytes;
    }
    if (tiles.empty()) return;

    // A transparent sibling follows the same scroll and clip as the original
    // buttons. Separate small pixel allocations tolerate PSRAM fragmentation.
    if (!launcher_snapshot.layer) {
        launcher_snapshot.layer = lv_obj_create(launcher_pager);
        lv_obj_remove_style_all(launcher_snapshot.layer);
        lv_obj_remove_flag(launcher_snapshot.layer, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_remove_flag(launcher_snapshot.layer, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_add_flag(launcher_snapshot.layer, LV_OBJ_FLAG_IGNORE_LAYOUT);
        lv_obj_add_flag(launcher_snapshot.layer, LV_OBJ_FLAG_HIDDEN);
    }
    lv_obj_set_size(launcher_snapshot.layer, width, height);
    lv_obj_set_pos(launcher_snapshot.layer, item_area.x1 - pager_area.x1 + lv_obj_get_scroll_x(launcher_pager),
                  item_area.y1 - pager_area.y1 + lv_obj_get_scroll_y(launcher_pager));
    launcher_snapshot.tiles = std::move(tiles);
    for (auto &tile : launcher_snapshot.tiles) {
        auto *image = lv_image_create(launcher_snapshot.layer);
        lv_obj_remove_flag(image, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_remove_flag(image, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_set_pos(image, tile.x, tile.y);
        lv_image_set_src(image, &tile.buffer);
    }
    launcher_snapshot.bytes = total_bytes;
    launcher_snapshot.attempted = true;
    launcher_cache_build_us = esp_timer_get_time() - started;
}

void start_launcher_scroll(lv_event_t *event)
{
    if (lv_event_get_target(event) == launcher_pager && launcher_is_visible() &&
            !launcher_snapshot.tiles.empty() && !launcher_assets_changed.load()) {
        show_launcher_snapshot(true);
        ++launcher_cached_scrolls;
    }
}

void launcher_items_changed(lv_event_t *event)
{
    if (lv_event_get_target(event) != launcher_snapshot.items) return;
    if (lv_event_get_code(event) == LV_EVENT_DELETE) {
        release_launcher_snapshot();
        launcher_snapshot.items = nullptr;
    }
    launcher_assets_changed.store(true);
}

void delete_launcher_pager(lv_event_t *event)
{
    if (lv_event_get_target(event) == launcher_pager) {
        // The parent's LV_EVENT_DELETE arrives while its children are alive.
        release_launcher_snapshot();
        launcher_snapshot = {};
        launcher_pager = nullptr;
    }
}

void refresh_settled_launcher(lv_event_t *event)
{
    auto *pager = static_cast<lv_obj_t *>(lv_event_get_current_target(event));
    if (lv_event_get_target(event) == pager) show_launcher_snapshot(false);
    if (lv_event_get_target(event) != pager || !brookesia_board_desktop_visible() ||
            brookesia_board_screen_asleep()) {
        return;
    }

    auto *screen = lv_obj_get_screen(pager);
    auto *display = lv_obj_get_display(pager);
    if (screen != lv_display_get_screen_active(display)) {
        return;
    }

    // Partial transfers at the viewport edge can leave a column of pixels on
    // this panel. Repaint complete rows once per scroll end, allowing the
    // ordinary partial redraws to keep the viewport responsive during a drag.
    lv_area_t area;
    lv_obj_get_coords(pager, &area);
    area.x1 = 0;
    area.x2 = lv_display_get_horizontal_resolution(display) - 1;
    if (lv_obj_invalidate_area(screen, &area) == LV_RESULT_OK) {
        ++launcher_settled_refreshes;
    }
}

void render_event(lv_event_t *event)
{
    const auto code = lv_event_get_code(event);
    const auto now = esp_timer_get_time();
    if (code == LV_EVENT_REFR_START) {
        refresh_stats.started = now;
        refresh_stats.strips = 0;
        refresh_stats.wait_us = 0;
        refresh_stats.flush_us = 0;
        refresh_stats.pixels = 0;
    } else if (code == LV_EVENT_REFR_READY && refresh_stats.started) {
        if (refresh_stats.strips) {
            refresh_stats.last_us = now-refresh_stats.started;
            refresh_stats.max_us = std::max(refresh_stats.max_us, refresh_stats.last_us);
            refresh_stats.last_strips = refresh_stats.strips;
            refresh_stats.last_flush_us = refresh_stats.flush_us;
            refresh_stats.last_pixels = refresh_stats.pixels;
            ++refresh_stats.count;
        }
        refresh_stats.started = 0;
    } else if (code == LV_EVENT_FLUSH_START) {
        ++refresh_stats.strips;
        const auto *area = static_cast<const lv_area_t *>(lv_event_get_param(event));
        if (area) refresh_stats.pixels += lv_area_get_size(area);
        refresh_stats.flush_started_us = now;
    } else if (code == LV_EVENT_FLUSH_FINISH && refresh_stats.flush_started_us) {
        refresh_stats.flush_us += now - refresh_stats.flush_started_us;
        refresh_stats.flush_started_us = 0;
    } else if (code == LV_EVENT_FLUSH_WAIT_START) {
        refresh_stats.wait_started = now;
    } else if (code == LV_EVENT_FLUSH_WAIT_FINISH && refresh_stats.wait_started) {
        refresh_stats.wait_us += now-refresh_stats.wait_started;
        refresh_stats.wait_started = 0;
    }
    if (code == LV_EVENT_RENDER_START || code == LV_EVENT_RENDER_READY) {
        rendering_weather_frame = code == LV_EVENT_RENDER_START;
    }
    if (code == LV_EVENT_RENDER_START) {
        render_stats.started_us = esp_timer_get_time();
    } else if (lv_event_get_code(event) == LV_EVENT_RENDER_READY && render_stats.started_us != 0) {
        const auto elapsed = esp_timer_get_time() - render_stats.started_us;
        render_stats.total_us += elapsed;
        render_stats.max_us = std::max(render_stats.max_us, elapsed);
        render_stats.count++;
        render_stats.started_us = 0;
    }
}

void log_render_stats(lv_timer_t *)
{
    if (render_stats.count != 0) {
        ESP_LOGI("S3_PERF", "render cycles=%lu avg_us=%lld max_us=%lld",
                 static_cast<unsigned long>(render_stats.count),
                 static_cast<long long>(render_stats.total_us / render_stats.count),
                 static_cast<long long>(render_stats.max_us));
        render_stats = {};
    }
}

} // namespace

extern "C" void brookesia_board_square_status_colors(bool enabled, uint32_t fill, uint32_t edge, uint32_t ink)
{
    square_status_fill = fill;
    square_status_edge = edge;
    square_status_ink = ink;
    square_status_active = enabled;
}

extern "C" void brookesia_board_square_wifi_status(bool visible, bool connected)
{
    square_wifi_state = visible ? (connected ? 2 : 1) : 0;
}

extern "C" void brookesia_board_lvgl_output_changed()
{
    weather_output_changed.store(true);
}

extern "C" void brookesia_board_lvgl_flush_failed(lv_display_t *display)
{
    if (sync_weather_rows(display)) {
        weather_rows.valid_rows.reset();
        weather_rows.repaint = true;
    }
}

extern "C" bool brookesia_board_prepare_lvgl_flush(
    lv_display_t *display, int *x_start, int y_start, int *x_end, int y_end, const void **pixels
)
{
    if (!sync_weather_rows(display)) return true;
    if (*x_start < 0 || *x_end > WEATHER_WIDTH || *x_start >= *x_end ||
            y_start < 0 || y_end > WEATHER_HEIGHT || y_start >= y_end || !*pixels) {
        return false;
    }

    const bool full_width = *x_start == 0 && *x_end == WEATHER_WIDTH;
    const bool full_frame = full_width && y_start == 0 && y_end == WEATHER_HEIGHT;
    if (full_frame) weather_rows.repaint = false;
    if (!weather_rows.allocation_attempted) {
        // Weather assets and locally streamed audio share the SD card during
        // app entry. Keep the original rendering path until playback is idle.
        if (local_audio::audiobook_busy.load()) {
            weather_rows.deferred_for_audio = true;
            return full_width;
        }
        weather_rows.allocation_attempted = true;
        weather_rows.pixels.reset(static_cast<uint8_t *>(
            heap_caps_malloc(WEATHER_ROW_BYTES * WEATHER_HEIGHT, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)));
        if (weather_rows.pixels) {
            weather_rows.repaint |= weather_rows.deferred_for_audio && !full_frame;
        } else {
            ESP_LOGW("S3_PERF", "Weather row cache unavailable; rendering complete rows");
        }
        weather_rows.deferred_for_audio = false;
    }
    if (!full_width && !weather_rows.valid_rows.all()) {
        // A rectangle can have been queued just before an output handover.
        // Wait for freshly painted rows before using it to form a full row.
        weather_rows.repaint = true;
        return false;
    }
    if (!weather_rows.pixels) return true;

    auto *rows = weather_rows.pixels.get() + y_start * WEATHER_ROW_BYTES;
    if (full_width) {
        std::memcpy(rows, *pixels, (y_end - y_start) * WEATHER_ROW_BYTES);
        for (int y = y_start; y < y_end; ++y) weather_rows.valid_rows.set(y);
    } else {
        const size_t dirty_bytes = (*x_end - *x_start) * 2;
        auto *dst = rows + *x_start * 2;
        const auto *src = static_cast<const uint8_t *>(*pixels);
        for (int y = y_start; y < y_end; ++y) {
            std::memcpy(dst, src, dirty_bytes);
            dst += WEATHER_ROW_BYTES;
            src += dirty_bytes;
        }
        // CO5300 still receives complete rows, including the cached pixels
        // outside the rectangle that LVGL just drew.
        *pixels = rows;
        *x_start = 0;
        *x_end = WEATHER_WIDTH;
        ++weather_cached_flushes;
    }
    return true;
}

extern "C" void brookesia_board_attach_launcher_pager(lv_obj_t *pager)
{
    launcher_pager = pager;
    lv_obj_add_event_cb(pager, start_launcher_scroll, LV_EVENT_SCROLL_BEGIN, nullptr);
    lv_obj_add_event_cb(pager, refresh_settled_launcher, LV_EVENT_SCROLL_END, nullptr);
    lv_obj_add_event_cb(pager, delete_launcher_pager, LV_EVENT_DELETE, nullptr);
}

extern "C" void brookesia_board_attach_launcher_items(lv_obj_t *items)
{
    launcher_snapshot.items = items;
    launcher_assets_changed.store(true);
    lv_obj_add_event_cb(items, launcher_items_changed, LV_EVENT_CHILD_CHANGED, nullptr);
    lv_obj_add_event_cb(items, launcher_items_changed, LV_EVENT_SIZE_CHANGED, nullptr);
    lv_obj_add_event_cb(items, launcher_items_changed, LV_EVENT_DELETE, nullptr);
}

extern "C" void brookesia_board_launcher_app_start(bool starting)
{
    if (!starting) {
        launcher_app_start_depth.fetch_sub(1);
        return;
    }
    // App images and GUI documents allocate PSRAM before the foreground notice.
    // Release the desktop pixels immediately and keep them released until the
    // start transaction finishes, including failure and rollback paths.
    launcher_app_start_depth.fetch_add(1);
    if (esp_lv_adapter_lock(-1) == ESP_OK) {
        release_launcher_snapshot();
        esp_lv_adapter_unlock();
    }
}

extern "C" void brookesia_board_launcher_assets_changed()
{
    launcher_assets_changed.store(true);
}

namespace {
constexpr int LAUNCHER_SWEEP_STEPS = 12;
struct LauncherSweep {
    lv_timer_t *timer = nullptr;
    lv_obj_t *pager = nullptr;
    int width = 0;
    int origin = 0;
    int position = 0;
    int step = 0;
    int64_t previous_done = 0;
    bool cached = false;
    bool interrupted = false;
    boost::json::array frames;
} launcher_sweep;

void finish_launcher_sweep()
{
    lv_timer_delete(launcher_sweep.timer);
    launcher_sweep.timer = nullptr;
}

void measure_launcher_frame(lv_timer_t *)
{
    if (!launcher_is_visible() || launcher_sweep.pager != launcher_pager ||
            launcher_pointer_pressed() || launcher_app_start_depth.load()) {
        launcher_sweep.interrupted = true;
        show_launcher_snapshot(false);
        finish_launcher_sweep();
        return;
    }

    auto *display = lv_obj_get_display(launcher_pager);
    if (!launcher_sweep.previous_done) {
        if (launcher_sweep.cached) {
            lv_obj_send_event(launcher_pager, LV_EVENT_SCROLL_BEGIN, nullptr);
            if (!launcher_snapshot.showing) {
                launcher_sweep.interrupted = true;
                finish_launcher_sweep();
                return;
            }
        }
        lv_refr_now(display);
        launcher_sweep.previous_done = esp_timer_get_time();
        return;
    }

    const auto i = ++launcher_sweep.step;
    const int fraction = i <= LAUNCHER_SWEEP_STEPS ? i : 2 * LAUNCHER_SWEEP_STEPS - i;
    const int direction = launcher_sweep.origin == 0 ? 1 : -1;
    const int next = launcher_sweep.origin + direction * launcher_sweep.width * fraction / LAUNCHER_SWEEP_STEPS;
    const auto started = esp_timer_get_time();
    lv_obj_scroll_by_raw(launcher_pager, launcher_sweep.position - next, 0);
    lv_refr_now(display);
    const auto done = esp_timer_get_time();
    launcher_sweep.frames.push_back(boost::json::object{
        {"refresh_us",done - started},{"interval_us",done - launcher_sweep.previous_done},
        {"flush_us",refresh_stats.last_flush_us},{"pixels",refresh_stats.last_pixels}});
    launcher_sweep.previous_done = done;
    launcher_sweep.position = next;
    if (i == 2 * LAUNCHER_SWEEP_STEPS) {
        lv_obj_send_event(launcher_pager, LV_EVENT_SCROLL_END, nullptr);
        finish_launcher_sweep();
    }
}
} // namespace

bool board_start_launcher_profile(bool cached)
{
    if (launcher_sweep.timer || !launcher_is_visible() || launcher_pointer_pressed() ||
            lv_obj_is_scrolling(launcher_pager) || !launcher_snapshot.items) return false;
    if (cached && (launcher_snapshot.tiles.empty() || launcher_assets_changed.load())) return false;

    const auto width = lv_obj_get_width(launcher_pager);
    const auto x = lv_obj_get_scroll_x(launcher_pager);
    if (width < 100 || (x != 0 && x != width) || lv_obj_get_width(launcher_snapshot.items) < 2 * width) {
        return false;
    }

    // Keep the diagnostic on the native GUI task, yielding between frames.
    launcher_sweep = {};
    launcher_sweep.pager = launcher_pager;
    launcher_sweep.width = width;
    launcher_sweep.origin = x;
    launcher_sweep.position = x;
    launcher_sweep.cached = cached;
    launcher_sweep.frames.reserve(2 * LAUNCHER_SWEEP_STEPS);
    launcher_sweep.timer = lv_timer_create(measure_launcher_frame, 5, nullptr);
    return launcher_sweep.timer != nullptr;
}

boost::json::object board_launcher_profile_result()
{
    if (launcher_sweep.timer) return {{"running",true}};
    return {{"running",false},{"cached",launcher_sweep.cached},{"interrupted",launcher_sweep.interrupted},
            {"frames",launcher_sweep.frames},{"build_us",launcher_cache_build_us},
            {"cache_bytes",launcher_snapshot.bytes}};
}

boost::json::object board_display_profile(bool force_refresh)
{
    auto *display = LvglDisplaySource::get_instance().display();
    int64_t forced_us = 0;
    if (force_refresh && display) {
        lv_obj_invalidate(lv_display_get_screen_active(display));
        const auto started = esp_timer_get_time();
        lv_refr_now(display);
        forced_us = esp_timer_get_time()-started;
    }
    boost::json::array canvases;
    const auto inspect = [&](auto &&self, lv_obj_t *object) -> void {
        if (!object) return;
        if (lv_obj_check_type(object, &lv_canvas_class)) {
            const auto *buffer = lv_canvas_get_draw_buf(object);
            if (buffer && buffer->data && buffer->header.w > 26 && buffer->header.h > 26) {
                const auto corner = lv_canvas_get_px(object, 0, 0);
                const auto inside = lv_canvas_get_px(object, 26, 26);
                canvases.push_back(boost::json::object{
                    {"width",buffer->header.w},{"height",buffer->header.h},
                    {"bytes",uint64_t(buffer->header.stride)*buffer->header.h},
                    {"corner_rgb",uint32_t(corner.red)<<16 | uint32_t(corner.green)<<8 | corner.blue},
                    {"inside_rgb",uint32_t(inside.red)<<16 | uint32_t(inside.green)<<8 | inside.blue}});
            }
        }
        for (uint32_t i=0; i<lv_obj_get_child_count(object); ++i) self(self,lv_obj_get_child(object,i));
    };
    if (display) {
        inspect(inspect,lv_display_get_layer_bottom(display));
        inspect(inspect,lv_display_get_screen_active(display));
        inspect(inspect,lv_display_get_layer_top(display));
        inspect(inspect,lv_display_get_layer_sys(display));
    }
    return {{"launcher_settled_refreshes",launcher_settled_refreshes},
            {"launcher_wide_dma_transfers",brookesia_panel_wide_desktop_draws()},
            {"launcher_cache_ready",!launcher_snapshot.tiles.empty() && !launcher_assets_changed.load()},
            {"launcher_cached_scrolls",launcher_cached_scrolls},
            {"weather_full_row_invalidations",weather_full_row_invalidations},
            {"weather_cached_flushes",weather_cached_flushes},{"weather_cache_ready",weather_rows.valid_rows.all()},
            {"refresh_count",refresh_stats.count},{"last_refresh_us",refresh_stats.last_us},
            {"max_refresh_us",refresh_stats.max_us},{"last_strips",refresh_stats.last_strips},
            {"flush_callback_us",refresh_stats.last_flush_us},{"flushed_pixels",refresh_stats.last_pixels},
            {"flush_wait_us",refresh_stats.wait_us},{"forced_refresh_us",forced_us},{"canvases",std::move(canvases)}};
}

bool Display::start(const Config &config)
{
    BROOKESIA_LOG_TRACE_GUARD();

    gesture_data_ = config.gesture_data;

    BROOKESIA_CHECK_FALSE_RETURN(start_display_service(), false, "Failed to start display service");
    BROOKESIA_CHECK_FALSE_RETURN(start_lvgl_display_source(config.lvgl_task_core_id), false, "Failed to start LVGL");
    BROOKESIA_CHECK_FALSE_RETURN(set_active_lvgl_source(), false, "Failed to activate LVGL source");
    BROOKESIA_CHECK_FALSE_RETURN(start_gesture(), false, "Failed to start display gesture");

    if (display_backlight_supported_) {
        auto result = DisplayHelper::call_function_async(
                          DisplayHelper::FunctionId::SetBacklightOnOff, display_output_id_, true
                      );
        BROOKESIA_CHECK_FALSE_RETURN(result, false, "Failed to set backlight on");
    }

    return true;
}

bool Display::start_display_service()
{
    BROOKESIA_LOG_TRACE_GUARD_WITH_THIS();

    BROOKESIA_CHECK_FALSE_RETURN(DisplayHelper::is_available(), false, "Display service is not available");

    display_service_binding_ = service::ServiceManager::get_instance().bind(DisplayHelper::get_name().data());
    BROOKESIA_CHECK_FALSE_RETURN(display_service_binding_.is_valid(), false, "Failed to bind Display service");

    auto outputs_json = DisplayHelper::call_function_sync<boost::json::array>(
                            DisplayHelper::FunctionId::GetOutputs,
                            service::helper::Timeout(DISPLAY_SERVICE_TIMEOUT_MS)
                        );
    BROOKESIA_CHECK_FALSE_RETURN(
        outputs_json.has_value(), false, "Failed to get Display outputs: %1%", outputs_json.error()
    );

    std::vector<DisplayHelper::OutputInfo> outputs;
    BROOKESIA_CHECK_FALSE_RETURN(
        BROOKESIA_DESCRIBE_FROM_JSON(boost::json::value(outputs_json.value()), outputs), false,
        "Failed to parse Display outputs"
    );
    BROOKESIA_CHECK_FALSE_RETURN(!outputs.empty(), false, "No Display output is available");

    const auto &main_output = outputs.front();
    BROOKESIA_CHECK_FALSE_RETURN(
        (main_output.width > 0) && (main_output.height > 0), false,
        "Invalid Display output size: %1%x%2%", main_output.width, main_output.height
    );

    display_output_name_ = main_output.name;
    display_output_id_ = main_output.id;
    display_width_ = main_output.width;
    display_height_ = main_output.height;
    display_backlight_supported_ = main_output.backlight.has_value();
    BROOKESIA_LOGI("Using Display output %1%", main_output);

    return true;
}

bool Display::start_lvgl_display_source(int core_id)
{
    BROOKESIA_LOG_TRACE_GUARD_WITH_THIS();

    gui::lvgl::DisplaySourceConfig config{};
    config.output_name = "";
    config.task_core_id = core_id;
    // Compose a whole screen before the SPI driver sends its short DMA chunks.
    // The previous 32-line buffers exposed every slow software-rendered strip.
    // One PSRAM buffer also releases the two 30 KiB internal draw buffers.
    config.buffer_height = display_height_;
    config.require_double_buffer = false;
    config.buffer_in_psram = true;

    auto &source = LvglDisplaySource::get_instance();
    BROOKESIA_CHECK_FALSE_RETURN(source.start(config), false, "Failed to start LVGL Display source");

    esp_lv_adapter_lock(-1);
    lv_display_add_event_cb(source.display(), round_weather_refresh, LV_EVENT_INVALIDATE_AREA, nullptr);
    lv_display_add_event_cb(source.display(), render_event, LV_EVENT_RENDER_START, nullptr);
    lv_display_add_event_cb(source.display(), render_event, LV_EVENT_RENDER_READY, nullptr);
    for (auto code : {LV_EVENT_REFR_START, LV_EVENT_REFR_READY, LV_EVENT_FLUSH_START, LV_EVENT_FLUSH_FINISH,
                      LV_EVENT_FLUSH_WAIT_START, LV_EVENT_FLUSH_WAIT_FINISH}) {
        lv_display_add_event_cb(source.display(), render_event, code, nullptr);
    }
    lv_timer_create(log_render_stats, 5000, nullptr);
    lv_timer_create(update_status_bar,200,nullptr);
    lv_timer_create(maintain_launcher_snapshot,180,nullptr);
    esp_lv_adapter_unlock();

    return true;
}

bool Display::set_active_lvgl_source()
{
    BROOKESIA_LOG_TRACE_GUARD_WITH_THIS();

    auto result = DisplayHelper::call_function_sync(
                      DisplayHelper::FunctionId::SetActiveSourceRole,
                      std::string(),
                      std::string(gui::lvgl::DISPLAY_SOURCE_ROLE),
                      service::helper::Timeout(DISPLAY_SERVICE_TIMEOUT_MS)
                  );
    BROOKESIA_CHECK_FALSE_RETURN(result.has_value(), false, "Failed to activate LVGL source: %1%", result.error());

    return true;
}

bool Display::start_gesture()
{
    BROOKESIA_LOG_TRACE_GUARD_WITH_THIS();

    auto config = gesture_data_;
    config.enabled = true;
    auto config_json = BROOKESIA_DESCRIBE_TO_JSON(config).as_object();
    auto result = DisplayHelper::call_function_sync(
                      DisplayHelper::FunctionId::SetTouchGestureConfig,
                      static_cast<double>(display_output_id_),
                      config_json,
                      service::helper::Timeout(DISPLAY_SERVICE_TIMEOUT_MS)
                  );
    BROOKESIA_CHECK_FALSE_RETURN(
        result.has_value(), false, "Failed to configure Display touch gesture: %1%", result.error()
    );

    BROOKESIA_LOGI("Display touch gesture enabled for output %1%", display_output_name_);

    return true;
}
