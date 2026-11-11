#pragma once
#include "brookesia/service_manager/service/manager.hpp"
namespace phone_navigation {
boost::json::object snapshot();
bool usable();
esp_brookesia::service::FunctionResult receive(const boost::json::object &, bool allow_start);
void disconnect();
}
