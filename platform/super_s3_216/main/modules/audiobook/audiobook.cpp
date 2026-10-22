#include "audiobook.hpp"
#include "../child_mode/child_mode.hpp"
#include "../audio_ownership.hpp"
#include <algorithm>
#include <atomic>
#include <string_view>
#include <cmath>
#include <cstring>
#include <dirent.h>
#include <mutex>
#include <sys/stat.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_heap_caps.h"
#include "brookesia/hal_interface/interface.hpp"
#include "brookesia/hal_interface/interfaces/audio/codec_player.hpp"
#include "dr_mp3.h"
#include "dr_wav.h"

using namespace esp_brookesia;
using namespace esp_brookesia::service;
namespace {
void *audio_malloc(size_t size, void *) {
    void *p = heap_caps_malloc(size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    return p ? p : heap_caps_malloc(size, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
}
void *audio_realloc(void *p, size_t size, void *) {
    return heap_caps_realloc(p, size, MALLOC_CAP_8BIT);
}
void audio_free(void *p, void *) { heap_caps_free(p); }
bool supported(const std::string &path) {
    auto at = path.find_last_of('.');
    if (at == std::string::npos) return false;
    auto ext = path.substr(at);
    std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
    return ext == ".mp3" || ext == ".wav";
}
bool permitted(const std::string &path) {
    return path.starts_with("/sdcard/audiobooks/") && path.find("..") == std::string::npos && supported(path);
}
void scan(const std::string &path, unsigned depth, std::vector<std::string> &files) {
    DIR *dir = opendir(path.c_str());
    if (!dir) return;
    while (auto *entry = readdir(dir)) {
        if (files.size() >= 512) break;
        if (entry->d_name[0] == '.') continue;
        const auto file = path + "/" + entry->d_name;
        struct stat st{};
        if (stat(file.c_str(), &st) != 0) continue;
        if (S_ISDIR(st.st_mode) && depth) scan(file, depth - 1, files);
        else if (S_ISREG(st.st_mode) && supported(file)) files.push_back(file);
    }
    closedir(dir);
}
class Audiobook final : public ServiceBase {
public:
    Audiobook() : ServiceBase({.name="Audiobook", .description="Local SD audiobook player", .version="0.1.0", .dependencies={"AudioPlayback"}}) {}
private:
    std::mutex mutex_;
    std::string path_, state_="Idle", error_;
    std::atomic<bool> live_{false}, cancel_{false}, paused_{false};
    std::atomic<int32_t> seek_{-1};
    std::atomic<uint32_t> position_{0}, duration_{0}, bytes_{0};
    void state(const char *s, const char *error="") {
        local_audio::audiobook_busy=std::string_view(s)=="Loading" || std::string_view(s)=="Playing";
        std::lock_guard<std::mutex> lock(mutex_); state_=s; error_=error;
    }
    std::expected<void,std::string> stop() {
        cancel_=true;
        for (int i=0; live_ && i<500; ++i) vTaskDelay(pdMS_TO_TICKS(10));
        if (live_) return std::unexpected("Audio worker is still stopping");
        return {};
    }
    void on_stop() override { stop(); }
    std::expected<void,std::string> play(const std::string &path, double start) {
        if(!child_mode_audiobook_allowed())return std::unexpected("听书已被家长限制，或已到休息时间");
        if (path!="@tone" && !permitted(path)) return std::unexpected("Only MP3/WAV under /sdcard/audiobooks is supported");
        if (!std::isfinite(start) || start<0 || start>86400) return std::unexpected("Invalid playback position");
        if (path!="@tone") {
            struct stat st{};
            if (stat(path.c_str(),&st)!=0 || !S_ISREG(st.st_mode)) return std::unexpected("Audio file is missing; check SD card");
        }
        auto stopped=stop(); if(!stopped) return stopped;
        if(!local_audio::claim(local_audio::Audiobook))return std::unexpected("Voice assistant is using audio; close it first");
        local_audio::audiobook_busy=true;
        {std::lock_guard<std::mutex> lock(mutex_);path_=path;state_="Loading";error_.clear();}
        position_=0;duration_=0;bytes_=0;cancel_=false;paused_=false;seek_=static_cast<int32_t>(start);live_=true;
        TaskHandle_t task=nullptr;
        if (xTaskCreatePinnedToCore([](void *ctx){static_cast<Audiobook *>(ctx)->run();vTaskDelete(nullptr);},
              "audiobook",12288,this,4,&task,0)!=pdPASS) {
            local_audio::release(local_audio::Audiobook);live_=false;state("Error","Not enough internal RAM for audio task");return std::unexpected("Audio task allocation failed");
        }
        return {};
    }
    boost::json::object snapshot() {
        std::lock_guard<std::mutex> lock(mutex_);
        return {{"state",state_},{"path",path_},{"error",error_},{"position",position_.load()},
                {"duration",duration_.load()},{"bytes_written",bytes_.load()},{"active",live_.load()}};
    }
    std::expected<boost::json::object,std::string> list() {
        struct stat st{};
        const bool mounted=stat("/sdcard",&st)==0 && S_ISDIR(st.st_mode);
        std::vector<std::string> paths;
        if(mounted) scan("/sdcard/audiobooks",2,paths);
        std::sort(paths.begin(),paths.end());
        boost::json::array entries;
        for(const auto &p:paths) entries.push_back(boost::json::object{{"path",p},{"title",p.substr(18)}});
        return boost::json::object{{"mounted",mounted},{"tracks",std::move(entries)},{"limit",512}};
    }
    std::vector<FunctionSchema> get_function_schemas() override {
        return {
            {"List","List local chapters",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Card and tracks"}},
            {"Play","Play local chapter",{{"Path","Local file",FunctionValueType::String},{"Position","Seconds",FunctionValueType::Number,0.0}}},
            {"Pause","Pause",{}},{"Resume","Resume",{}},{"Stop","Stop",{}},
            {"Seek","Seek in current chapter",{{"Seconds","Seconds",FunctionValueType::Number}}},
            {"GetState","Get player state",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Playback state"}},
            {"TestTone","Play a two second quiet test tone",{}}
        };
    }
    FunctionHandlerList get_function_handlers() override {
        return {
            BROOKESIA_SERVICE_FUNC_HANDLER_0("List",list()),
            BROOKESIA_SERVICE_FUNC_HANDLER_2("Play","Path",std::string,"Position",double,play(PARAM1,PARAM2)),
            {"Pause",[this](FunctionParameterMap &&)->FunctionResult{if(!live_)return {.success=false,.error_message="Nothing is playing"};paused_=true;state("Paused");return {.success=true};}},
            {"Resume",[this](FunctionParameterMap &&)->FunctionResult{if(!live_)return {.success=false,.error_message="Nothing to resume"};paused_=false;state("Playing");return {.success=true};}},
            BROOKESIA_SERVICE_FUNC_HANDLER_0("Stop",stop()),
            {"Seek",[this](FunctionParameterMap &&args)->FunctionResult{
                const double seconds=std::get<double>(args.at("Seconds"));
                if(!live_ || !std::isfinite(seconds) || seconds<0 || seconds>86400) return {.success=false,.error_message="Invalid seek"};
                seek_=static_cast<int32_t>(seconds);return {.success=true};}},
            {"GetState",[this](FunctionParameterMap &&)->FunctionResult{return {.success=true,.data=FunctionValue(snapshot())};}},
            BROOKESIA_SERVICE_FUNC_HANDLER_0("TestTone",play("@tone",0))
        };
    }
    void run() {
        auto codecs=hal::acquire_interfaces<hal::audio::CodecPlayerIface>();
        auto codec=codecs.empty()?hal::InterfaceHandle<hal::audio::CodecPlayerIface>{}:std::move(codecs.front());
        auto *mp3=static_cast<drmp3 *>(audio_malloc(sizeof(drmp3),nullptr));
        auto *wav=static_cast<drwav *>(audio_malloc(sizeof(drwav),nullptr));
        auto *pcm=static_cast<int16_t *>(audio_malloc(1024*2*sizeof(int16_t),nullptr));
        bool mp3open=false,wavopen=false,opened=false,failed=false,eof=false;
        std::string path;{std::lock_guard<std::mutex> lock(mutex_);path=path_;}
        const bool tone=path=="@tone";
        uint32_t rate=16000,channels=1;uint64_t frames=0,total=32000;
        const drmp3_allocation_callbacks mp3alloc{nullptr,audio_malloc,audio_realloc,audio_free};
        const drwav_allocation_callbacks wavalloc{nullptr,audio_malloc,audio_realloc,audio_free};
        auto fail=[&](const char *message){state("Error",message);failed=true;};
        do {
            if(!codec || !pcm || !mp3 || !wav){fail("Audio memory or codec unavailable");break;}
            if(!tone){
                auto ext=path.substr(path.find_last_of('.'));std::transform(ext.begin(),ext.end(),ext.begin(),::tolower);
                if(ext==".mp3") {
                    mp3open=drmp3_init_file(mp3,path.c_str(),&mp3alloc);
                    if(!mp3open){fail("Invalid or unsupported MP3");break;}
                    rate=mp3->sampleRate;channels=mp3->channels;
                    total=mp3->totalPCMFrameCount==DRMP3_UINT64_MAX?0:mp3->totalPCMFrameCount;
                }else{
                    wavopen=drwav_init_file(wav,path.c_str(),&wavalloc);
                    if(!wavopen){fail("Invalid or unsupported WAV");break;}
                    rate=wav->sampleRate;channels=wav->channels;total=wav->totalPCMFrameCount;
                }
            }
            if((channels!=1 && channels!=2) || rate<8000 || rate>48000){fail("Supported audio: mono/stereo, 8-48 kHz");break;}
            duration_=total/rate;
            codec->close();
            if(!codec->open({.bits=16,.channels=static_cast<uint8_t>(channels),.sample_rate=rate})) {fail("Failed to open speaker codec");break;}
            opened=true;
            if(codec->is_pa_on_off_supported())codec->set_pa_on_off(true);
            state("Playing");
            while(!cancel_) {
                if(!child_mode_audiobook_allowed())break;
                int32_t requested=seek_.exchange(-1);
                if(requested>=0){
                    uint64_t target=static_cast<uint64_t>(requested)*rate;
                    if(total)target=std::min(target,total);
                    bool ok=tone || (mp3open?drmp3_seek_to_pcm_frame(mp3,target):drwav_seek_to_pcm_frame(wav,target));
                    if(!ok){fail("Failed to seek audio");break;}frames=target;position_=frames/rate;
                }
                if(paused_){vTaskDelay(pdMS_TO_TICKS(20));continue;}
                size_t count;
                if(tone){
                    count=static_cast<size_t>(std::min<uint64_t>(1024,total-frames));
                    for(size_t i=0;i<count;++i)pcm[i]=static_cast<int16_t>(1000*std::sin(2*3.14159265*440*(frames+i)/rate));
                }else count=mp3open?drmp3_read_pcm_frames_s16(mp3,1024,pcm):drwav_read_pcm_frames_s16(wav,1024,pcm);
                if(!count){eof=true;break;}
                size_t size=count*channels*sizeof(int16_t);
                if(!codec->write_data(reinterpret_cast<uint8_t *>(pcm),size)){fail("Speaker write failed");break;}
                frames+=count;position_=frames/rate;bytes_+=size;
                vTaskDelay(1);
            }
        }while(false);
        if(opened){
            if(codec->is_pa_on_off_supported())codec->set_pa_on_off(false);
            codec->close();
        }
        if(mp3open)drmp3_uninit(mp3);
        if(wavopen)drwav_uninit(wav);
        audio_free(mp3,nullptr);audio_free(wav,nullptr);audio_free(pcm,nullptr);
        if(!failed)state(eof?"Ended":"Stopped");
        codec.reset();local_audio::release(local_audio::Audiobook);live_=false;
    }
};
}
std::shared_ptr<ServiceBase> make_audiobook_service(){return std::make_shared<Audiobook>();}
