#pragma once
#include <memory>
#include "brookesia/service_manager/service/base.hpp"
std::shared_ptr<esp_brookesia::service::ServiceBase> make_offline_voice_service();
bool offline_voice_prepare_online();
bool offline_voice_quiesce();
extern "C" bool brookesia_board_offline_voice_enabled();
extern "C" void brookesia_board_set_offline_voice(bool enabled);
