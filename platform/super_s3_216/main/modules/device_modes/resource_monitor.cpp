#include "resource_monitor.hpp"
#include "resource_math.hpp"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace resource_monitor {
namespace {
portMUX_TYPE mutex=portMUX_INITIALIZER_UNLOCKED;
Snapshot cached;
using Counter=configRUN_TIME_COUNTER_TYPE;
resource_math::CpuWindow<Counter,portNUM_PROCESSORS> cpu;
int64_t last=-1000000;
}
void poll() {
    const auto now=esp_timer_get_time();
    if(now-last<1000000)return;
    last=now;
    std::array<Counter,portNUM_PROCESSORS> idle{};
    for(unsigned i=0;i<portNUM_PROCESSORS;++i)idle[i]=ulTaskGetIdleRunTimeCounterForCore(i);
    const auto usage=cpu.sample(uint64_t(now),idle);
    Snapshot next;next.sampled_us=now;next.cores=portNUM_PROCESSORS;
    next.cpu_basis_points=usage.valid?usage.total:-1;
    for(unsigned i=0;i<portNUM_PROCESSORS && i<next.core_basis_points.size();++i)
        next.core_basis_points[i]=usage.valid?usage.cores[i]:-1;
    // Count each byte-addressable heap once, including internal DRAM and PSRAM.
    next.ram_total=heap_caps_get_total_size(MALLOC_CAP_8BIT);
    next.ram_free=heap_caps_get_free_size(MALLOC_CAP_8BIT);
    next.ram_basis_points=resource_math::heap_usage(next.ram_total,next.ram_free);
    next.internal_total=heap_caps_get_total_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    next.internal_free=heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT);
    next.psram_total=heap_caps_get_total_size(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    next.psram_free=heap_caps_get_free_size(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    portENTER_CRITICAL(&mutex);next.samples=cached.samples+1;cached=next;portEXIT_CRITICAL(&mutex);
}
Snapshot snapshot() {
    portENTER_CRITICAL(&mutex);const auto value=cached;portEXIT_CRITICAL(&mutex);return value;
}
}
