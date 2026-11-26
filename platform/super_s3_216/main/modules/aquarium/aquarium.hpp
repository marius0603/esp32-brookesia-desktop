#pragma once

#include "boost/json/object.hpp"

namespace aquarium {
inline constexpr int feed_rssi_dbm = -25;
enum class FeedResult { Accepted, NotOpen, Cooldown };
bool start(bool night, int stock = -1);
bool choose_stock(unsigned stock);
bool stop();
bool light(bool night);
const char *tap(int x, int y);
FeedResult feed();
boost::json::object profile();
}
