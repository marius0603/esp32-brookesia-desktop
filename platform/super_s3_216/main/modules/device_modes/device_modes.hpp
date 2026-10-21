#pragma once
#include <memory>
#include "brookesia/service_manager/service/base.hpp"
std::shared_ptr<esp_brookesia::service::ServiceBase> make_device_modes_service();
// Runs on the existing orientation worker; no additional task stack.
void device_modes_poll();
extern "C" bool brookesia_board_screen_asleep();
extern "C" bool brookesia_board_do_not_disturb();
extern "C" bool brookesia_board_auto_sleep_enabled();
extern "C" void brookesia_board_set_auto_sleep(bool enabled);
extern "C" void brookesia_board_set_do_not_disturb(bool enabled);

extern "C" bool brookesia_board_manual_dnd();
extern "C" bool brookesia_board_quiet_enabled();
extern "C" int brookesia_board_quiet_start();
extern "C" int brookesia_board_quiet_end();
extern "C" int brookesia_board_local_minute();
extern "C" void brookesia_board_set_quiet_hours(bool,int,int);
