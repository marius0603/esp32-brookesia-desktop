#pragma once
#include <string_view>
namespace phone_provisioning {
constexpr unsigned WINDOW_SECONDS=300, CONNECT_SECONDS=35;
constexpr bool valid_credentials(std::string_view ssid,std::string_view password) {
    return !ssid.empty() && ssid.size()<=32 && ssid.find('\0')==std::string_view::npos &&
        (password.empty() || (password.size()>=8 && password.size()<=63)) &&
        password.find('\0')==std::string_view::npos;
}
constexpr bool expired(long long now,long long started,unsigned seconds) {
    return now>=started && now-started>=static_cast<long long>(seconds)*1000000;
}
}
