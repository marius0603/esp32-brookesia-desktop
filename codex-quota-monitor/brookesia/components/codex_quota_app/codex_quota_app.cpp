#include <algorithm>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <inttypes.h>
#include <memory>
#include "esp_brookesia.hpp"
#include "esp_lib_utils.h"
#include "esp_timer.h"
#include "codex_quota_app.hpp"
#include "codex_quota_feed.h"
#include "codex_quota_controls.h"
#include "quota_protocol.h"

LV_FONT_DECLARE(codex_quota_font);

namespace {
lv_obj_t *label(lv_obj_t *parent, int x, int y, int width, const char *text)
{
    auto *object = lv_label_create(parent);
    lv_obj_set_pos(object, x, y);
    lv_obj_set_width(object, width);
    lv_obj_set_style_text_font(object, &codex_quota_font, 0);
    lv_obj_set_style_text_color(object, lv_color_hex(0xdce7f3), 0);
    lv_obj_set_style_text_align(object, LV_TEXT_ALIGN_CENTER, 0);
    lv_label_set_text(object, text);
    return object;
}
lv_obj_t *panel(lv_obj_t *parent, int width, int height)
{
    auto *object = lv_obj_create(parent);
    lv_obj_remove_style_all(object);
    lv_obj_set_size(object, width, height);
    lv_obj_remove_flag(object, LV_OBJ_FLAG_SCROLLABLE | LV_OBJ_FLAG_CLICKABLE);
    return object;
}
lv_obj_t *button(lv_obj_t *parent, int x, int y, int width, const char *text)
{
    auto *object = lv_button_create(parent);
    lv_obj_set_pos(object, x, y);
    lv_obj_set_size(object, width, 38);
    auto *caption = lv_label_create(object);
    lv_obj_set_style_text_font(caption, &codex_quota_font, 0);
    lv_label_set_text(caption, text);
    lv_obj_center(caption);
    return object;
}
void enabled(lv_obj_t *object, bool value)
{
    if (value) lv_obj_remove_state(object, LV_STATE_DISABLED);
    else lv_obj_add_state(object, LV_STATE_DISABLED);
}
void window_name(char *out, size_t length, int minutes)
{
    if (minutes == 10080) std::snprintf(out, length, "每周额度");
    else if (minutes % 60 == 0) std::snprintf(out, length, "%d 小时额度", minutes / 60);
    else std::snprintf(out, length, "%d 分钟额度", minutes);
}
void countdown(char *out, size_t length, int64_t reset, int64_t now)
{
    if (!reset) { std::snprintf(out, length, "暂无重置时间"); return; }
    int64_t seconds = reset - now;
    if (seconds <= 0) { std::snprintf(out, length, "等待同步"); return; }
    int64_t days = seconds / 86400;
    int hours = (seconds % 86400) / 3600, minutes = (seconds % 3600) / 60, sec = seconds % 60;
    if (days) std::snprintf(out, length, "%" PRId64 "天 %02d:%02d:%02d", days, hours, minutes, sec);
    else std::snprintf(out, length, "%02d:%02d:%02d", hours, minutes, sec);
}
uint32_t color(float remaining, const codex_quota_snapshot_t &data, bool fresh)
{
    if (!fresh) return 0x718096;
    if (remaining <= data.critical) return 0xff6878;
    return remaining <= data.warning ? 0xffb759 : 0x4ce0b3;
}
const char *status_text(const char *status)
{
    if (!std::strcmp(status, "ok")) return "额度已同步";
    if (!std::strcmp(status, "stale")) return "数据已过期";
    if (!std::strcmp(status, "auth_required")) return "请在电脑端登录 Codex";
    if (!std::strcmp(status, "error")) return "采集失败  保留上次数据";
    return "等待电脑连接";
}
}

namespace esp_brookesia::apps {

CodexQuota::CodexQuota() : systems::phone::App("Codex", nullptr, true, true, true) {}

bool CodexQuota::run()
{
    const auto &area = getVisualArea();
    int width = lv_area_get_width(&area), height = lv_area_get_height(&area);
    if (width < 360 || height < 360) return false;
    root_ = panel(lv_screen_active(), width, height);
    lv_obj_set_style_bg_color(root_, lv_color_hex(0x080c12), 0);
    lv_obj_set_style_bg_opa(root_, LV_OPA_COVER, 0);
    label(root_, 96, 7, width - 152, "Codex 额度");
    auto *refresh = lv_button_create(root_);
    lv_obj_set_pos(refresh, width - 50, 3);
    lv_obj_set_size(refresh, 42, 36);
    auto *refresh_text = lv_label_create(refresh);
    lv_label_set_text(refresh_text, "R");
    lv_obj_center(refresh_text);
    lv_obj_add_event_cb(refresh, [](lv_event_t *) { codex_quota_request_refresh(); }, LV_EVENT_CLICKED, nullptr);
    status_ = label(root_, 12, 36, width - 24, "等待电脑连接");
    overview_ = panel(root_, width, height);
    lv_obj_move_foreground(status_);
    int diameter = std::min(220, std::min(width - 64, height - 220));
    int ring_y = 63;
    ring_ = lv_arc_create(overview_);
    lv_obj_set_pos(ring_, (width - diameter) / 2, ring_y);
    lv_obj_set_size(ring_, diameter, diameter);
    lv_arc_set_rotation(ring_, 270);
    lv_arc_set_bg_angles(ring_, 0, 360);
    lv_arc_set_range(ring_, 0, 100);
    lv_obj_remove_style(ring_, nullptr, LV_PART_KNOB);
    lv_obj_remove_flag(ring_, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_arc_width(ring_, 10, LV_PART_MAIN);
    lv_obj_set_style_arc_width(ring_, 10, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(ring_, lv_color_hex(0x202b38), LV_PART_MAIN);
    window_name_ = label(overview_, 40, ring_y + diameter / 6, width - 80, "暂无额度数据");
    percent_ = label(overview_, 40, ring_y + diameter * 2 / 5 - 8, width - 80, "--");
#if LV_FONT_MONTSERRAT_40
    lv_obj_set_style_text_font(percent_, &lv_font_montserrat_40, 0);
#endif
    lv_obj_add_flag(percent_, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(percent_, [](lv_event_t *event) {
        auto *app = static_cast<CodexQuota *>(lv_event_get_user_data(event));
        app->selected_ = 1 - app->selected_;
        app->refreshView();
    }, LV_EVENT_CLICKED, this);
    label(overview_, 50, ring_y + diameter * 3 / 5 + 8, width - 100, "剩余");
    countdown_ = label(overview_, 18, ring_y + diameter * 4 / 5, width - 36, "等待首次同步");
    secondary_ = label(overview_, 15, ring_y + diameter + 8, width - 30, "");
    secondary_bar_ = lv_bar_create(overview_);
    lv_obj_set_pos(secondary_bar_, 65, ring_y + diameter + 38);
    lv_obj_set_size(secondary_bar_, width - 130, 6);
    lv_obj_set_style_bg_color(secondary_bar_, lv_color_hex(0x202b38), LV_PART_MAIN);
    details_ = panel(root_, width, height - 160);
    lv_obj_set_y(details_, 67);
    detail_text_ = label(details_, 16, 8, width - 32, "暂无额度数据");
    lv_obj_add_flag(details_, LV_OBJ_FLAG_HIDDEN);
    footer_ = label(root_, 16, height - 87, width - 32, "等待首次同步");
    lv_obj_set_style_text_color(footer_, lv_color_hex(0x8295ac), 0);
    auto *details_button = button(root_, 10, 3, 76, "详情");
    lv_obj_add_event_cb(details_button, [](lv_event_t *event) {
        static_cast<CodexQuota *>(lv_event_get_user_data(event))->toggleDetails();
    }, LV_EVENT_CLICKED, this);
    int cell = (width - 56) / 4, control_y = height - 53;
    volume_down_ = button(root_, 16, control_y, cell, "音量 -");
    volume_text_ = label(root_, 24 + cell, control_y + 8, cell, "音量 --");
    volume_up_ = button(root_, 32 + cell * 2, control_y, cell, "音量 +");
    power_button_ = button(root_, 40 + cell * 3, control_y, cell, "电源");
    lv_obj_add_event_cb(volume_down_, [](lv_event_t *event) {
        static_cast<CodexQuota *>(lv_event_get_user_data(event))->adjustVolume(-5);
    }, LV_EVENT_CLICKED, this);
    lv_obj_add_event_cb(volume_up_, [](lv_event_t *event) {
        static_cast<CodexQuota *>(lv_event_get_user_data(event))->adjustVolume(5);
    }, LV_EVENT_CLICKED, this);
    lv_obj_add_event_cb(power_button_, [](lv_event_t *event) {
        static_cast<CodexQuota *>(lv_event_get_user_data(event))->showPowerDialog();
    }, LV_EVENT_CLICKED, this);
    power_dialog_ = nullptr;
    control_notice_until_ = 0;
    showing_details_ = false;
    timer_ = lv_timer_create(timerCallback, 1000, this);
    refreshView();
    return timer_ != nullptr;
}

void CodexQuota::adjustVolume(int delta)
{
    if (!codex_quota_adjust_volume(delta)) {
        lv_label_set_text(footer_, "音量调整失败，请重试");
        control_notice_until_ = esp_timer_get_time() / 1000 + 3000;
    }
    refreshView();
}

void CodexQuota::showPowerDialog()
{
    if (power_dialog_ || !codex_quota_can_power_off()) return;
    int width = lv_obj_get_width(root_), height = lv_obj_get_height(root_);
    power_dialog_ = panel(root_, width, height);
    lv_obj_add_flag(power_dialog_, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_bg_color(power_dialog_, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(power_dialog_, LV_OPA_60, 0);
    auto *dialog = panel(power_dialog_, width - 48, 228);
    lv_obj_add_flag(dialog, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_center(dialog);
    lv_obj_set_style_bg_color(dialog, lv_color_hex(0x172231), 0);
    lv_obj_set_style_bg_opa(dialog, LV_OPA_COVER, 0);
    lv_obj_set_style_radius(dialog, 16, 0);
    power_message_ = label(dialog, 16, 22, width - 80, "确认关机？\n关机后请用实体电源键开机");
    auto *cancel = button(dialog, 20, 160, (width - 108) / 2, "取消");
    power_confirm_ = button(dialog, (width - 48) / 2 + 10, 160, (width - 108) / 2, "关机");
    lv_obj_set_style_bg_color(power_confirm_, lv_color_hex(0xb53d50), 0);
    lv_obj_add_event_cb(cancel, [](lv_event_t *event) {
        static_cast<CodexQuota *>(lv_event_get_user_data(event))->dismissPowerDialog();
    }, LV_EVENT_CLICKED, this);
    lv_obj_add_event_cb(power_confirm_, [](lv_event_t *event) {
        static_cast<CodexQuota *>(lv_event_get_user_data(event))->confirmPowerOff();
    }, LV_EVENT_CLICKED, this);
}

void CodexQuota::dismissPowerDialog()
{
    if (power_dialog_) lv_obj_delete(power_dialog_);
    power_dialog_ = power_message_ = power_confirm_ = nullptr;
}

void CodexQuota::confirmPowerOff()
{
    if (!power_dialog_) return;
    enabled(power_confirm_, false);
    if (codex_quota_power_off()) {
        lv_label_set_text(power_message_, "已提交关机请求\n再次开机请用实体电源键");
    } else {
        lv_label_set_text(power_message_, "关机失败，请重试");
        enabled(power_confirm_, true);
    }
}

void CodexQuota::toggleDetails()
{
    showing_details_ = !showing_details_;
    if (showing_details_) {
        lv_obj_add_flag(overview_, LV_OBJ_FLAG_HIDDEN);
        lv_obj_remove_flag(details_, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_remove_flag(overview_, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(details_, LV_OBJ_FLAG_HIDDEN);
    }
}

void CodexQuota::refreshView()
{
    if (!root_) return;
    codex_quota_snapshot_t data;
    codex_quota_copy_snapshot(&data);
    int64_t now_ms = esp_timer_get_time() / 1000;
    int volume = 0;
    bool has_volume = codex_quota_get_volume(&volume);
    if (has_volume) lv_label_set_text_fmt(volume_text_, "音量 %d%%", volume);
    else lv_label_set_text(volume_text_, "音量 --");
    enabled(volume_down_, has_volume && volume > 0);
    enabled(volume_up_, has_volume && volume < 100);
    enabled(power_button_, codex_quota_can_power_off());
    int64_t now = codex_quota_estimated_now(&data, now_ms);
    const char *status = codex_quota_status(&data, now_ms);
    bool fresh = !std::strcmp(status, "ok");
    lv_label_set_text(status_, status_text(status));
    lv_obj_set_style_text_color(status_, lv_color_hex(fresh ? 0x4ce0b3 : 0xffb759), 0);
    char name[64], reset[80], details[384] = "";
    if (data.count) {
        const auto &window = data.windows[selected_ % data.count];
        window_name(name, sizeof(name), window.minutes);
        lv_label_set_text(window_name_, name);
        lv_label_set_text_fmt(percent_, "%g%%", static_cast<double>(100 - window.used));
        lv_obj_set_style_text_color(percent_, lv_color_hex(color(100 - window.used, data, fresh)), 0);
        lv_obj_set_style_arc_color(ring_, lv_color_hex(color(100 - window.used, data, fresh)), LV_PART_INDICATOR);
        lv_arc_set_value(ring_, static_cast<int>(100 - window.used));
        countdown(reset, sizeof(reset), window.reset_at, now);
        lv_label_set_text(countdown_, reset);
    } else {
        lv_label_set_text(percent_, "--");
        lv_label_set_text(window_name_, "暂无额度数据");
        lv_label_set_text(countdown_, "等待首次同步");
        lv_arc_set_value(ring_, 0);
    }
    if (data.count > 1) {
        const auto &other = data.windows[(selected_ + 1) % data.count];
        window_name(name, sizeof(name), other.minutes);
        lv_label_set_text_fmt(secondary_, "%s  剩余 %g%%", name, static_cast<double>(100 - other.used));
        lv_bar_set_value(secondary_bar_, static_cast<int>(100 - other.used), LV_ANIM_OFF);
        lv_obj_set_style_bg_color(secondary_bar_, lv_color_hex(color(100 - other.used, data, fresh)), LV_PART_INDICATOR);
        lv_obj_remove_flag(secondary_bar_, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_label_set_text(secondary_, "");
        lv_obj_add_flag(secondary_bar_, LV_OBJ_FLAG_HIDDEN);
    }
    for (int i = 0; i < data.count; ++i) {
        const auto &window = data.windows[i];
        window_name(name, sizeof(name), window.minutes);
        countdown(reset, sizeof(reset), window.reset_at, now);
        size_t used = std::strlen(details);
        std::snprintf(details + used, sizeof(details) - used, "%s\n剩余 %g%%  已用 %g%%\n重置 %s\n\n", name,
                      static_cast<double>(100 - window.used), static_cast<double>(window.used), reset);
    }
    lv_label_set_text(detail_text_, data.count ? details : "暂无额度数据");
    if (now_ms < control_notice_until_) return;
    if (data.has_sample) {
        time_t stamp = static_cast<time_t>(data.sampled_at + 8 * 3600);
        struct tm local;
        gmtime_r(&stamp, &local);
        lv_label_set_text_fmt(footer_, "同步 %02d:%02d:%02d", local.tm_hour, local.tm_min, local.tm_sec);
    } else lv_label_set_text(footer_, "等待首次同步");
}

void CodexQuota::timerCallback(lv_timer_t *timer)
{
    static_cast<CodexQuota *>(lv_timer_get_user_data(timer))->refreshView();
}
bool CodexQuota::back()
{
    if (power_dialog_) { dismissPowerDialog(); return true; }
    return notifyCoreClosed();
}
bool CodexQuota::pause() { if (timer_) lv_timer_pause(timer_); return true; }
bool CodexQuota::resume() { if (timer_) lv_timer_resume(timer_); refreshView(); return true; }
bool CodexQuota::close()
{
    // Brookesia owns and recycles the screen and timer recorded during run().
    timer_ = nullptr;
    root_ = nullptr;
    power_dialog_ = power_message_ = power_confirm_ = nullptr;
    return true;
}

ESP_UTILS_REGISTER_PLUGIN_WITH_CONSTRUCTOR(systems::base::App, CodexQuota, "Codex", []() {
    return std::make_shared<CodexQuota>();
})
}
