#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>
namespace pc_voice {
constexpr size_t header_bytes=12,max_pcm_bytes=1920;
enum class Frame { Invalid,Stale,Current };
inline uint32_t read32(const uint8_t *p){return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);}
inline Frame inspect(const uint8_t *data,size_t bytes,uint32_t turn){
    if(!data||bytes<=header_bytes||bytes>header_bytes+max_pcm_bytes||(bytes-header_bytes)%2||std::memcmp(data,"VPC1",4))return Frame::Invalid;
    return read32(data+4)==turn?Frame::Current:Frame::Stale;
}
}
