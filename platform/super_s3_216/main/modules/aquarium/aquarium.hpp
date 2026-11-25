#pragma once

#include "boost/json/object.hpp"

namespace aquarium {
bool start(bool night);
bool stop();
bool light(bool night);
const char *tap(int x, int y);
boost::json::object profile();
}
