#include <assert.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "esp_timer.h"
#include "nvs.h"
#include "lvgl.h"
#include "bsp/esp-bsp.h"
#include "bsp/display.h"
#include "quota_state.h"
#include "quota_hardware.h"

LV_FONT_DECLARE(quota_font);

static lv_obj_t *screen, *body, *title, *status_label;
static lv_obj_t *pages[3], *ring, *main_name, *main_percent, *main_countdown, *other_name, *other_bar, *sync_label;
static lv_obj_t *detail_rows[2], *detail_footer, *setting_text, *hint;
static lv_obj_t *volume_down, *volume_up, *volume_label, *power_button;
static lv_obj_t *power_dialog, *power_message, *power_confirm;
static QueueHandle_t key_queue;
static nvs_handle_t settings;
static bool settings_open;
static uint8_t selected = 0, brightness = 70, page = 0;
static uint8_t saved_volume = 35;
static int current_brightness = -1;
static bool manual_sleep = false;
static int64_t last_action_ms;
static lv_point_t pressed;
static bool press_woke;

static int64_t milliseconds(void) { return esp_timer_get_time() / 1000; }

static lv_obj_t *label(lv_obj_t *parent, int x, int y, int width, const lv_font_t *font, uint32_t color)
{
    lv_obj_t *obj = lv_label_create(parent);
    lv_obj_set_pos(obj, x, y);
    lv_obj_set_width(obj, width);
    lv_obj_set_style_text_font(obj, font, 0);
    lv_obj_set_style_text_color(obj, lv_color_hex(color), 0);
    lv_obj_set_style_text_align(obj, LV_TEXT_ALIGN_CENTER, 0);
    return obj;
}

static lv_obj_t *container(lv_obj_t *parent)
{
    lv_obj_t *obj = lv_obj_create(parent);
    lv_obj_remove_style_all(obj);
    lv_obj_set_size(obj, 480, 480);
    lv_obj_remove_flag(obj, LV_OBJ_FLAG_SCROLLABLE | LV_OBJ_FLAG_CLICKABLE);
    return obj;
}

static void save_settings(void)
{
    if (!settings_open) return;
    nvs_set_u8(settings, "selected", selected);
    nvs_set_u8(settings, "brightness", brightness);
    nvs_set_u8(settings, "volume", saved_volume);
    nvs_commit(settings);
}

static void set_brightness(int value)
{
    if (value != current_brightness) {
        if (bsp_display_brightness_set(value) == ESP_OK) current_brightness = value;
    }
}

static void show_page(void)
{
    for (int i = 0; i < 3; i++) {
        if (i == page) lv_obj_remove_flag(pages[i], LV_OBJ_FLAG_HIDDEN);
        else lv_obj_add_flag(pages[i], LV_OBJ_FLAG_HIDDEN);
    }
    lv_label_set_text(hint, page == 0 ? "点击切换额度  左右滑动翻页" : page == 1 ? "点击刷新  左右滑动翻页" : "点击空白区域调整亮度");
}

static bool control_wake(void)
{
    bool asleep = current_brightness == 0;
    manual_sleep = false;
    last_action_ms = milliseconds();
    set_brightness(brightness);
    return asleep;
}

static lv_obj_t *control_button(lv_obj_t *parent, int x, int y, int width, const char *text)
{
    lv_obj_t *button = lv_button_create(parent);
    lv_obj_set_pos(button, x, y);
    lv_obj_set_size(button, width, 38);
    lv_obj_t *caption = lv_label_create(button);
    lv_obj_set_style_text_font(caption, &quota_font, 0);
    lv_label_set_text(caption, text);
    lv_obj_center(caption);
    return button;
}

static void enable_control(lv_obj_t *obj, bool enable)
{
    if (enable) lv_obj_remove_state(obj, LV_STATE_DISABLED);
    else lv_obj_add_state(obj, LV_STATE_DISABLED);
}

static void volume_event(lv_event_t *event)
{
    if (control_wake()) return;
    int value;
    if (!quota_get_volume(&value)) return;
    value += lv_event_get_target(event) == volume_down ? -5 : 5;
    value = value < 0 ? 0 : value > 100 ? 100 : value;
    if (quota_set_volume(value)) {
        saved_volume = value;
        save_settings();
        lv_label_set_text_fmt(volume_label, "音量 %d%%", value);
    } else lv_label_set_text(volume_label, "调整失败");
}

static void power_cancel_event(lv_event_t *event)
{
    if (control_wake()) return;
    lv_obj_delete(power_dialog);
    power_dialog = power_message = power_confirm = NULL;
}

static void power_confirm_event(lv_event_t *event)
{
    if (control_wake()) return;
    save_settings();
    enable_control(power_confirm, false);
    lv_label_set_text(power_message, "正在关机\n再次开机请用实体电源键");
    if (quota_power_off() != ESP_OK) {
        lv_label_set_text(power_message, "关机失败，请重试");
        enable_control(power_confirm, true);
    }
}

static void power_event(lv_event_t *event)
{
    if (control_wake() || power_dialog || !quota_power_ready()) return;
    power_dialog = container(screen);
    lv_obj_add_flag(power_dialog, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_bg_color(power_dialog, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(power_dialog, LV_OPA_60, 0);
    lv_obj_t *dialog = container(power_dialog);
    lv_obj_set_size(dialog, 400, 228);
    lv_obj_center(dialog);
    lv_obj_add_flag(dialog, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_bg_color(dialog, lv_color_hex(0x172231), 0);
    lv_obj_set_style_bg_opa(dialog, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(dialog, 16, 0);
    power_message = label(dialog, 20, 25, 360, &quota_font, 0xdce7f3);
    lv_label_set_text(power_message, "确认关机？\n关机后请用实体电源键开机");
    lv_obj_t *cancel = control_button(dialog, 25, 160, 165, "取消");
    power_confirm = control_button(dialog, 210, 160, 165, "关机");
    lv_obj_set_style_bg_color(power_confirm, lv_color_hex(0xb53d50), 0);
    lv_obj_add_event_cb(cancel, power_cancel_event, LV_EVENT_CLICKED, NULL);
    lv_obj_add_event_cb(power_confirm, power_confirm_event, LV_EVENT_CLICKED, NULL);
}

static void screen_event(lv_event_t *event)
{
    lv_event_code_t code = lv_event_get_code(event);
    lv_indev_t *input = lv_indev_active();
    if (!input) return;
    if (code == LV_EVENT_PRESSED) {
        lv_indev_get_point(input, &pressed);
        press_woke = current_brightness == 0;
        manual_sleep = false;
        last_action_ms = milliseconds();
        set_brightness(brightness);
    } else if (code == LV_EVENT_RELEASED) {
        lv_point_t point;
        lv_indev_get_point(input, &point);
        last_action_ms = milliseconds();
        if (press_woke) return;
        int dx = point.x - pressed.x;
        if (abs(dx) > 70) {
            page = (page + (dx < 0 ? 1 : 2)) % 3;
            show_page();
        } else if (page == 0) {
            selected = 1 - selected;
            save_settings();
        } else if (page == 1) {
            quota_request_refresh();
        } else {
            brightness = brightness == 30 ? 50 : brightness == 50 ? 70 : brightness == 70 ? 100 : 30;
            set_brightness(brightness);
            save_settings();
        }
    }
}

static void window_name(char *out, size_t length, int minutes)
{
    if (minutes == 10080) snprintf(out, length, "每周额度");
    else if (minutes % 1440 == 0) snprintf(out, length, "%d 天额度", minutes / 1440);
    else if (minutes % 60 == 0) snprintf(out, length, "%d 小时额度", minutes / 60);
    else snprintf(out, length, "%d 分钟额度", minutes);
}

static void countdown(char *out, size_t length, int64_t reset, int64_t now)
{
    if (!reset) { snprintf(out, length, "暂无重置时间"); return; }
    int64_t seconds = reset - now;
    if (seconds <= 0) { snprintf(out, length, "等待同步"); return; }
    int64_t days = seconds / 86400;
    int hours = (seconds % 86400) / 3600, minutes = (seconds % 3600) / 60, sec = seconds % 60;
    if (days) snprintf(out, length, "重置 %" PRId64 "天 %02d:%02d:%02d", days, hours, minutes, sec);
    else snprintf(out, length, "重置 %02d:%02d:%02d", hours, minutes, sec);
}

static const char *status_text(const char *status)
{
    if (!strcmp(status, "ok")) return "额度已同步";
    if (!strcmp(status, "stale")) return "数据已过期";
    if (!strcmp(status, "auth_required")) return "请在电脑端登录 Codex";
    if (!strcmp(status, "error")) return "采集失败  保留上次数据";
    if (!strcmp(status, "starting")) return "正在连接 Codex";
    return "电脑未连接";
}

static uint32_t quota_color(float remaining, const quota_snapshot_t *snapshot, bool fresh)
{
    if (!fresh) return 0x718096;
    if (remaining <= snapshot->critical) return 0xff6878;
    return remaining <= snapshot->warning ? 0xffb759 : 0x4ce0b3;
}

static void timer_callback(lv_timer_t *timer)
{
    int64_t now_ms = milliseconds();
    int volume = 0;
    bool audio_ok = quota_get_volume(&volume);
    if (audio_ok) lv_label_set_text_fmt(volume_label, "音量 %d%%", volume);
    else lv_label_set_text(volume_label, "音量 --");
    enable_control(volume_down, audio_ok && volume > 0);
    enable_control(volume_up, audio_ok && volume < 100);
    enable_control(power_button, quota_power_ready());
    bool long_press;
    while (xQueueReceive(key_queue, &long_press, 0) == pdTRUE) {
        last_action_ms = now_ms;
        if (long_press) {
            manual_sleep = current_brightness != 0;
            set_brightness(manual_sleep ? 0 : brightness);
        } else if (current_brightness == 0) {
            manual_sleep = false;
            set_brightness(brightness);
        } else quota_request_refresh();
    }
    if (manual_sleep || now_ms - last_action_ms >= 300000) set_brightness(0);
    else if (now_ms - last_action_ms >= 60000) set_brightness(brightness < 15 ? brightness : 15);
    else set_brightness(brightness);

    quota_snapshot_t snapshot;
    quota_copy_snapshot(&snapshot);
    int64_t now = quota_estimated_now(&snapshot, now_ms);
    const char *status = quota_status(&snapshot, now_ms);
    bool fresh = !strcmp(status, "ok");
    lv_label_set_text_fmt(title, "CODEX  /  %s", snapshot.plan[0] ? snapshot.plan : "--");
    lv_label_set_text(status_label, status_text(status));
    lv_obj_set_style_text_color(status_label, lv_color_hex(fresh ? 0x4ce0b3 : 0xffb759), 0);

    const quota_window_t *window = snapshot.count ? &snapshot.windows[selected % snapshot.count] : NULL;
    float remaining = window ? 100 - window->used : 0;
    uint32_t color = quota_color(remaining, &snapshot, fresh);
    char name[64], text[192];
    if (window) {
        window_name(name, sizeof(name), window->minutes);
        lv_label_set_text(main_name, name);
        lv_label_set_text_fmt(main_percent, "%g%%", (double)remaining);
        countdown(text, sizeof(text), window->reset_at, now);
        lv_label_set_text(main_countdown, text);
        lv_arc_set_value(ring, (int)remaining);
    } else {
        lv_label_set_text(main_name, "暂无额度数据");
        lv_label_set_text(main_percent, "--");
        lv_label_set_text(main_countdown, "等待首次同步");
        lv_arc_set_value(ring, 0);
    }
    lv_obj_set_style_text_color(main_percent, lv_color_hex(color), 0);
    lv_obj_set_style_arc_color(ring, lv_color_hex(color), LV_PART_INDICATOR);
    if (snapshot.count > 1) {
        const quota_window_t *other = &snapshot.windows[(selected + 1) % snapshot.count];
        window_name(name, sizeof(name), other->minutes);
        lv_label_set_text_fmt(other_name, "%s   剩余 %g%%", name, (double)(100 - other->used));
        lv_bar_set_value(other_bar, (int)(100 - other->used), LV_ANIM_OFF);
        lv_obj_set_style_bg_color(other_bar, lv_color_hex(quota_color(100 - other->used, &snapshot, fresh)), LV_PART_INDICATOR);
        lv_obj_remove_flag(other_bar, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_label_set_text(other_name, "");
        lv_obj_add_flag(other_bar, LV_OBJ_FLAG_HIDDEN);
    }
    if (snapshot.has_sample) {
        time_t sample = (time_t)(snapshot.sampled_at + 8 * 3600);
        struct tm local;
        gmtime_r(&sample, &local);
        lv_label_set_text_fmt(sync_label, "同步 %02d:%02d:%02d  北京时间", local.tm_hour, local.tm_min, local.tm_sec);
    } else lv_label_set_text(sync_label, "等待电脑发送额度数据");

    for (int i = 0; i < 2; i++) {
        if (i < snapshot.count) {
            const quota_window_t *row = &snapshot.windows[i];
            window_name(name, sizeof(name), row->minutes);
            countdown(text, sizeof(text), row->reset_at, now);
            lv_label_set_text_fmt(detail_rows[i], "%s\n剩余 %g%%  已用 %g%%\n%s", name, (double)(100 - row->used), (double)row->used, text);
        } else lv_label_set_text(detail_rows[i], "暂无额度数据");
    }
    lv_label_set_text_fmt(detail_footer, "数据源 %s", snapshot.bucket[0] ? snapshot.bucket : "codex");
    lv_label_set_text_fmt(setting_text, "屏幕亮度 %d%%\n\n闲置 60 秒调暗 / 5 分钟息屏\n按键短按刷新 / 长按息屏唤醒\n\n提醒阈值 %d%% / %d%%\n\n音量和电源按钮位于底部\n完全关机后用实体电源键开机", brightness, snapshot.received ? snapshot.warning : 20, snapshot.received ? snapshot.critical : 10);
    // Small periodic position shifts reduce stationary pixel exposure.
    int shift = ((now_ms / 60000) % 3) - 1;
    lv_obj_set_pos(body, shift * 2, 0);
}

void quota_key_event(bool long_press)
{
    if (key_queue) xQueueSend(key_queue, &long_press, 0);
}

void quota_ui_start(void)
{
    settings_open = nvs_open("quota_ui", NVS_READWRITE, &settings) == ESP_OK;
    if (settings_open) {
        nvs_get_u8(settings, "selected", &selected);
        nvs_get_u8(settings, "brightness", &brightness);
        nvs_get_u8(settings, "volume", &saved_volume);
    }
    if (selected > 1) selected = 0;
    if (brightness < 10 || brightness > 100) brightness = 70;
    if (saved_volume > 100) saved_volume = 35;
    quota_hardware_init(saved_volume);
    key_queue = xQueueCreate(8, sizeof(bool));
    assert(key_queue);
    lv_display_t *display = bsp_display_start();
    if (!display) abort();
    bsp_display_lock(-1);
    screen = lv_screen_active();
    lv_obj_set_style_bg_color(screen, lv_color_hex(0x080c12), 0);
    lv_obj_remove_flag(screen, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(screen, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(screen, screen_event, LV_EVENT_PRESSED, NULL);
    lv_obj_add_event_cb(screen, screen_event, LV_EVENT_RELEASED, NULL);
    body = container(screen);
    for (int i = 0; i < 3; i++) pages[i] = container(body);
    title = label(body, 60, 24, 360, &lv_font_montserrat_20, 0xdce7f3);
    status_label = label(body, 40, 58, 400, &quota_font, 0xffb759);
    ring = lv_arc_create(pages[0]);
    lv_obj_set_pos(ring, 140, 105);
    lv_obj_set_size(ring, 200, 200);
    lv_arc_set_rotation(ring, 270);
    lv_arc_set_bg_angles(ring, 0, 360);
    lv_arc_set_range(ring, 0, 100);
    lv_obj_remove_style(ring, NULL, LV_PART_KNOB);
    lv_obj_remove_flag(ring, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_arc_width(ring, 12, LV_PART_MAIN);
    lv_obj_set_style_arc_width(ring, 12, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(ring, lv_color_hex(0x202b38), LV_PART_MAIN);
    main_name = label(pages[0], 130, 130, 220, &quota_font, 0x9aafc6);
    main_percent = label(pages[0], 130, 164, 220, &lv_font_montserrat_48, 0x4ce0b3);
    lv_label_set_text(label(pages[0], 170, 226, 140, &quota_font, 0x9aafc6), "剩余");
    main_countdown = label(pages[0], 100, 267, 280, &quota_font, 0xdce7f3);
    other_name = label(pages[0], 60, 322, 360, &quota_font, 0xdce7f3);
    other_bar = lv_bar_create(pages[0]);
    lv_obj_set_pos(other_bar, 105, 353);
    lv_obj_set_size(other_bar, 270, 6);
    lv_obj_set_style_bg_color(other_bar, lv_color_hex(0x202b38), LV_PART_MAIN);
    sync_label = label(pages[0], 40, 367, 400, &quota_font, 0x8295ac);
    detail_rows[0] = label(pages[1], 45, 120, 390, &quota_font, 0xdce7f3);
    detail_rows[1] = label(pages[1], 45, 245, 390, &quota_font, 0xdce7f3);
    detail_footer = label(pages[1], 45, 355, 390, &quota_font, 0x8295ac);
    setting_text = label(pages[2], 40, 107, 400, &quota_font, 0xdce7f3);
    hint = label(body, 35, 391, 410, &quota_font, 0x566a82);
    lv_obj_set_style_text_font(hint, &quota_font, 0);
    volume_down = control_button(body, 45, 417, 90, "音量 -");
    volume_label = label(body, 135, 426, 120, &quota_font, 0xdce7f3);
    volume_up = control_button(body, 255, 417, 90, "音量 +");
    power_button = control_button(body, 355, 417, 80, "电源");
    lv_obj_add_event_cb(volume_down, volume_event, LV_EVENT_CLICKED, NULL);
    lv_obj_add_event_cb(volume_up, volume_event, LV_EVENT_CLICKED, NULL);
    lv_obj_add_event_cb(power_button, power_event, LV_EVENT_CLICKED, NULL);
    show_page();
    last_action_ms = milliseconds();
    set_brightness(brightness);
    lv_timer_create(timer_callback, 500, NULL);
    bsp_display_unlock();
}
