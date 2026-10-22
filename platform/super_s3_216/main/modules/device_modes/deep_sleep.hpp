#pragma once
#include "boost/json/object.hpp"
void board_deep_sleep_boot();
boost::json::object board_deep_sleep_state();
extern "C" int brookesia_board_request_deep_sleep(unsigned test_wake_seconds);
extern "C" bool brookesia_board_deep_sleep_pending();
