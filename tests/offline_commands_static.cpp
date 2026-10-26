#include "../platform/super_s3_216/main/modules/offline_voice/commands.hpp"
#include <limits>
using offline_commands::accept;
static_assert(accept(1,0.8f,0,0));
static_assert(accept(8,0.8f,8,0.79f)); // Variants of one intent may agree.
static_assert(!accept(8,0.8f,7,0.79f)); // Different close candidates must retry.
static_assert(accept(6,0.9f,5,0.6f));
static_assert(!accept(0,0.9f,0,0) && !accept(9,0.9f,0,0));
static_assert(!accept(1,0.61f,0,0));
static_assert(!accept(1,std::numeric_limits<float>::quiet_NaN(),0,0));
static_assert(!accept(1,std::numeric_limits<float>::infinity(),0,0));
static_assert(!accept(1,0.8f,2,std::numeric_limits<float>::quiet_NaN()));
constexpr bool all_intents(){
 for(int id=1;id<=8;++id){bool found=false;for(auto p:offline_commands::phrases)if(p.id==id)found=true;if(!found)return false;}
 return true;
}
static_assert(all_intents());

static_assert(accept(2,0.50f,0,0));
static_assert(!accept(2,0.44f,0,0));
static_assert(!accept(2,0.50f,3,0.40f));
static_assert(!accept(5,0.61f,0,0));
