#pragma once
#include <algorithm>
#include <cstddef>
#include <cstdint>

// IMA/DVI 4-bit ADPCM, high nibble first, matching Python 3.12 audioop.
// Each transport packet carries its INITIAL predictor/index independently.
namespace pc_voice {
struct ImaState { int predictor=0,index=0; };
constexpr int ima_steps[89]={7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,371,408,449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,6484,7132,7845,8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,22385,24623,27086,29794,32767};
constexpr int ima_index[8]={-1,-1,-1,-1,2,4,6,8};
inline int16_t ima_apply(unsigned code,ImaState &state){
    const int step=ima_steps[state.index];
    int delta=step>>3;
    if(code&4)delta+=step;
    if(code&2)delta+=step>>1;
    if(code&1)delta+=step>>2;
    state.predictor=std::clamp(state.predictor+((code&8)?-delta:delta),-32768,32767);
    state.index=std::clamp(state.index+ima_index[code&7],0,88);
    return static_cast<int16_t>(state.predictor);
}
inline size_t ima_encode(const int16_t *pcm,size_t samples,uint8_t *output,ImaState &state){
    for(size_t i=0;i<samples;++i){
        int difference=int(pcm[i])-state.predictor;
        unsigned code=difference<0?8:0;
        if(difference<0)difference=-difference;
        int step=ima_steps[state.index];
        for(unsigned bit=4;bit;bit>>=1,step>>=1)if(difference>=step){code|=bit;difference-=step;}
        ima_apply(code,state);
        if(i%2)output[i/2]|=uint8_t(code);
        else output[i/2]=uint8_t(code<<4);
    }
    return (samples+1)/2;
}
inline bool ima_decode(const uint8_t *input,size_t bytes,int16_t *output,size_t samples,ImaState state){
    if(!input||!output||!samples||bytes!=(samples+1)/2||state.index<0||state.index>88)return false;
    for(size_t i=0;i<samples;++i)output[i]=ima_apply((i%2?input[i/2]:input[i/2]>>4)&15,state);
    return true;
}
inline uint16_t read16(const uint8_t *p){return uint16_t(p[0])|(uint16_t(p[1])<<8);}
inline void write16(uint8_t *p,uint16_t value){p[0]=uint8_t(value);p[1]=uint8_t(value>>8);}
}
