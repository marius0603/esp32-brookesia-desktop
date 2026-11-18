#pragma once
#include <algorithm>
#include <string_view>
namespace child_policy {
constexpr int volume_limit_max=100;
constexpr unsigned audiobook = 1, songs = 32, radio = 64;
constexpr unsigned default_mask = audiobook | songs | 2 | 4;
constexpr bool valid_mask(unsigned mask) {return mask<=127;}
constexpr unsigned migrate_mask(unsigned mask) {
    return mask | ((mask & audiobook) ? songs | radio : 0);
}
constexpr unsigned app_bit(std::string_view id) {
    if(id=="local.audiobook")return audiobook;
    if(id=="local.nurserysongs")return songs;
    if(id=="local.radio")return radio;
    if(id=="local.weather")return 2;
    if(id=="local.flipclock")return 4;
    if(id=="local.voiceassistant")return 8;
    if(id=="local.lightlearning" || id=="local.gravitymaze")return 16;
    return 0;
}
constexpr bool allowed(bool ready,bool enabled,unsigned mask,bool resting,unsigned permission) {
    return ready && (!enabled || ((mask&permission)!=0 && !resting));
}
constexpr bool station_allowed(bool radio_allowed,bool child,unsigned station_flag,unsigned whitelist) {
    return radio_allowed && (!child || (station_flag & whitelist) != 0);
}
// FAT matches directory names case-insensitively and ignores trailing spaces and dots.
constexpr bool is_song_path(std::string_view path) {
    constexpr std::string_view root="/sdcard/audiobooks/";
    if(!path.starts_with(root))return false;
    path.remove_prefix(root.size());
    constexpr std::string_view name="songs";
    for(;;) {
        const auto separator=path.find('/');
        if(separator==std::string_view::npos)return false;
        auto directory=path.substr(0,separator);
        path.remove_prefix(separator+1);
        if(directory.empty() || directory==".")continue;
        while(!directory.empty() && (directory.back()==' ' || directory.back()=='.'))directory.remove_suffix(1);
        if(directory.size()!=name.size())return false;
        for(size_t i=0;i<name.size();++i)
            if(directory[i]!=name[i] && directory[i]!=name[i]-'a'+'A')return false;
        return true;
    }
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
