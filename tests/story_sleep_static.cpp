#include "../platform/super_s3_216/main/modules/audiobook/story_sleep.hpp"
using namespace story_sleep;
static_assert(valid(0)&&valid(15)&&valid(30)&&valid(45));
static_assert(!valid(-1)&&!valid(10)&&!valid(60));
static_assert(remaining(0,900000)==900 && remaining(899999,900000)==1);
static_assert(remaining(900000,900000)==0 && remaining(900001,900000)==0);
static_assert(gain(779999,900000)==1000 && gain(780000,900000)==1000);
static_assert(gain(840000,900000)==500 && gain(899999,900000)==0);
static_assert(gain(900000,900000)==0 && gain(900001,900000)==0);
static_assert(dim(1000)==1000 && dim(500)==550 && dim(0)==100);
static_assert(gain(3000000,3120000)==1000 && gain(3060000,3120000)==500);
static_assert(remaining(0x100000000ULL,0x100000000ULL+2700000)==2700);
