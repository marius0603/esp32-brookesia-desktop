#pragma once
#include <memory>
#include "brookesia/service_manager/service/base.hpp"
std::shared_ptr<esp_brookesia::service::ServiceBase> make_phone_provisioning_service();
extern "C" bool brookesia_board_phone_provisioning_start();
extern "C" void brookesia_board_phone_provisioning_stop();
extern "C" bool brookesia_board_phone_provisioning_active();
extern "C" const char *brookesia_board_phone_provisioning_text();
