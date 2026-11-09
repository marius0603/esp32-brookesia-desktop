#include "../platform/super_s3_216/main/modules/device_modes/resource_math.hpp"
using namespace resource_math;
static_assert(heap_usage(1000,1000)==0 && heap_usage(1000,0)==10000);
static_assert(heap_usage(8000000,2000000)==7500 && heap_usage(0,0)==-1);
static_assert(heap_usage(100,110)==0 && rounded_percent(-1)==-1 && rounded_percent(7549)==75 && rounded_percent(7550)==76);
constexpr bool cpu_cases() {
    CpuWindow<uint32_t,2> w;
    if(w.sample(1000000,{100,200}).valid)return false;
    auto idle=w.sample(2000000,{1000100,1000200});
    if(!idle.valid || idle.total!=0)return false;
    auto half=w.sample(3000000,{1000100,2000200});
    if(half.total!=5000 || half.cores[0]!=10000 || half.cores[1]!=0)return false;
    if(w.sample(4000000,{1000100,2000200}).total!=10000)return false;
    if(w.sample(4000000,{1000100,2000200}).valid)return false;
    return true;
}
static_assert(cpu_cases());
constexpr bool wrap_case() {
    CpuWindow<uint32_t,2> w;w.sample(1000,{0xfffffff0U,0xfffffff0U});
    auto s=w.sample(1032,{0x10U,0xfffffff0U});
    return s.valid && s.total==5000 && s.cores[0]==0 && s.cores[1]==10000;
}
static_assert(wrap_case());
