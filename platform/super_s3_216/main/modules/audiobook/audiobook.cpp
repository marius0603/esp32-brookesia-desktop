#include "story_titles.hpp"
#include "audiobook.hpp"
#include "../child_mode/child_mode.hpp"
#include "../audio_ownership.hpp"
#include "../device_modes/device_modes.hpp"
#include "story_sleep.hpp"
#include "buffered_pcm.hpp"
#include "sonic/sonic.h"
#include <memory>
#include "esp_timer.h"
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
#include "brookesia/service_manager/service/manager.hpp"

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
constexpr const char *songs_root="/sdcard/audiobooks/songs";
bool is_song(const std::string &path) {return path.starts_with(std::string(songs_root)+"/");}
void scan_library(bool songs,std::vector<std::string> &files) {
    scan(songs?songs_root:"/sdcard/audiobooks",2,files);
    if(!songs)std::erase_if(files,[](const auto &path){return is_song(path);});
    std::sort(files.begin(),files.end());
}
const int16_t goodnight_pcm[]={
#include "assets/goodnight_pcm.inc"
};
class Audiobook final : public ServiceBase {
public:
    Audiobook() : ServiceBase({.name="Audiobook", .description="Local SD audiobook player", .version="0.1.0", .dependencies={"AudioPlayback"}}) {}
    void poll_sleep() {
        std::unique_lock operation(operation_,std::try_to_lock);
        if(!operation || !started_)return;
        {
            std::lock_guard lock(mutex_);
            if(deadline_ && !sleep_due_) {
                const auto now=uint64_t(esp_timer_get_time()/1000);
                gain_=story_sleep::gain(now,deadline_,fade_ms_);
                brookesia_board_story_dim(story_sleep::dim(gain_));
                if(now>=deadline_)sleep_due_=true;
            }
        }
        if(sleep_due_ && !live_) {
            if(local_audio::claim(local_audio::Audiobook)) {
                cancel_=false;live_=true;local_audio::audiobook_busy=true;
                if(xTaskCreatePinnedToCore([](void *ctx){static_cast<Audiobook *>(ctx)->run(true);vTaskDelete(nullptr);},
                    "story_goodnight",12288,this,4,nullptr,0)!=pdPASS) {
                    local_audio::release(local_audio::Audiobook);live_=false;
                    complete_sleep(sleep_id_);
                }
            } else complete_sleep(sleep_id_); // Never interrupt another audio owner.
        }
    }
private:
    std::mutex operation_,mutex_;
    std::atomic<bool> started_{false},sleep_due_{false};
    std::atomic<int> gain_{1000};
    uint64_t deadline_=0,fade_ms_=story_sleep::fade_ms;
    uint32_t sleep_id_=0,goodnight_count_=0;
    int sleep_minutes_=0;
    bool sleep_completed_=false,goodnight_played_=false;
    std::atomic<bool> announce_{false};
    std::atomic<unsigned> announcement_count_{0},last_announcement_{0};
    static constexpr const char *mode_names_[3]={"sequence","random","repeat_one"};
    std::atomic<unsigned> play_mode_{0};
    std::atomic<unsigned> speed_percent_{100};
    std::atomic<bool> mode_loaded_{false};
    std::mutex mode_mutex_;
    std::atomic<unsigned> song_mode_{0};
    std::atomic<bool> song_mode_loaded_{false};
    std::mutex song_mode_mutex_;
    FunctionResult mode_storage(const char *function,const boost::json::object &args){
        auto storage=ServiceManager::get_instance().get_service("Storage");
        return storage&&storage->is_running()?storage->call_function_sync(function,args,8000):FunctionResult{.success=false,.error_message="Storage unavailable"};
    }
    bool on_start() override {started_=true;return true;}
    void load_mode_once(){
        if(mode_loaded_)return;
        std::lock_guard lock(mode_mutex_);if(mode_loaded_)return;
        // Lifecycle can run on the setup task's PSRAM stack. Defer this until
        // the first command, and delegate Flash I/O to the storage service.
        auto result=mode_storage("FSReadText",{{"Path","/littlefs/audiobook-play-mode.json"}});
        if(result.success&&result.data&&std::holds_alternative<std::string>(*result.data)){
            boost::system::error_code ec;auto saved=boost::json::parse(std::get<std::string>(*result.data),ec);
            if(!ec && saved.is_object())if(auto *mode=saved.as_object().if_contains("mode");mode&&mode->is_string())
                for(unsigned i=0;i<3;++i)if(mode->as_string()==mode_names_[i])play_mode_=i;
        }
        mode_loaded_=true;
    }
    std::expected<void,std::string> set_play_mode(const std::string &mode){
        unsigned selected=3;for(unsigned i=0;i<3;++i)if(mode==mode_names_[i])selected=i;
        if(selected==3)return std::unexpected("Invalid playback mode");
        load_mode_once();
        std::lock_guard lock(mode_mutex_);if(play_mode_==selected)return {};
        const auto text=boost::json::serialize(boost::json::object{{"mode",mode}});
        auto result=mode_storage("FSWriteText",{{"Path","/littlefs/audiobook-play-mode.json"},{"Data",text}});
        if(!result.success)return std::unexpected(result.error_message);
        play_mode_=selected;return {};
    }
    void load_song_mode_once(){
        if(song_mode_loaded_)return;
        std::lock_guard lock(song_mode_mutex_);if(song_mode_loaded_)return;
        // Prefer the shared native preference; migrate the existing JS choice
        // without modifying its bookmark or any story preference.
        for(const char *path:{"/sdcard/apps/local.nurserysongs/data/play-mode.json","/sdcard/apps/local.nurserysongs/data/player.json"}){
            auto result=mode_storage("FSReadText",{{"Path",path}});
            if(!result.success||!result.data||!std::holds_alternative<std::string>(*result.data))continue;
            boost::system::error_code ec;auto saved=boost::json::parse(std::get<std::string>(*result.data),ec);
            if(ec||!saved.is_object())continue;
            if(auto *mode=saved.as_object().if_contains("mode");mode&&mode->is_string())
                for(unsigned i=0;i<3;++i)if(mode->as_string()==mode_names_[i]){song_mode_=i;song_mode_loaded_=true;return;}
        }
        song_mode_loaded_=true;
    }
    std::expected<void,std::string> set_song_mode(const std::string &mode){
        unsigned selected=3;for(unsigned i=0;i<3;++i)if(mode==mode_names_[i])selected=i;
        if(selected==3)return std::unexpected("Invalid song playback mode");
        struct stat st{};if(stat("/sdcard/apps/local.nurserysongs/manifest.json",&st)!=0)return std::unexpected("请插入安装了儿歌应用的 SD 卡");
        load_song_mode_once();std::lock_guard lock(song_mode_mutex_);
        if(song_mode_==selected)return {};
        auto made=mode_storage("FSMkdir",{{"Path","/sdcard/apps/local.nurserysongs/data"}});
        if(!made.success)return std::unexpected(made.error_message);
        auto result=mode_storage("FSWriteText",{{"Path","/sdcard/apps/local.nurserysongs/data/play-mode.json"},
            {"Data",boost::json::serialize(boost::json::object{{"mode",mode}})}});
        if(!result.success)return std::unexpected(result.error_message);
        song_mode_=selected;return {};
    }
    void reset_sleep() {
        std::lock_guard lock(mutex_);
        ++sleep_id_;deadline_=0;sleep_minutes_=0;sleep_completed_=false;
        sleep_due_=false;gain_=1000;local_audio::story_timer_busy=false;brookesia_board_story_dim(1000);
    }
    std::expected<void,std::string> set_sleep(double minutes,bool test=false) {
        if(!std::isfinite(minutes) || std::floor(minutes)!=minutes || minutes<0 || minutes>45 || (!test && !story_sleep::valid(int(minutes))))
            return std::unexpected("Use 0,15,30 or 45 minutes");
        std::lock_guard operation(operation_);
        if(sleep_due_ && minutes!=0)return std::unexpected("Goodnight is finishing; cancel first");
        reset_sleep();
        if(minutes) {
            std::lock_guard lock(mutex_);
            sleep_minutes_=test?0:int(minutes);fade_ms_=test?8000:story_sleep::fade_ms;
            deadline_=uint64_t(esp_timer_get_time()/1000)+(test?10000:uint64_t(minutes)*60000);
            goodnight_played_=false;local_audio::story_timer_busy=true;
        }
        return {};
    }
    void complete_sleep(uint32_t id) {
        std::lock_guard lock(mutex_);
        if(id!=sleep_id_ || !sleep_due_)return;
        deadline_=0;sleep_minutes_=0;sleep_due_=false;sleep_completed_=true;gain_=1000;local_audio::story_timer_busy=false;
        brookesia_board_story_sleep_done();
    }
    void say_goodnight(hal::InterfaceHandle<hal::audio::CodecPlayerIface> &codec,int16_t *pcm,uint32_t id) {
        if(cancel_ || brookesia_board_do_not_disturb() || !child_mode_audiobook_allowed())return;
        codec->close();
        if(!codec->open({.bits=16,.channels=2,.sample_rate=16000}))return;
        if(codec->is_pa_on_off_supported())codec->set_pa_on_off(true);
        state("Goodnight");
        const size_t total=std::size(goodnight_pcm);
        bool wrote=false;
        for(size_t at=0;at<total && !cancel_ && sleep_due_;at+=512) {
            if(brookesia_board_do_not_disturb() || !child_mode_audiobook_allowed())break;
            const size_t count=std::min<size_t>(512,total-at);
            for(size_t i=0;i<count;++i) {
                const int envelope=std::min<size_t>(640,std::min(at+i,total-at-i));
                pcm[2*i]=pcm[2*i+1]=int32_t(goodnight_pcm[at+i])*envelope/(640*4); // Gentle quarter-level speech.
            }
            if(!codec->write_data(reinterpret_cast<uint8_t *>(pcm),count*2*sizeof(int16_t)))break;
            wrote=true;vTaskDelay(1);
        }
        std::lock_guard lock(mutex_);
        if(wrote && id==sleep_id_){goodnight_played_=true;++goodnight_count_;}
    }
    void say_remaining(hal::InterfaceHandle<hal::audio::CodecPlayerIface> &codec,int16_t *pcm){
        if(cancel_ || brookesia_board_do_not_disturb() || !child_mode_audiobook_allowed())return;
        unsigned prompt=0;
        {std::lock_guard lock(mutex_);if(deadline_){const auto seconds=story_sleep::remaining(esp_timer_get_time()/1000,deadline_);prompt=seconds<60?46:std::min(45u,unsigned((seconds+59)/60));}}
        char path[96];snprintf(path,sizeof(path),"/sdcard/offline-voice/prompts/remaining-%02u.pcm",prompt);
        FILE *fp=fopen(path,"rb");if(!fp)return;
        bool wrote=false;
        codec->close();
        if(codec->open({.bits=16,.channels=2,.sample_rate=16000})){
            if(codec->is_pa_on_off_supported())codec->set_pa_on_off(true);
            size_t n;while(!cancel_ && !sleep_due_ && !brookesia_board_do_not_disturb() && child_mode_audiobook_allowed() && (n=fread(pcm,2,512,fp))>0){
                for(size_t i=n;i-->0;){const int16_t sample=pcm[i];pcm[2*i]=pcm[2*i+1]=sample;}
                if(!codec->write_data(reinterpret_cast<uint8_t *>(pcm),n*4))break;
                wrote=true;vTaskDelay(1);
            }
        }
        fclose(fp);if(wrote){++announcement_count_;last_announcement_=prompt;}
    }
    std::expected<void,std::string> voice_action(double command){
        if(!std::isfinite(command)||std::floor(command)!=command||command<1||command>8)return std::unexpected("Invalid command");
        const int id=int(command);
        if(id!=7 && !child_mode_audiobook_allowed())return std::unexpected("听书已被家长限制，或已到休息时间");
        if(id==2){paused_=true;state("Paused");return {};}
        if(id==7){std::lock_guard operation(operation_);reset_sleep();std::lock_guard lock(mutex_);deadline_=esp_timer_get_time()/1000;sleep_due_=true;local_audio::story_timer_busy=true;return {};}
        if(id==8){
            std::lock_guard operation(operation_);
            if(sleep_due_)return std::unexpected("Goodnight is finishing");
            if(live_){announce_=true;return {};}
            if(!local_audio::claim(local_audio::Audiobook))return std::unexpected("Audio busy");
            cancel_=false;live_=true;local_audio::audiobook_busy=true;
            if(xTaskCreatePinnedToCore([](void *ctx){static_cast<Audiobook *>(ctx)->run(false,true);vTaskDelete(nullptr);},"story_remaining",12288,this,4,nullptr,0)!=pdPASS){live_=false;local_audio::release(local_audio::Audiobook);return std::unexpected("Audio memory unavailable");}
            return {};
        }
        if(id==1||id==3||id==4){
            std::string current;bool ended=false;{std::lock_guard lock(mutex_);current=path_;ended=state_=="Ended";}
            if(live_ && id!=4 && !(id==1 && is_song(current))){paused_=false;state("Playing");return {};}
            if(id!=4 && permitted(current) && !(id==1 && is_song(current)))return play(current,ended?0:position_.load());
            // "Tell a story" always selects the story library. "Next" keeps
            // the active library, so offline next never crosses into stories.
            if(id==1 && is_song(current)) {current.clear();}
            std::vector<std::string> files;scan_library(id!=1 && is_song(current),files);
            if(files.empty())return std::unexpected("SD 卡中没有故事");
            auto next=std::find(files.begin(),files.end(),current);if(id==4 && next!=files.end() && ++next!=files.end())return play(*next,0);
            return play(files.front(),0);
        }
        return std::unexpected("Volume is handled by AudioPlayback");
    }
    std::string path_, state_="Idle", error_;
    std::atomic<bool> live_{false}, cancel_{false}, paused_{false};
    std::atomic<int32_t> seek_{-1};
    std::atomic<uint32_t> position_{0}, duration_{0}, bytes_{0};
    std::atomic<uint32_t> pcm_epoch_{0},starvations_{0},write_gap_us_{0},decode_max_us_{0};
    std::atomic<uint32_t> pcm_stack_free_{StoryPcmBuffer::stack_bytes};
    std::atomic<uint32_t> test_decode_delay_ms_{0};
    void state(const char *s, const char *error="") {
        local_audio::audiobook_busy=std::string_view(s)=="Loading" || std::string_view(s)=="Playing" || std::string_view(s)=="Goodnight";
        std::lock_guard<std::mutex> lock(mutex_); state_=s; error_=error;
    }
    std::expected<void,std::string> stop_worker() {
        cancel_=true;announce_=false;
        for (int i=0; live_ && i<500; ++i) vTaskDelay(pdMS_TO_TICKS(10));
        if (live_) return std::unexpected("Audio worker is still stopping");
        return {};
    }
    std::expected<void,std::string> stop() {
        std::lock_guard operation(operation_);reset_sleep();return stop_worker();
    }
    void on_stop() override {started_=false;stop();}
    std::expected<void,std::string> play(const std::string &path, double start) {
        std::lock_guard operation(operation_);
        if(sleep_due_)return std::unexpected("Goodnight is finishing; cancel the timer first");
        if(!child_mode_audiobook_allowed())return std::unexpected("听书已被家长限制，或已到休息时间");
        if (path!="@tone" && !permitted(path)) return std::unexpected("Only MP3/WAV under /sdcard/audiobooks is supported");
        if (!std::isfinite(start) || start<0 || start>86400) return std::unexpected("Invalid playback position");
        if (path!="@tone") {
            struct stat st{};
            if (stat(path.c_str(),&st)!=0 || !S_ISREG(st.st_mode)) return std::unexpected("Audio file is missing; check SD card");
        }
        auto stopped=stop_worker(); if(!stopped) return stopped;
        if(!local_audio::claim(local_audio::Audiobook))return std::unexpected("Voice assistant is using audio; close it first");
        local_audio::audiobook_busy=true;
        {std::lock_guard<std::mutex> lock(mutex_);path_=path;state_="Loading";error_.clear();sleep_completed_=false;}
        position_=0;duration_=0;bytes_=0;starvations_=0;write_gap_us_=0;decode_max_us_=0;++pcm_epoch_;cancel_=false;paused_=false;seek_=static_cast<int32_t>(start);live_=true;
        TaskHandle_t task=nullptr;
        if (xTaskCreatePinnedToCore([](void *ctx){static_cast<Audiobook *>(ctx)->run();vTaskDelete(nullptr);},
              "audiobook",12288,this,4,&task,0)!=pdPASS) {
            local_audio::release(local_audio::Audiobook);live_=false;state("Error","Not enough internal RAM for audio task");return std::unexpected("Audio task allocation failed");
        }
        return {};
    }
    boost::json::object snapshot() {
        load_mode_once();
        load_song_mode_once();
        std::lock_guard<std::mutex> lock(mutex_);
        return {{"state",state_},{"path",path_},{"title",story_titles::title(path_)},{"error",error_},{"position",position_.load()},
                {"play_mode",mode_names_[play_mode_.load()]},{"song_play_mode",mode_names_[song_mode_.load()]},{"speed",speed_percent_.load()/100.0},
                {"duration",duration_.load()},{"bytes_written",bytes_.load()},{"active",live_.load()},
                {"pcm_buffer_bytes",StoryPcmBuffer::capacity},{"pcm_starvations",starvations_.load()},{"write_gap_max_us",write_gap_us_.load()},{"decode_max_us",decode_max_us_.load()},{"pcm_stack_free_min_bytes",pcm_stack_free_.load()},{"test_decode_delay_ms",test_decode_delay_ms_.load()},
                {"sleep_minutes",sleep_minutes_},{"sleep_remaining_seconds",story_sleep::remaining(esp_timer_get_time()/1000,deadline_)},
                {"sleep_active",deadline_!=0},{"sleep_fading",deadline_!=0 && gain_<1000},
                {"sleep_finishing",sleep_due_.load()},{"sleep_completed",sleep_completed_},
                {"sleep_gain_per_mille",gain_.load()},{"goodnight_played",goodnight_played_},{"goodnight_count",goodnight_count_},{"announcement_count",announcement_count_.load()},{"last_announcement",last_announcement_.load()}};
    }
    std::expected<boost::json::object,std::string> list(bool songs=false) {
        struct stat st{};
        const bool mounted=stat("/sdcard",&st)==0 && S_ISDIR(st.st_mode);
        std::vector<std::string> paths;
        if(mounted) scan_library(songs,paths);
        boost::json::array entries;
        for(const auto &p:paths) entries.push_back(boost::json::object{{"path",p},{"title",story_titles::title(p)}});
        return boost::json::object{{"mounted",mounted},{"tracks",std::move(entries)},{"limit",512}};
    }
    std::vector<FunctionSchema> get_function_schemas() override {
        return {
            {"List","List local chapters",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Card and tracks"}},
            {"ListSongs","List the separate nursery song library",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Card and tracks"}},
            {"Play","Play local chapter",{{"Path","Local file",FunctionValueType::String},{"Position","Seconds",FunctionValueType::Number,0.0}}},
            {"Pause","Pause",{}},{"Resume","Resume",{}},{"Stop","Stop",{}},
            {"Seek","Seek in current chapter",{{"Seconds","Seconds",FunctionValueType::Number}}},
            {"GetState","Get player state",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Playback state"}},
            {"TestTone","Play a two second quiet test tone",{}},
            {"SetSleepTimer","Set a wall-clock story timer; 0 cancels",{{"Minutes","0,15,30,45",FunctionValueType::Number}}},
            {"TestSleepTimer","Ten second diagnostic with eight second fade",{}},
            {"VoiceAction","Local story command routing",{{"Command","1..8",FunctionValueType::Number}}},
            {"TestDecodeDelay","Temporary decoder stall every 32 chunks; 0 disables",{{"Milliseconds","0..200",FunctionValueType::Number}}},
            {"SetSpeed","Set speech speed (0.5,0.75,1,1.25,1.5,2)",{{"Speed","Playback multiplier",FunctionValueType::Number}}},
            {"SetPlayMode","Set and persist a shared playback mode",{{"Mode","sequence/random/repeat_one",FunctionValueType::String}}},
            {"SetSongMode","Set the independent shared nursery-song mode",{{"Mode","sequence/random/repeat_one",FunctionValueType::String}}}
        };
    }
    FunctionHandlerList get_function_handlers() override {
        return {
            BROOKESIA_SERVICE_FUNC_HANDLER_0("List",list()),
            BROOKESIA_SERVICE_FUNC_HANDLER_0("ListSongs",list(true)),
            BROOKESIA_SERVICE_FUNC_HANDLER_2("Play","Path",std::string,"Position",double,play(PARAM1,PARAM2)),
            {"Pause",[this](FunctionParameterMap &&)->FunctionResult{if(!live_)return {.success=false,.error_message="Nothing is playing"};paused_=true;state("Paused");return {.success=true};}},
            {"Resume",[this](FunctionParameterMap &&)->FunctionResult{if(!live_)return {.success=false,.error_message="Nothing to resume"};paused_=false;state("Playing");return {.success=true};}},
            BROOKESIA_SERVICE_FUNC_HANDLER_0("Stop",stop()),
            {"Seek",[this](FunctionParameterMap &&args)->FunctionResult{
                const double seconds=std::get<double>(args.at("Seconds"));
                if(!live_ || !std::isfinite(seconds) || seconds<0 || seconds>86400) return {.success=false,.error_message="Invalid seek"};
                seek_=static_cast<int32_t>(seconds);return {.success=true};}},
            {"GetState",[this](FunctionParameterMap &&)->FunctionResult{return {.success=true,.data=FunctionValue(snapshot())};}},
            BROOKESIA_SERVICE_FUNC_HANDLER_0("TestTone",play("@tone",0)),
            BROOKESIA_SERVICE_FUNC_HANDLER_1("SetSleepTimer","Minutes",double,set_sleep(PARAM)),
            BROOKESIA_SERVICE_FUNC_HANDLER_0("TestSleepTimer",set_sleep(1,true)),
            BROOKESIA_SERVICE_FUNC_HANDLER_1("VoiceAction","Command",double,voice_action(PARAM)),
            {"TestDecodeDelay",[this](FunctionParameterMap &&args)->FunctionResult{
                const double ms=std::get<double>(args.at("Milliseconds"));
                if(!std::isfinite(ms)||ms<0||ms>200||std::floor(ms)!=ms)return {.success=false,.error_message="Use an integer from 0 to 200"};
                test_decode_delay_ms_=uint32_t(ms);return {.success=true};}},
            {"SetSpeed",[this](FunctionParameterMap &&args)->FunctionResult{
                const double speed=std::get<double>(args.at("Speed"));
                if(!std::isfinite(speed)||(speed!=.5&&speed!=.75&&speed!=1&&speed!=1.25&&speed!=1.5&&speed!=2))return {.success=false,.error_message="Unsupported playback speed"};
                speed_percent_=unsigned(speed*100);return {.success=true};}},
            BROOKESIA_SERVICE_FUNC_HANDLER_1("SetPlayMode","Mode",std::string,set_play_mode(PARAM)),
            BROOKESIA_SERVICE_FUNC_HANDLER_1("SetSongMode","Mode",std::string,set_song_mode(PARAM))
        };
    }
    void run(bool goodnight_only=false,bool feedback_only=false) {
        auto codecs=hal::acquire_interfaces<hal::audio::CodecPlayerIface>();
        auto codec=codecs.empty()?hal::InterfaceHandle<hal::audio::CodecPlayerIface>{}:std::move(codecs.front());
        auto *mp3=static_cast<drmp3 *>(audio_malloc(sizeof(drmp3),nullptr));
        auto *wav=static_cast<drwav *>(audio_malloc(sizeof(drwav),nullptr));
        auto *pcm=static_cast<int16_t *>(audio_malloc(1024*2*sizeof(int16_t),nullptr));
        auto *output=static_cast<int16_t *>(audio_malloc(4096*sizeof(int16_t),nullptr));
        bool mp3open=false,wavopen=false,opened=false,failed=false,eof=false;
        std::unique_ptr<StoryPcmBuffer> buffered;
        std::unique_ptr<sonicStreamStruct,decltype(&sonicDestroyStream)> stretch(nullptr,&sonicDestroyStream);
        auto start_buffer=[&](){
            buffered=std::make_unique<StoryPcmBuffer>([&](const uint8_t *data,size_t size,uint32_t position,uint32_t epoch){
                if(!codec->write_data(data,size))return false;
                pcm_stack_free_=std::min(pcm_stack_free_.load(),uint32_t(uxTaskGetStackHighWaterMark(nullptr)));
                bytes_+=size;if(position!=UINT32_MAX && epoch==pcm_epoch_)position_=position;
                return true;
            },paused_,pcm_epoch_,starvations_,write_gap_us_,[&](){return cancel_ || sleep_due_;});
            return buffered->start();
        };
        bool finish_sleep=goodnight_only;uint32_t finish_id=0;
        {std::lock_guard lock(mutex_);finish_id=sleep_id_;}
        std::string path;{std::lock_guard<std::mutex> lock(mutex_);path=path_;}
        const bool tone=path=="@tone";
        uint32_t rate=16000,channels=1;uint64_t frames=0,total=32000;
        const drmp3_allocation_callbacks mp3alloc{nullptr,audio_malloc,audio_realloc,audio_free};
        const drwav_allocation_callbacks wavalloc{nullptr,audio_malloc,audio_realloc,audio_free};
        auto fail=[&](const char *message){state("Error",message);failed=true;};
        do {
            if(!codec || !pcm || !output || !mp3 || !wav){fail("Audio memory or codec unavailable");break;}
            if(goodnight_only)break;
            if(feedback_only){say_remaining(codec,pcm);opened=true;break;}
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
            if(!codec->open({.bits=16,.channels=2,.sample_rate=16000})) {fail("Failed to open speaker codec");break;}
            opened=true;
            if(codec->is_pa_on_off_supported())codec->set_pa_on_off(true);
            if(!start_buffer()){fail("PCM buffer/task unavailable");break;}
            stretch.reset(sonicCreateStream(16000,1));
            if(!stretch){fail("Speech speed buffer unavailable");break;}
            state("Playing");
            auto emit=[&](){
                int n;while((n=sonicReadShortFromStream(stretch.get(),pcm,1024))>0){
                    for(int i=0;i<n;++i)output[2*i]=output[2*i+1]=pcm[i];
                    if(!buffered->send(output,n*4,frames/rate,[&](){return cancel_ || sleep_due_ || seek_.load()>=0;}))return false;
                }return true;
            };
            uint64_t resample_phase=0;
            unsigned decode_chunks=0;
            while(!cancel_) {
                if(sleep_due_){finish_sleep=true;{std::lock_guard lock(mutex_);finish_id=sleep_id_;}break;}
                if(announce_.exchange(false)){
                    const bool was_paused=paused_.load();
                    buffered->finish(!was_paused);buffered.reset();
                    // A paused prompt must not drain audible story data. Resume
                    // its decoder at the last submitted (whole-second) position.
                    if(was_paused)seek_=position_.load();
                    else vTaskDelay(pdMS_TO_TICKS(60));
                    say_remaining(codec,pcm);
                    if(!start_buffer()){fail("PCM buffer/task unavailable");break;}
                }
                if(!child_mode_audiobook_allowed())break;
                int32_t requested=seek_.exchange(-1);
                if(requested>=0){
                    ++pcm_epoch_;
                    stretch.reset(sonicCreateStream(16000,1));
                    if(!stretch){fail("Speech speed buffer unavailable");break;}
                    uint64_t target=static_cast<uint64_t>(requested)*rate;
                    if(total)target=std::min(target,total);
                    bool ok=tone || (mp3open?drmp3_seek_to_pcm_frame(mp3,target):drwav_seek_to_pcm_frame(wav,target));
                    if(!ok){fail("Failed to seek audio");break;}frames=target;position_=frames/rate;resample_phase=0;
                }
                if(paused_){vTaskDelay(pdMS_TO_TICKS(20));continue;}
                size_t count;
                if(tone){
                    count=static_cast<size_t>(std::min<uint64_t>(1024,total-frames));
                    for(size_t i=0;i<count;++i)pcm[i]=static_cast<int16_t>(1000*std::sin(2*3.14159265*440*(frames+i)/rate));
                }else {
                    const auto began=esp_timer_get_time();
                    if(++decode_chunks%32==0 && test_decode_delay_ms_)vTaskDelay(pdMS_TO_TICKS(test_decode_delay_ms_.load()));
                    count=mp3open?drmp3_read_pcm_frames_s16(mp3,1024,pcm):drwav_read_pcm_frames_s16(wav,1024,pcm);
                    decode_max_us_=std::max(decode_max_us_.load(),uint32_t(esp_timer_get_time()-began));
                }
                if(!count){
                    if(!sonicFlushStream(stretch.get()) || !emit()){if(!cancel_&&!sleep_due_&&seek_.load()<0)fail("Speech output failed");}
                    else eof=true;
                    if(seek_.load()>=0)continue;
                    break;
                }
                // Duplicated stereo keeps 32-bit RX slots compatible with the shared 16 kHz TX clock.
                size_t written=0;const int gain=gain_.load()*(local_audio::offline_duck?250:1000)/1000;
                for(;resample_phase<count*16000;resample_phase+=rate){
                    const size_t at=resample_phase/16000,next=std::min<size_t>(at+1,count-1);const int fraction=resample_phase%16000;
                    int a=0,b=0;for(unsigned ch=0;ch<channels;++ch){a+=pcm[at*channels+ch];b+=pcm[next*channels+ch];}
                    const int sample=(int64_t(a)*(16000-fraction)+int64_t(b)*fraction)/(16000*channels);
                    output[written++]=int32_t(sample)*gain/1000;
                }
                resample_phase-=count*16000;
                frames+=count;
                sonicSetSpeed(stretch.get(),tone?1.0f:speed_percent_.load()/100.0f);
                if(!sonicWriteShortToStream(stretch.get(),output,written) || !emit()){
                    if(seek_.load()<0 && !cancel_ && !sleep_due_){fail("Speech output failed");break;}
                    if(cancel_ || sleep_due_)break;
                }
            }
        }while(false);
        if(buffered){buffered->finish(eof && !cancel_ && !sleep_due_ && !failed);if(buffered->failed()&&!failed)fail("Speaker write failed");buffered.reset();if(eof&&!cancel_&&!sleep_due_)vTaskDelay(pdMS_TO_TICKS(60));}
        if(finish_sleep && codec && pcm && !failed) {say_goodnight(codec,pcm,finish_id);opened=true;}
        if(opened){
            if(codec->is_pa_on_off_supported())codec->set_pa_on_off(false);
            codec->close();
        }
        if(mp3open)drmp3_uninit(mp3);
        if(wavopen)drwav_uninit(wav);
        audio_free(mp3,nullptr);audio_free(wav,nullptr);audio_free(pcm,nullptr);audio_free(output,nullptr);
        if(finish_sleep)complete_sleep(finish_id);
        if(!failed)state(finish_sleep?"SleepEnded":eof?"Ended":"Stopped");
        codec.reset();local_audio::release(local_audio::Audiobook);live_=false;
    }
};
std::weak_ptr<Audiobook> book_instance;
}
void audiobook_sleep_poll(){if(auto book=book_instance.lock())book->poll_sleep();}
std::shared_ptr<ServiceBase> make_audiobook_service(){auto book=std::make_shared<Audiobook>();book_instance=book;return book;}
