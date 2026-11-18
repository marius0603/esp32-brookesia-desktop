#include "../platform/super_s3_216/main/modules/child_mode/policy.hpp"
using namespace child_policy;
static_assert(visible(false,0,"brookesia.general.settings"));
static_assert(visible(true,7,"local.audiobook") && visible(true,7,"local.weather") && visible(true,7,"local.flipclock"));
static_assert(visible(true,songs,"local.nurserysongs") && !visible(true,audiobook,"local.nurserysongs"));
static_assert(!visible(true,7,"local.voiceassistant") && visible(true,15,"local.voiceassistant"));
static_assert(!visible(true,15,"brookesia.general.settings") && !visible(true,15,"brookesia.general.files"));
static_assert(!visible(true,15,"brookesia.general.app_store") && !visible(true,15,"local.future_app"));
static_assert(visible(true,0,"local.childmode") && visible(true,0,"brookesia.system.super.shell"));
static_assert(night(21,21,8) && night(23,21,8) && night(0,21,8) && night(7,21,8));
static_assert(!night(8,21,8) && !night(20,21,8));
static_assert(night(12,10,15) && !night(15,10,15) && !night(9,10,15));
static_assert(!night(12,8,8));
static_assert(reserve(0)==0 && reserve(1)==60 && reserve(60)==60 && reserve(61)==120);

static_assert(visible(true,radio,"local.radio") && !visible(true,audiobook|songs,"local.radio"));
static_assert(!visible(true,songs|radio,"local.audiobook"));
static_assert(migrate_mask(31)==127 && migrate_mask(30)==30);
static_assert(valid_mask(default_mask) && !valid_mask(128));
static_assert(allowed(true,true,songs,false,songs) && !allowed(true,true,songs,false,audiobook));
static_assert(allowed(true,false,0,true,radio) && !allowed(false,false,audiobook,false,audiobook));
static_assert(!allowed(true,true,radio,true,radio));
static_assert(station_allowed(true,false,0,0));
static_assert(station_allowed(true,true,2,3));
static_assert(!station_allowed(true,true,1,0) && !station_allowed(true,true,2,1));
static_assert(!station_allowed(false,true,1,1) && !station_allowed(true,true,0,3));
static_assert(is_song_path("/sdcard/audiobooks/songs/lullabies/song.mp3"));
static_assert(is_song_path("/sdcard/audiobooks//SoNgS. /song.mp3"));
static_assert(!is_song_path("/sdcard/audiobooks/songs_extra/story.mp3"));
static_assert(!is_song_path("/sdcard/audiobooks/stories/songs/story.mp3"));

static_assert(volume_limit_max==100);

static_assert(app_bit("local.gravitymaze")==16);
static_assert(visible(true,16,"local.gravitymaze") && !visible(true,7,"local.gravitymaze"));
