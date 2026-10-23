#pragma once
#include <algorithm>
#include <cstdint>
namespace story_sleep {
constexpr bool valid(int minutes){return minutes==0 || minutes==15 || minutes==30 || minutes==45;}
constexpr uint64_t fade_ms=120000;
constexpr uint32_t remaining(uint64_t now,uint64_t deadline){return deadline>now?uint32_t((deadline-now+999)/1000):0;}
constexpr int gain(uint64_t now,uint64_t deadline,uint64_t fade=fade_ms){
    return deadline<=now?0:int(std::min<uint64_t>(1000,(deadline-now)*1000/fade));
}
constexpr int dim(int gain){return 100+gain*900/1000;}
} // namespace story_sleep
