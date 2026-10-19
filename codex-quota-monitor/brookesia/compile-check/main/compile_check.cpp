/* Link-check fixture only. It does not initialize or replace the factory desktop. */
#include "codex_quota_app.hpp"
#include "codex_quota_feed.h"
#include "codex_quota_controls.h"
extern "C" void app_main(void)
{
    (void)codex_quota_protocol_hello();
    (void)codex_quota_feed_json(nullptr, 0);
    codex_quota_set_refresh_callback(nullptr, nullptr);
    (void)codex_quota_request_refresh();
    codex_quota_set_device_controls(nullptr);
    int volume;
    (void)codex_quota_get_volume(&volume);
    (void)codex_quota_adjust_volume(5);
    (void)codex_quota_can_power_off();
    (void)codex_quota_power_off();
}
