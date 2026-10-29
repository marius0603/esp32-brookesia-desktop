#include "../platform/super_s3_216/main/modules/phone_provisioning/rules.hpp"
using namespace phone_provisioning;
using namespace std::literals;
static_assert(valid_credentials("home","12345678"));
static_assert(valid_credentials("open-network",""));
static_assert(!valid_credentials("","12345678"));
static_assert(!valid_credentials("home","short"));
static_assert(valid_credentials("12345678901234567890123456789012","12345678"));
static_assert(!valid_credentials("123456789012345678901234567890123","12345678"));
static_assert(!valid_credentials("bad\0name"sv,"12345678"));
static_assert(!valid_credentials("home","1234\0abcd"sv));
static_assert(!expired(299999999,0,WINDOW_SECONDS));
static_assert(expired(300000000,0,WINDOW_SECONDS));
static_assert(!expired(35000000,1,CONNECT_SECONDS));
static_assert(expired(35000001,1,CONNECT_SECONDS));
static_assert(!expired(0,1000,WINDOW_SECONDS));
