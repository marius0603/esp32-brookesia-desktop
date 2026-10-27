#include <cassert>
#include <cstdint>
#include "../platform/super_s3_216/main/modules/voice_assistant/pcm_protocol.hpp"
int main(){
    uint8_t packet[1933]={'V','P','C','1',0x78,0x56,0x34,0x12,1,0,0,0};
    using pc_voice::Frame;
    assert(pc_voice::read32(packet+4)==0x12345678);
    assert(pc_voice::inspect(packet,1932,0x12345678)==Frame::Current);
    assert(pc_voice::inspect(packet,1932,2)==Frame::Stale);
    assert(pc_voice::inspect(packet,12,0x12345678)==Frame::Invalid);
    assert(pc_voice::inspect(packet,13,0x12345678)==Frame::Invalid);
    assert(pc_voice::inspect(packet,1933,0x12345678)==Frame::Invalid);
    assert(pc_voice::inspect(nullptr,14,1)==Frame::Invalid);
    packet[0]='X';assert(pc_voice::inspect(packet,14,0x12345678)==Frame::Invalid);
}
