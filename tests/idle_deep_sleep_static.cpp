#include "../platform/super_s3_216/main/modules/device_modes/idle_deep_sleep.hpp"
using namespace idle_deep_sleep;
static_assert(index(0)==0 && index(10)==1 && index(20)==2 && index(30)==3);
static_assert(index(60)==4 && index(120)==5 && index(240)==6);
static_assert(index(-1)==-1 && index(5)==-1 && index(999)==-1);
static_assert(!due(600001,0,0)); // Disabled, regardless of idle time.
static_assert(!due(599999,0,600) && due(600000,0,600));
static_assert(!due(1199999,0,1200) && due(1200000,0,1200));
static_assert(!due(7199999,0,7200) && due(7200000,0,7200));
static_assert(remaining(0,0,600)==600 && remaining(599999,0,600)==1);
static_assert(remaining(600000,0,600)==0 && remaining(123456,0,0)==0);
static_assert(due(5000,0xfffffff0U,5)); // Millisecond clock wrap.
static_assert(!due(5000,4999,5)); // Touch/audio activity restarts the interval.
static_assert(!due(5000,5001,5) && remaining(5000,5001,5)==5); // Concurrent touch.
