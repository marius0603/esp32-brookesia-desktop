#pragma once
#include <algorithm>
#include <string_view>
namespace child_policy {
constexpr int volume_limit_max=100;
constexpr bool valid_mask(unsigned mask) {return mask<=31;}
constexpr unsigned app_bit(std::string_view id) {
    if(id=="local.audiobook" || id=="local.nurserysongs" || id=="local.radio")return 1;
    if(id=="local.weather")return 2;
    if(id=="local.flipclock")return 4;
    if(id=="local.voiceassistant")return 8;
    if(id=="local.lightlearning" || id=="local.gravitymaze")return 16;
    return 0;
}
constexpr bool audio_allowed(bool ready,bool enabled,unsigned mask,bool resting) {
    return ready && (!enabled || ((mask&1)!=0 && !resting));
}
constexpr bool administrative(std::string_view id) {
    return id=="brookesia.system.super.shell" || id=="local.childmode";
}
constexpr bool visible(bool enabled,unsigned mask,std::string_view id) {
    return !enabled || administrative(id) || (app_bit(id)&mask)!=0;
}
constexpr bool night(int hour,int start,int end) {
    if(start==end)return false;
    return start<end ? hour>=start && hour<end : hour>=start || hour<end;
}
constexpr unsigned reserve(unsigned seconds) {return ((seconds+59)/60)*60;}
}
