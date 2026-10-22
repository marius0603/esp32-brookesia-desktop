#pragma once
#include <array>
#include <cstdint>
namespace idle_deep_sleep {
inline constexpr std::array<int,7> minutes{0,10,20,30,60,120,240};
constexpr int index(int value) {
    for(unsigned i=0;i<minutes.size();++i)if(minutes[i]==value)return int(i);
    return -1;
}
constexpr bool due(uint32_t now,uint32_t activity,uint32_t seconds) {
    const uint32_t elapsed=now-activity;
    // Another core can publish a touch after the caller samples "now".
    // Treat that slightly newer timestamp as zero idle, not a 49-day wrap.
    return seconds!=0 && elapsed<0x80000000U && elapsed>=seconds*1000U;
}
constexpr uint32_t remaining(uint32_t now,uint32_t activity,uint32_t seconds) {
    const uint32_t delta=now-activity;
    const uint32_t elapsed=delta<0x80000000U?delta:0U;
    if(!seconds || elapsed>=seconds*1000U)return 0;
    return (seconds*1000U-elapsed+999U)/1000U;
}
}
