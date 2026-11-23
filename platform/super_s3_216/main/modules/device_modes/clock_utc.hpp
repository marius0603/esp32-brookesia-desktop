#pragma once

namespace board_clock {
void initialize();
void poll();
bool restored_from_rtc();
bool rtc_current();
}
