#include "launcher_swipe.hpp"

using esp_brookesia::system::super::LauncherSwipe;

constexpr int page_width = 372;

constexpr bool slow_drag_uses_distance()
{
    LauncherSwipe swipe;
    swipe.begin();
    for (uint32_t time_ms = 20; time_ms <= 500; time_ms += 20) {
        swipe.update(-static_cast<float>(time_ms) * 0.2F, 0, time_ms);
    }
    swipe.update(-100, 0, 520);
    swipe.update(-100, 0, 540);
    return swipe.dragging() && swipe.page_delta(-100, page_width, 600) == 1;
}

constexpr bool same_distance_needs_a_flick()
{
    LauncherSwipe swipe;
    swipe.begin();
    for (uint32_t time_ms = 20; time_ms <= 240; time_ms += 20) {
        swipe.update(static_cast<float>(time_ms) * 0.1F, 0, time_ms);
    }
    if (swipe.page_delta(24, page_width, 300) != 0) {
        return false;
    }

    swipe.begin();
    swipe.update(24, 0, 20);
    return swipe.dragging() && swipe.page_delta(24, page_width, 80) == -1;
}

constexpr bool recent_reversal_cancels_a_page_turn()
{
    LauncherSwipe swipe;
    swipe.begin();
    swipe.update(-40, 0, 20);
    swipe.update(-95, 0, 40);
    swipe.update(-110, 0, 60);
    if (swipe.page_delta(-110, page_width, 120) != 1) {
        return false;
    }

    swipe.update(-96, 0, 80);
    return swipe.page_delta(-96, page_width, 140) == 0;
}

constexpr bool held_or_stale_flick_does_not_turn()
{
    LauncherSwipe swipe;
    swipe.begin();
    swipe.update(-30, 0, 20);
    if (swipe.page_delta(-30, page_width, 80) != 1 ||
            swipe.page_delta(-30, page_width, 140) != 0) {
        return false;
    }

    for (uint32_t time_ms = 40; time_ms <= 100; time_ms += 20) {
        swipe.update(-30, 0, time_ms);
    }
    return swipe.page_delta(-30, page_width, 160) == 0;
}

constexpr bool tap_vertical_and_consecutive_swipes()
{
    LauncherSwipe swipe;
    swipe.begin();
    swipe.update(3, 2, 20);
    if (swipe.dragging() || swipe.page_delta(3, page_width, 80) != 0) {
        return false;
    }

    swipe.begin();
    swipe.update(20, 80, 20);
    if (swipe.dragging()) {
        return false;
    }

    swipe.begin();
    swipe.update(-25, 0, 20);
    if (!swipe.dragging() || swipe.page_delta(-25, page_width, 80) != 1) {
        return false;
    }

    swipe.begin();
    if (swipe.dragging()) {
        return false;
    }
    swipe.update(25, 0, 20);
    return swipe.dragging() && swipe.page_delta(25, page_width, 80) == -1;
}

static_assert(slow_drag_uses_distance());
static_assert(same_distance_needs_a_flick());
static_assert(recent_reversal_cancels_a_page_turn());
static_assert(held_or_stale_flick_does_not_turn());
static_assert(tap_vertical_and_consecutive_swipes());
