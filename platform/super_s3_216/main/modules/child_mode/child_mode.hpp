#pragma once
#include <memory>
#include "brookesia/service_manager/service/base.hpp"
namespace esp_brookesia::system::core { class System; }
std::shared_ptr<esp_brookesia::service::ServiceBase> make_child_mode_service();
void child_mode_attach_system(esp_brookesia::system::core::System *system);
bool child_mode_voice_allowed();
bool child_mode_audiobook_allowed();
bool child_mode_learning_allowed();
