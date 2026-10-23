#pragma once
#include <memory>
#include "brookesia/service_manager/service/base.hpp"
std::shared_ptr<esp_brookesia::service::ServiceBase> make_audiobook_service();

// Driven by the existing internal-stack board poll, independent of JS visibility.
void audiobook_sleep_poll();
