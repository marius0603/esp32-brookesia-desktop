#include "../platform/super_s3_216/main/modules/child_mode/policy.hpp"
using namespace child_policy;
static_assert(visible(false,0,"brookesia.general.settings"));
static_assert(visible(true,7,"local.audiobook") && visible(true,7,"local.weather") && visible(true,7,"local.flipclock"));
static_assert(visible(true,1,"local.nurserysongs") && !visible(true,0,"local.nurserysongs"));
static_assert(!visible(true,7,"local.voiceassistant") && visible(true,15,"local.voiceassistant"));
static_assert(!visible(true,15,"brookesia.general.settings") && !visible(true,15,"brookesia.general.files"));
static_assert(!visible(true,15,"brookesia.general.app_store") && !visible(true,15,"local.future_app"));
static_assert(visible(true,0,"local.childmode") && visible(true,0,"brookesia.system.super.shell"));
static_assert(night(21,21,8) && night(23,21,8) && night(0,21,8) && night(7,21,8));
static_assert(!night(8,21,8) && !night(20,21,8));
static_assert(night(12,10,15) && !night(15,10,15) && !night(9,10,15));
static_assert(!night(12,8,8));
static_assert(reserve(0)==0 && reserve(1)==60 && reserve(60)==60 && reserve(61)==120);

static_assert(visible(true,1,"local.radio") && !visible(true,0,"local.radio"));
static_assert(app_bit("local.radio")==app_bit("local.audiobook") && app_bit("local.radio")==app_bit("local.nurserysongs"));
static_assert(audio_allowed(true,true,1,false) && audio_allowed(true,false,0,true));
static_assert(!audio_allowed(false,false,1,false) && !audio_allowed(true,true,0,false) && !audio_allowed(true,true,1,true));
