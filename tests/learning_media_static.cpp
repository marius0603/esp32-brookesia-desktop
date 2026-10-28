#include "../platform/super_s3_216/main/modules/learning_audio/media_rules.hpp"
#include "../platform/super_s3_216/main/modules/child_mode/policy.hpp"
using learning_media::allowed_path;
static_assert(allowed_path("/sdcard/learning/packs/starter/audio/en-hello.wav"));
static_assert(!allowed_path("/sdcard/learning/packs/starter/../outside.wav"));
static_assert(!allowed_path("/sdcard/learning/packs//outside.wav"));
static_assert(!allowed_path("/sdcard/learning/packs/starter/audio/test.mp3"));
static_assert(!allowed_path("https://example.com/animal.wav"));
static_assert(!allowed_path("/littlefs/animal.wav"));
static_assert(learning_media::max_record_seconds==8);
static_assert(!child_policy::visible(true,7,"local.lightlearning"));
static_assert(!child_policy::visible(true,15,"local.lightlearning"));
static_assert(child_policy::visible(true,16,"local.lightlearning"));
static_assert(child_policy::visible(true,23,"local.audiobook"));
static_assert(child_policy::valid_mask(7));
static_assert(child_policy::valid_mask(23)); // persisted default + learning survives reboot
static_assert(child_policy::valid_mask(31));
static_assert(!child_policy::valid_mask(32));
int main(){}
