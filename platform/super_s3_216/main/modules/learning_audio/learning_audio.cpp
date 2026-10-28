#include "learning_audio.hpp"
#include "media_rules.hpp"
#include "../audiobook/dr_wav.h"
#include "../audio_ownership.hpp"
#include "../child_mode/child_mode.hpp"
#include "../offline_voice/offline_voice.hpp"
#include "brookesia/hal_interface/interface.hpp"
#include "brookesia/hal_interface/interfaces/audio/codec_recorder.hpp"
#include "brookesia/hal_interface/interfaces/audio/codec_player.hpp"
#include "esp_heap_caps.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>
#include <cstdio>
#include <mutex>
using namespace esp_brookesia;
using namespace esp_brookesia::service;
namespace {
constexpr size_t samples=480,block_bytes=samples*2,max_bytes=learning_media::sample_rate*2*learning_media::max_record_seconds;
class LearningAudio final:public ServiceBase {
public:
    LearningAudio():ServiceBase({.name="LearningAudio",.description="Offline learning sounds and volatile recording replay",.version="0.1.0",.dependencies={"AudioPlayback"}}){}
private:
    static bool repair_font() {
        // Repair only the learning font entry written by the early installer.
        // Preserve all other registered fonts and metadata.
        constexpr const char *path="/littlefs/system/fonts/index.json";
        FILE *file=fopen(path,"rb");
        if(!file)return true;
        fseek(file,0,SEEK_END);const long size=ftell(file);rewind(file);
        if(size<=0||size>16384){fclose(file);return true;}
        std::string raw(size,'\0');
        const bool read=fread(raw.data(),1,raw.size(),file)==raw.size();fclose(file);
        if(!read)return true;
        boost::system::error_code ec;auto document=boost::json::parse(raw,ec);
        if(ec||!document.is_object())return true;
        auto *fonts=document.as_object().if_contains("fonts");
        if(!fonts||!fonts->is_array())return true;
        bool changed=false;
        for(auto &value:fonts->as_array()){
            if(!value.is_object())continue;
            auto &entry=value.as_object();
            auto *id=entry.if_contains("id");auto *source=entry.if_contains("src");
            if(id&&id->is_string()&&id->as_string()=="learning"&&source&&source->is_string()&&source->as_string()=="learning-extra.ttf"&&!entry.if_contains("languages")){
                entry["languages"]=boost::json::array{"en","zh_CN"};changed=true;
            }
        }
        if(!changed)return true;
        const auto fixed=boost::json::serialize(document);
        constexpr const char *temporary="/littlefs/system/fonts/index.json.learning-fix";
        file=fopen(temporary,"wb");if(!file)return false;
        bool saved=fwrite(fixed.data(),1,fixed.size(),file)==fixed.size();
        saved=fflush(file)==0&&saved;saved=fclose(file)==0&&saved;
        return saved&&std::rename(temporary,path)==0;
    }
    bool on_init() override {
        // The manager initializes services on a PSRAM stack. Flash writes must
        // run on an internal stack while the SPI cache is disabled.
        struct Repair { SemaphoreHandle_t done; bool result=false; } repair{xSemaphoreCreateBinary()};
        if(!repair.done)return false;
        const auto created=xTaskCreatePinnedToCore([](void *context){
            auto &r=*static_cast<Repair *>(context);
            r.result=repair_font();xSemaphoreGive(r.done);vTaskDelete(nullptr);
        },"learning_font",12288,&repair,3,nullptr,0);
        if(created!=pdPASS){vSemaphoreDelete(repair.done);return false;}
        xSemaphoreTake(repair.done,portMAX_DELAY);vSemaphoreDelete(repair.done);
        return repair.result;
    }
    std::mutex operation_,state_mutex_;
    std::atomic<bool> live_{false},cancel_{false},finish_{false},forget_{false};
    std::atomic<unsigned> recorded_{0},played_{0},level_{0},stack_min_{8192},job_{0};
    uint8_t *recording_=nullptr;
    std::string state_="Idle",error_,path_;
    unsigned limit_=5;
    void state(const char *name){std::lock_guard lock(state_mutex_);state_=name;}
    void fail(const char *message){std::lock_guard lock(state_mutex_);state_="Error";error_=message;}
    boost::json::object snapshot(){std::lock_guard lock(state_mutex_);return {
        {"state",state_},{"error",error_},{"active",live_.load()},{"recorded_bytes",recorded_.load()},
        {"recorded_ms",recorded_.load()*1000/32000},{"played_bytes",played_.load()},{"level",level_.load()},
        {"max_record_seconds",learning_media::max_record_seconds},{"stack_free_min_bytes",stack_min_.load()}};}
    void discard(){
        std::lock_guard lock(operation_);forget_=true;cancel_=true;
        if(!live_){if(recording_){memset(recording_,0,max_bytes);heap_caps_free(recording_);recording_=nullptr;}recorded_=0;state("Idle");}
    }
    std::expected<void,std::string> launch(unsigned mode,const std::string &path="",double seconds=5){
        std::lock_guard lock(operation_);
        if(!child_mode_learning_allowed())return std::unexpected("轻学习未获家长授权，或已到休息时间");
        if(live_)return std::unexpected("音频正在处理，请稍候");
        if(mode==1&&!learning_media::allowed_path(path))return std::unexpected("请选择内容包内的WAV音频");
        if(mode==2&&(!recording_||!recorded_))return std::unexpected("请先录一段跟读");
        if(mode==3&&(!std::isfinite(seconds)||seconds<1||seconds>learning_media::max_record_seconds||seconds!=std::floor(seconds)))return std::unexpected("录音时长需为1至8秒");
        if(!offline_voice_prepare_online())return std::unexpected("麦克风正在释放，请稍后重试");
        if(!local_audio::claim(local_audio::Learning))return std::unexpected("请先停止其他音频");
        if(mode==3){
            if(!recording_)recording_=static_cast<uint8_t *>(heap_caps_calloc(1,max_bytes,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
            if(!recording_){local_audio::release(local_audio::Learning);return std::unexpected("录音内存不足");}
            memset(recording_,0,max_bytes);recorded_=0;
        }
        cancel_=finish_=forget_=false;played_=level_=0;stack_min_=8192;job_=mode;limit_=unsigned(seconds);path_=path;
        {std::lock_guard lock(state_mutex_);error_.clear();state_="Starting";}
        live_=true;local_audio::learning_busy=true;
        if(xTaskCreatePinnedToCore([](void *p){static_cast<LearningAudio *>(p)->run();vTaskDelete(nullptr);},"learning_audio",8192,this,4,nullptr,0)!=pdPASS){
            live_=false;local_audio::release(local_audio::Learning);fail("音频任务内存不足");return std::unexpected("Audio task allocation failed");}
        return {};
    }
    void run(){
        const auto mode=job_.load();
        auto players=hal::acquire_interfaces<hal::audio::CodecPlayerIface>();
        auto recorders=hal::acquire_interfaces<hal::audio::CodecRecorderIface>();
        auto player=players.empty()?hal::InterfaceHandle<hal::audio::CodecPlayerIface>{}:std::move(players.front());
        auto recorder=recorders.empty()?hal::InterfaceHandle<hal::audio::CodecRecorderIface>{}:std::move(recorders.front());
        auto *pcm=static_cast<int16_t *>(heap_caps_malloc(block_bytes,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
        auto *raw=static_cast<uint8_t *>(heap_caps_malloc(samples*4*4,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
        auto *wav=static_cast<drwav *>(heap_caps_calloc(1,sizeof(drwav),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
        bool rec_open=false,play_open=false,wav_open=false,failed=false;
        auto error=[&](const char *text){fail(text);failed=true;};
        do {
            if(!pcm||!raw||!wav||!player||!recorder){error("音频设备或内存不可用");break;}
            if(mode==3){
                if(!recorder->open()){error("无法打开麦克风");break;}rec_open=true;
                const auto info=recorder->get_info();
                if(info.sample_rate!=16000||info.channels<1||info.channels>4||(info.bits!=16&&info.bits!=32)){error("麦克风格式不兼容");break;}
                const auto at=info.mic_layout.find('M');const unsigned channel=at<info.channels?at:info.channels-1;
                state("Recording");
                while(!cancel_&&!finish_&&child_mode_learning_allowed()&&recorded_+block_bytes<=limit_*32000){
                    if(!recorder->read_data(raw,samples*info.channels*(info.bits/8))){error("麦克风读取失败");break;}
                    unsigned peak=0;
                    for(size_t i=0;i<samples;++i){const int value=info.bits==32?reinterpret_cast<int32_t *>(raw)[i*info.channels+channel]>>16:reinterpret_cast<int16_t *>(raw)[i*info.channels+channel];pcm[i]=int16_t(value);peak=std::max(peak,unsigned(std::abs(value)));}
                    memcpy(recording_+recorded_,pcm,block_bytes);recorded_+=block_bytes;level_=std::min(100u,peak/100);
                    stack_min_=std::min(stack_min_.load(),unsigned(uxTaskGetStackHighWaterMark(nullptr)));vTaskDelay(1);
                }
            }else{
                if(mode==1){
                    wav_open=drwav_init_file(wav,path_.c_str(),nullptr);
                    if(!wav_open||wav->sampleRate!=16000||wav->channels!=1||wav->bitsPerSample!=16||wav->totalPCMFrameCount>16000*20){error("音频需为16kHz单声道16位WAV，最长20秒");break;}
                }
                player->close();if(!player->open({.bits=16,.channels=1,.sample_rate=16000})){error("无法打开喇叭");break;}
                play_open=true;if(player->is_pa_on_off_supported())player->set_pa_on_off(true);state("Playing");
                size_t offset=0;
                while(!cancel_&&child_mode_learning_allowed()){
                    size_t count=0;
                    if(mode==1)count=drwav_read_pcm_frames_s16(wav,samples,pcm);
                    else {count=std::min(size_t(recorded_)-offset,block_bytes)/2;if(count)memcpy(pcm,recording_+offset,count*2);offset+=count*2;}
                    if(!count)break;
                    if(!player->write_data(reinterpret_cast<uint8_t *>(pcm),count*2)){error("音频播放失败");break;}
                    played_+=count*2;stack_min_=std::min(stack_min_.load(),unsigned(uxTaskGetStackHighWaterMark(nullptr)));vTaskDelay(1);
                }
            }
        }while(false);
        if(rec_open)recorder->close();
        if(play_open){if(player->is_pa_on_off_supported())player->set_pa_on_off(false);player->close();}
        if(wav_open)drwav_uninit(wav);
        heap_caps_free(pcm);heap_caps_free(raw);heap_caps_free(wav);level_=0;
        std::lock_guard lock(operation_);
        if(forget_){if(recording_){memset(recording_,0,max_bytes);heap_caps_free(recording_);recording_=nullptr;}recorded_=0;}
        if(!failed)state(cancel_?"Idle":mode==3?"Recorded":"Idle");
        local_audio::release(local_audio::Learning);live_=false;
    }
    void on_stop() override{cancel_=true;while(live_)vTaskDelay(pdMS_TO_TICKS(10));discard();}
    std::vector<FunctionSchema> get_function_schemas() override{return {
        {"PlayFile","Play a local learning WAV",{{"Path","Pack WAV path",FunctionValueType::String}}},
        {"StartRecording","Record locally in volatile memory",{{"Seconds","1 to 8",FunctionValueType::Number,5.0}}},
        {"StopRecording","Finish current recording",{}},{"Replay","Replay last recording",{}},
        {"Stop","Cancel active audio",{}},{"Discard","Erase the volatile recording",{}},
        {"GetState","Read learning audio state",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Learning audio"}}};}
    FunctionHandlerList get_function_handlers() override{return {
        BROOKESIA_SERVICE_FUNC_HANDLER_1("PlayFile","Path",std::string,launch(1,PARAM)),
        BROOKESIA_SERVICE_FUNC_HANDLER_1("StartRecording","Seconds",double,launch(3,"",PARAM)),
        {"StopRecording",[this](FunctionParameterMap &&)->FunctionResult{finish_=true;return {.success=true};}},
        BROOKESIA_SERVICE_FUNC_HANDLER_0("Replay",launch(2)),
        {"Stop",[this](FunctionParameterMap &&)->FunctionResult{cancel_=true;return {.success=true};}},
        {"Discard",[this](FunctionParameterMap &&)->FunctionResult{discard();return {.success=true};}},
        {"GetState",[this](FunctionParameterMap &&)->FunctionResult{return {.success=true,.data=FunctionValue(snapshot())};}}};}
};
}
std::shared_ptr<ServiceBase> make_learning_audio_service(){return std::make_shared<LearningAudio>();}
