#include <cassert>
#include <cstdint>
#include <cstring>
#include "../platform/super_s3_216/main/modules/voice_assistant/pcm_protocol.hpp"
int main(){
    const int16_t source[]={0,1000,-1000,2000,-2000,5000,-5000,15000,-15000,30000,-30000,0,200,400,-200,-400};
    // Independent reference: CPython 3.12 audioop.lin2adpcm/adpcm2lin.
    const uint8_t expected[]={7,247,247,247,247,242,128,128};
    const int16_t decoded[]={0,11,-19,44,-92,201,-430,927,-1983,4253,-9119,436,-1301,278,-1157,148};
    pc_voice::ImaState state;uint8_t output[8]{};int16_t pcm[16]{};
    assert(pc_voice::ima_encode(source,16,output,state)==8);
    assert(!std::memcmp(output,expected,8));assert(state.predictor==148&&state.index==75);
    assert(pc_voice::ima_decode(expected,8,pcm,16,{}));assert(!std::memcmp(pcm,decoded,sizeof(pcm)));
    assert(!pc_voice::ima_decode(expected,8,pcm,16,{0,89}));
    assert(!pc_voice::ima_decode(expected,7,pcm,16,{}));
    uint8_t packet[25]={'V','P','A','1',1,0,0,0,0,0,0,0,0,0,0,16,0};
    std::memcpy(packet+17,expected,8);
    assert(pc_voice::inspect(packet,sizeof(packet),1)==pc_voice::Frame::Current);
    assert(pc_voice::inspect(packet,sizeof(packet),2)==pc_voice::Frame::Stale);
    packet[14]=89;assert(pc_voice::inspect(packet,sizeof(packet),1)==pc_voice::Frame::Invalid);
    packet[14]=0;packet[15]=0;assert(pc_voice::inspect(packet,sizeof(packet),1)==pc_voice::Frame::Invalid);
}
