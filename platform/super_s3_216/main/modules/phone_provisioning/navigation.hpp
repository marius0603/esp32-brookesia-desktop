#pragma once
#include "brookesia/service_manager/service/base.hpp"
namespace esp_brookesia::system::super {class System;}
namespace phone_remote {
void attach_system(esp_brookesia::system::super::System *system);
esp_brookesia::service::FunctionResult open_app(int id);
}
