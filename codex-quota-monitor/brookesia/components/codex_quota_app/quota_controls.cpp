#include "codex_quota_controls.h"
#include <algorithm>

static codex_quota_device_controls_t device;

extern "C" void codex_quota_set_device_controls(const codex_quota_device_controls_t *controls)
{
    device = controls ? *controls : codex_quota_device_controls_t{};
}
extern "C" bool codex_quota_get_volume(int *percent)
{
    if (!percent || !device.get_volume || !device.set_volume) return false;
    int actual = -1;
    if (!device.get_volume(device.context, &actual) || actual < 0 || actual > 100) return false;
    *percent = actual;
    return true;
}
extern "C" bool codex_quota_adjust_volume(int delta)
{
    int current;
    if (!codex_quota_get_volume(&current)) return false;
    int target = static_cast<int>(std::clamp(static_cast<long long>(current) + delta, 0LL, 100LL));
    return target == current || device.set_volume(device.context, target);
}
extern "C" bool codex_quota_can_power_off(void) { return device.power_off != nullptr; }
extern "C" bool codex_quota_power_off(void)
{
    return device.power_off && device.power_off(device.context);
}
