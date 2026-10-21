// Compile-only regression checks: uses the firmware header without ESP-IDF.
#include "../platform/super_s3_216/main/modules/auto_rotation/orientation.hpp"
using namespace board_orientation;
static_assert(classify(0,1,0)==0 && classify(0,-1,0)==180);
static_assert(classify(1,0,0)==270 && classify(-1,0,0)==90);
static_assert(classify(0,0,1)==-1 && classify(0,0,-1)==-1);
static_assert(classify(.71F,.71F,0)==-1); // diagonal
static_assert(classify(0,2,0)==-1 && classify(0,0,0)==-1); // shake/free fall
static_assert(classify(.1F,.96F,.15F)==0); // small tilt/noise
static_assert(screen_angle(0,0)==0 && screen_angle(90,0)==270);
static_assert(screen_angle(180,0)==180 && screen_angle(270,0)==90);
// Preserve the actual board's upright calibration (raw pose 270, offset 90).
static_assert(screen_angle(270,90)==0 && screen_angle(0,90)==270);
static_assert(screen_angle(90,90)==180 && screen_angle(180,90)==90);
constexpr bool touch_rotation_roundtrip() {
    for(int a : {0,90,180,270}) {
        for(int16_t x : {int16_t(0),int16_t(123),int16_t(239),int16_t(479)}) {
            for(int16_t y : {int16_t(0),int16_t(77),int16_t(301),int16_t(479)}) {
                // Physical pixel after panel MADCTL swap, then mirror.
                int16_t px=(a==90 || a==270)?y:x;
                int16_t py=(a==90 || a==270)?x:y;
                if(a==90 || a==180)px=479-px;
                if(a==180 || a==270)py=479-py;
                inverse_touch(px,py,a);
                if(px!=x || py!=y)return false;
            }
        }
    }
    int16_t x=-1,y=480;inverse_touch(x,y,0);
    return x==0 && y==479;
}
static_assert(touch_rotation_roundtrip());
