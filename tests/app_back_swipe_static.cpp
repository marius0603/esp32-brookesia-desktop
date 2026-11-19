#include "app_back_swipe.hpp"

using esp_brookesia::system::super::AppBackSwipe;

constexpr int exit_distance = 96;

constexpr bool reserves_only_the_bottom_edge()
{
    AppBackSwipe swipe;
    swipe.begin(false);
    if (swipe.update(0, 140, 20) || swipe.should_return(140, exit_distance, 80)) {
        return false;
    }
    swipe.begin(true);
    if (swipe.update(7, 4, 20) || swipe.update(40, 12, 40)) {
        return false;
    }
    return !swipe.update(40, 120, 60) && !swipe.should_return(120, exit_distance, 120);
}

constexpr bool commits_only_after_a_qualified_release()
{
    AppBackSwipe swipe;
    swipe.begin(true);
    for (uint32_t time_ms = 20; time_ms <= 500; time_ms += 20) {
        swipe.update(3, static_cast<int>(time_ms) / 5, time_ms);
    }
    return swipe.should_return(100, exit_distance, 560);
}

constexpr bool short_flick_and_pause_differ()
{
    AppBackSwipe swipe;
    swipe.begin(true);
    if (!swipe.update(2, 30, 20) || !swipe.should_return(30, exit_distance, 80) ||
            swipe.should_return(30, exit_distance, 141)) {
        return false;
    }
    for (uint32_t time_ms = 40; time_ms <= 100; time_ms += 20) {
        swipe.update(2, 30, time_ms);
    }
    return !swipe.should_return(30, exit_distance, 160);
}

constexpr bool pull_back_cancels_even_beyond_the_distance_threshold()
{
    AppBackSwipe swipe;
    swipe.begin(true);
    swipe.update(0, 120, 20);
    if (!swipe.should_return(120, exit_distance, 80)) {
        return false;
    }
    swipe.update(0, 100, 40);
    return !swipe.should_return(100, exit_distance, 100);
}

constexpr bool ignores_taps_and_resets_between_gestures()
{
    AppBackSwipe swipe;
    swipe.begin(true);
    if (swipe.update(1, 3, 20) || swipe.should_return(3, exit_distance, 80)) {
        return false;
    }
    swipe.begin(true);
    if (!swipe.update(1, 30, 20) || !swipe.should_return(30, exit_distance, 80)) {
        return false;
    }
    swipe.begin(true);
    return !swipe.update(1, 3, 20) && !swipe.should_return(3, exit_distance, 80);
}

static_assert(AppBackSwipe::edge_height(480) == 24);
static_assert(reserves_only_the_bottom_edge());
static_assert(commits_only_after_a_qualified_release());
static_assert(short_flick_and_pause_differ());
static_assert(pull_back_cancels_even_beyond_the_distance_threshold());
static_assert(ignores_taps_and_resets_between_gestures());
