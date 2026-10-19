#include "codex_quota_feed.h"
#include "quota_protocol.h"
#include "freertos/FreeRTOS.h"
#include "esp_timer.h"
static portMUX_TYPE state_lock = portMUX_INITIALIZER_UNLOCKED;
static codex_quota_snapshot_t state;
static codex_quota_refresh_callback_t refresh_callback;
static void *refresh_context;
static int64_t last_refresh_ms = -15000;
extern "C" bool codex_quota_feed_json(const char *json, size_t length)
{
    codex_quota_snapshot_t next;
    if (!codex_quota_parse(json, length, esp_timer_get_time() / 1000, &next)) return false;
    portENTER_CRITICAL(&state_lock);
    state = next;
    portEXIT_CRITICAL(&state_lock);
    return true;
}
extern "C" void codex_quota_copy_snapshot(codex_quota_snapshot_t *out)
{
    if (!out) return;
    portENTER_CRITICAL(&state_lock);
    *out = state;
    portEXIT_CRITICAL(&state_lock);
}
extern "C" const char *codex_quota_protocol_hello(void)
{
    return "{\"type\":\"hello\",\"device\":\"codex-quota-monitor\",\"v\":1}\n";
}
extern "C" void codex_quota_set_refresh_callback(codex_quota_refresh_callback_t callback, void *context)
{
    portENTER_CRITICAL(&state_lock);
    refresh_callback = callback;
    refresh_context = context;
    portEXIT_CRITICAL(&state_lock);
}
extern "C" bool codex_quota_request_refresh(void)
{
    int64_t now = esp_timer_get_time() / 1000;
    portENTER_CRITICAL(&state_lock);
    auto callback = refresh_callback;
    void *context = refresh_context;
    bool accepted = callback && now - last_refresh_ms >= 15000;
    if (accepted) last_refresh_ms = now;
    portEXIT_CRITICAL(&state_lock);
    if (accepted) callback(context);
    return accepted;
}
