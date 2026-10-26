#include <cassert>
#include <cstdint>
#include "../platform/super_s3_216/main/modules/device_modes/screen_lock.hpp"

int main() {
    screen_lock::DoublePress key;
    key.press(100); assert(!key.release(160));
    key.press(300); assert(key.release(350));
    assert(key.pending()==0);
    // A lone press expires; the next press starts a fresh pair.
    key.press(1000); assert(!key.release(1050));
    key.expire(1800); assert(key.pending()==0);
    key.press(1900); assert(!key.release(1950));
    key.reset();
    // Holding, including repeated press notifications, cannot unlock.
    key.press(2000); key.press(2700); key.press(3050);
    assert(!key.release(3200)); assert(key.pending()==0);
    // A short press followed by a long hold must not qualify.
    key.press(4000); assert(!key.release(4050));
    key.press(4200); assert(!key.release(4600)); assert(key.pending()==0);
    // A spurious release without a preceding press is ignored.
    assert(!key.release(4700));
    key.press(4800); assert(!key.release(4850));
    key.press(5400); assert(key.release(5500));
    // Another key cancels the pair; the following plus press is only the first.
    key.press(6000); assert(!key.release(6050)); key.reset();
    key.press(6200); assert(!key.release(6250)); key.reset();
    // Millisecond rollover keeps the same interval semantics.
    key.press(UINT32_MAX-100); assert(!key.release(UINT32_MAX-50));
    key.press(80); assert(key.release(120));
    key.reset(); assert(key.pending()==0);
}
