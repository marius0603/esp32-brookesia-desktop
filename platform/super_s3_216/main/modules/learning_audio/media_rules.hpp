#pragma once
#include <string_view>
namespace learning_media {
constexpr unsigned sample_rate=16000,max_record_seconds=8;
constexpr bool allowed_path(std::string_view path) {
    constexpr std::string_view root="/sdcard/learning/packs/";
    if(!path.starts_with(root)||!path.ends_with(".wav")||path.size()>240)return false;
    auto tail=path.substr(root.size());
    if(tail.empty()||tail.front()=='/')return false;
    while(!tail.empty()){
        const auto slash=tail.find('/');const auto part=tail.substr(0,slash);
        if(part.empty()||part=="."||part=="..")return false;
        for(char c:part)if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='-'||c=='_'||c=='.'))return false;
        if(slash==std::string_view::npos)break;
        tail.remove_prefix(slash+1);
    }
    return true;
}
}
