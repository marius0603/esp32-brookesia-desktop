#pragma once
#include <memory>
#include "brookesia/service_manager/service/base.hpp"
std::shared_ptr<esp_brookesia::service::ServiceBase> make_learning_audio_service();
