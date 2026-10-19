#pragma once
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Register before launching the app, from the host's GUI task or under its GUI lock.
 * Callbacks run on the GUI task and must return promptly. The host owns all drivers.
 * Volume is the real system output volume, expressed as 0..100 percent.
 * power_off returns true when the host accepts a shutdown request; it must flush
 * its own settings and stop audio before powering down. No driver is initialized here.
 */
typedef struct {
    void *context;
    bool (*get_volume)(void *context, int *percent);
    bool (*set_volume)(void *context, int percent);
    bool (*power_off)(void *context);
} codex_quota_device_controls_t;
void codex_quota_set_device_controls(const codex_quota_device_controls_t *controls);
bool codex_quota_get_volume(int *percent);
bool codex_quota_adjust_volume(int delta);
bool codex_quota_can_power_off(void);
bool codex_quota_power_off(void);
#ifdef __cplusplus
}
#endif
