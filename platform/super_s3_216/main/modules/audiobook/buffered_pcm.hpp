#pragma once
#include <algorithm>
#include <atomic>
#include <cstring>
#include <functional>
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/ringbuf.h"
#include "freertos/idf_additions.h"

// SD/decoder runs independently of the speaker. Each item carries a seek epoch
// and the source position, so queued data cannot play after a seek or advance
// the bookmark before it has actually been submitted to the codec.
class StoryPcmBuffer {
public:
    struct Header {uint32_t epoch,position,bytes;};
    using Writer=std::function<bool(const uint8_t *,size_t,uint32_t,uint32_t)>;
    static constexpr size_t preferred_capacity=128*1024,minimum_capacity=64*1024;
    static constexpr size_t max_pcm=8192,stack_bytes=4096;
    // App workers can stay runnable throughout a page transition. Give PCM
    // delivery priority over those workers; I2S writes and a full queue block.
    static constexpr UBaseType_t decoder_priority=CONFIG_BROOKESIA_SYSTEM_CORE_WORKER_PRIORITY+1;
    static constexpr UBaseType_t output_priority=decoder_priority+1;
    static_assert(output_priority<configMAX_PRIORITIES);
    StoryPcmBuffer(Writer writer,std::atomic<bool> &paused,std::atomic<uint32_t> &epoch,
                   std::atomic<uint32_t> &starvations,std::atomic<uint32_t> &write_gap,std::function<bool()> abort,
                   size_t capacity=minimum_capacity,UBaseType_t priority=6)
        :writer_(std::move(writer)),paused_(paused),epoch_(epoch),starvations_(starvations),write_gap_(write_gap),
         abort_(std::move(abort)),capacity_(capacity),priority_(priority){}
    bool start(){
        constexpr auto caps=MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT;
        ring_=xRingbufferCreateWithCaps(capacity_,RINGBUF_TYPE_NOSPLIT,caps);
        if(!ring_ && capacity_>minimum_capacity){
            capacity_=minimum_capacity;
            ring_=xRingbufferCreateWithCaps(capacity_,RINGBUF_TYPE_NOSPLIT,caps);
        }
        staging_=static_cast<uint8_t *>(heap_caps_malloc(sizeof(Header)+max_pcm,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
        if(!ring_ || !staging_)return false;
        live_=true;
        if(xTaskCreatePinnedToCore([](void *p){auto *self=static_cast<StoryPcmBuffer *>(p);self->consume();vTaskDelete(nullptr);},
            "story_pcm",stack_bytes,this,priority_,nullptr,1)!=pdPASS){live_=false;return false;}
        return true;
    }
    bool send(const int16_t *pcm,size_t bytes,uint32_t position,const std::function<bool()> &cancel){
        if(bytes>max_pcm || bytes%4)return false;
        Header h{epoch_.load(),position,static_cast<uint32_t>(bytes)};
        std::memcpy(staging_,&h,sizeof(h));std::memcpy(staging_+sizeof(h),pcm,bytes);
        while(!quit_ && !failed_ && !cancel()){
            if(xRingbufferSend(ring_,staging_,sizeof(h)+bytes,pdMS_TO_TICKS(20))==pdTRUE){
                prefilled_+=bytes;if(prefilled_>=capacity_/2)primed_=true;return true;
            }
        }
        return false;
    }
    void finish(bool drain){
        if(!live_)return;
        drain_=drain;quit_=true;primed_=true;
        while(live_)vTaskDelay(pdMS_TO_TICKS(5));
    }
    bool failed()const{return failed_;}
    size_t capacity()const{return capacity_;}
    ~StoryPcmBuffer(){finish(false);if(ring_)vRingbufferDeleteWithCaps(ring_);heap_caps_free(staging_);}
private:
    Writer writer_;std::atomic<bool> &paused_;std::atomic<uint32_t> &epoch_,&starvations_,&write_gap_;
    std::function<bool()> abort_;
    RingbufHandle_t ring_=nullptr;uint8_t *staging_=nullptr;size_t prefilled_=0;
    size_t capacity_;
    const UBaseType_t priority_;
    std::atomic<bool> live_{false},quit_{false},drain_{false},failed_{false},primed_{false};
    void consume(){
        while(!primed_ && !quit_ && !abort_())vTaskDelay(pdMS_TO_TICKS(5));
        bool starving=false;int64_t previous=0;
        while(!quit_ || drain_){
            if(abort_())break;
            if(paused_){previous=0;vTaskDelay(pdMS_TO_TICKS(10));continue;}
            size_t size=0;auto *item=static_cast<uint8_t *>(xRingbufferReceive(ring_,&size,pdMS_TO_TICKS(10)));
            if(!item){
                if(quit_)break;
                if(!starving){++starvations_;starving=true;}
                continue;
            }
            Header h{};
            if(size>=sizeof(h))std::memcpy(&h,item,sizeof(h));
            bool okay=true;
            if(h.epoch==epoch_ && size==sizeof(h)+h.bytes){
                // Bound each codec write to 32 ms of 16kHz stereo PCM.
                for(size_t at=0;at<h.bytes;at+=2048){
                    while(paused_ && !(quit_ && !drain_) && !abort_() && h.epoch==epoch_){previous=0;vTaskDelay(pdMS_TO_TICKS(10));}
                    if((quit_ && !drain_) || abort_() || h.epoch!=epoch_)break;
                    const size_t n=std::min<size_t>(2048,h.bytes-at);
                    const auto began=esp_timer_get_time();
                    if(previous)write_gap_=std::max(write_gap_.load(),uint32_t(began-previous));
                    okay=writer_(item+sizeof(h)+at,n,at+n==h.bytes?h.position:UINT32_MAX,h.epoch);
                    previous=esp_timer_get_time();
                    if(!okay)break;
                    // The output task has higher priority than volume/control
                    // RPCs. Yield after releasing the codec lock so a waiter
                    // can acquire it before the next blocking I2S write.
                    vTaskDelay(1);
                }
            }else previous=0;
            vRingbufferReturnItem(ring_,item);starving=false;
            if(!okay){failed_=true;break;}
        }
        live_=false;
    }
};
