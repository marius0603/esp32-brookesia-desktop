#include "offline_voice.hpp"
#include "commands.hpp"
#include "model_manifest.hpp"
#include "../audio_ownership.hpp"
#include "../child_mode/child_mode.hpp"
#include "../device_modes/device_modes.hpp"
#include "brookesia/hal_interface.hpp"
#include "brookesia/service_manager/service/manager.hpp"
#include "esp_afe_sr_models.h"
#include "esp_mn_models.h"
#include "esp_mn_speech_commands.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "esp_lv_adapter.h"
#include "lvgl.h"
#include "src/misc/cache/instance/lv_image_cache.h"
#include "mbedtls/md.h"
#include "freertos/idf_additions.h"
#include <atomic>
#include <mutex>
#include <cstdio>
#include <cstring>
#include <algorithm>
#include <sys/stat.h>
using namespace esp_brookesia;
using namespace esp_brookesia::service;
namespace {
constexpr const char *ROOT="/sdcard/offline-voice/models";
std::atomic<bool> mic_in_use{false};
std::atomic<TaskHandle_t> sr_worker{nullptr},sr_feeder{nullptr};
std::atomic<int64_t> online_hold_until{0};
int64_t now_ms(){return esp_timer_get_time()/1000;}
FunctionResult invoke(const char *name,const char *fn,const boost::json::object &args={}){
 auto s=ServiceManager::get_instance().get_service(name);
 return s && s->is_running()?s->call_function_sync(fn,args,8000):FunctionResult{.success=false,.error_message="Service unavailable"};
}
class OfflineVoice final:public ServiceBase {
public:
 OfflineVoice():ServiceBase({.name="OfflineVoice",.description="Local WakeNet and MultiNet commands; no audio upload",.version="0.1.0",.dependencies={"Audiobook","AudioPlayback","DeviceModes"}}){}
private:
 std::atomic<bool> live_{false},stop_{false},active_{false},listening_{false};
 std::atomic<uint32_t> frames_{0},wakes_{0},recognized_{0},rejected_{0},stack_free_{16384};
 std::atomic<int> last_id_{0};std::atomic<float> last_score_{0};
 std::atomic<bool> feed_run_{false},feed_live_{false},diagnostic_begin_{false};
 std::atomic<bool> manual_listen_{false};
 std::atomic<int> pending_action_{0};
 std::atomic<uint32_t> fetched_{0},mic_peak_{0};std::atomic<int> afe_result_{-99},feed_result_{0};
 std::atomic<uint32_t> feed_stack_free_{8192};
 std::atomic<int> diagnostic_{0};std::atomic<bool> diagnostic_active_{false};
 std::mutex mutex_;std::string status_="关闭",error_,last_action_;
 const esp_afe_sr_iface_t *afe_=nullptr;esp_afe_sr_data_t *afe_data_=nullptr;
 esp_mn_iface_t *mn_=nullptr;model_iface_data_t *mn_data_=nullptr;srmodel_list_t *models_=nullptr;
 hal::InterfaceHandle<hal::audio::CodecRecorderIface> recorder_;
 uint8_t *raw_=nullptr;int16_t *feed_=nullptr;int chunk_=0,raw_bytes_=0,recorder_bits_=0;
 std::atomic<bool> cache_limited_{false};std::atomic<uint32_t> cache_reclaimed_{0},model_psram_min_{UINT32_MAX};
 bool limit_image_cache(){
  if(esp_lv_adapter_lock(500)!=ESP_OK){status("屏幕忙，请再试一次");return false;}
  const auto before=heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
  // Resize without reserve's eviction loop, then drop idle decoded entries.
  // Disable caching during the window: a nonzero tiny cache rejects oversized
  // images in LVGL 9. View objects/framebuffer remain; decoder buffers are transient.
  lv_image_cache_resize(0,false);lv_image_cache_drop(nullptr);cache_limited_=true;
  const auto after=heap_caps_get_free_size(MALLOC_CAP_SPIRAM);cache_reclaimed_=after>before?after-before:0;
  esp_lv_adapter_unlock();return true;
 }
 void restore_image_cache(){
  if(!cache_limited_)return;
  if(esp_lv_adapter_lock(1000)!=ESP_OK)return;
  lv_image_cache_resize(CONFIG_LV_CACHE_DEF_SIZE,false);cache_limited_=false;esp_lv_adapter_unlock();
 }
 bool commands_allocated_=false;std::atomic<bool> command_loaded_{false};std::atomic<int64_t> model_load_ms_{0};
 void close_commands(){
  if(commands_allocated_)esp_mn_commands_free();
  commands_allocated_=false;
  if(mn_data_)mn_->destroy(mn_data_);
  mn_data_=nullptr;command_loaded_=false;restore_image_cache();
 }
 bool open_commands(){
  if(mn_data_)return true;
  if(!limit_image_cache())return false;
  if(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)<2500000 || heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT)<40000){restore_image_cache();status("请先关闭其他应用","没有足够内存打开命令识别");return false;}
  status("准备命令识别");const auto began=now_ms();
  char *name=esp_srmodel_filter(models_,ESP_MN_PREFIX,ESP_MN_CHINESE);
  if(!(mn_data_=mn_->create(name,10000))){close_commands();status("命令模型初始化失败");return false;}
  if(esp_mn_commands_alloc(mn_,mn_data_)!=ESP_OK){close_commands();status("命令表初始化失败");return false;}
  commands_allocated_=true;
  for(const auto &p:offline_commands::phrases)if(esp_mn_commands_add(p.id,p.pinyin)!=ESP_OK){close_commands();status("命令词格式错误");return false;}
  if(auto errors=esp_mn_commands_update();errors && errors->num){close_commands();status("命令词加载失败");return false;}
  if(afe_->get_fetch_chunksize(afe_data_)!=mn_->get_samp_chunksize(mn_data_)){close_commands();status("音频帧不兼容");return false;}
  mn_->set_det_threshold(mn_data_,0.40f);command_loaded_=true;model_psram_min_=std::min(model_psram_min_.load(),uint32_t(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)));model_load_ms_=now_ms()-began;return true;
 }
 void status(const char *text,const char *error=""){std::lock_guard lock(mutex_);status_=text;error_=error;}
 bool permitted(){return !stop_ && brookesia_board_offline_voice_enabled() && !local_audio::sleeping &&
     local_audio::owner!=local_audio::Assistant && now_ms()>=online_hold_until;}
 bool verify_models(){
  auto *buf=static_cast<uint8_t *>(heap_caps_malloc(4096,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
  if(!buf)return false;
  bool okay=true;
  for(const auto &file:offline_model_files){
   const std::string path=std::string(ROOT)+"/"+file.path;struct stat st{};
   if(stat(path.c_str(),&st) || st.st_size!=file.bytes){okay=false;break;}
   FILE *fp=fopen(path.c_str(),"rb");if(!fp){okay=false;break;}
   mbedtls_md_context_t sha;mbedtls_md_init(&sha);
   if(mbedtls_md_setup(&sha,mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),0)!=0 || mbedtls_md_starts(&sha)!=0){fclose(fp);okay=false;mbedtls_md_free(&sha);break;}
   size_t n;while((n=fread(buf,1,4096,fp))>0)mbedtls_md_update(&sha,buf,n);
   if(ferror(fp))okay=false;
   fclose(fp);unsigned char digest[32];mbedtls_md_finish(&sha,digest);mbedtls_md_free(&sha);
   char hex[65];for(int i=0;i<32;++i)snprintf(hex+2*i,3,"%02x",digest[i]);
   if(std::strcmp(hex,file.sha256)!=0)okay=false;
   if(!okay || !permitted())break;
  }
  heap_caps_free(buf);return okay && permitted();
 }
 bool prepare(){
  mic_in_use=true;status("检查本地模型");if(!verify_models()){status("模型未就绪","请检查 SD 离线语音资源或开关状态");return false;}
  // Preserve enough internal heap for I2S, USB, GUI and task synchronization.
  if(heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT)<50000 || heap_caps_get_free_size(MALLOC_CAP_SPIRAM)<900000){status("内存不足","请关闭其他应用后重试");return false;}
  status("加载离线模型");models_=esp_srmodel_init(ROOT);
  if(!models_ || models_->num!=2){status("模型错误");return false;}
  char *name=esp_srmodel_filter(models_,ESP_MN_PREFIX,ESP_MN_CHINESE);mn_=name?esp_mn_handle_from_name(name):nullptr;
  if(!mn_){status("命令模型未找到");return false;}
  auto *cfg=afe_config_init("MR",models_,AFE_TYPE_SR,AFE_MODE_LOW_COST);
  if(!cfg){status("前端配置失败");return false;}
  cfg->memory_alloc_mode=AFE_MEMORY_ALLOC_MORE_PSRAM;cfg->se_init=false;
  cfg->aec_init=true;cfg->aec_mode=AEC_MODE_SR_LOW_COST;
  cfg->vad_mode=VAD_MODE_2;cfg->vad_min_noise_ms=800;cfg->vad_min_speech_ms=128;
  cfg->agc_init=true;cfg->agc_compression_gain_db=6;
  // Keep more than the 800 ms VAD history: an eight-frame ring fills
  // with retained history and can no longer accept new frames.
  cfg->afe_ringbuf_size=80;
  cfg->afe_perferred_core=0;cfg->afe_perferred_priority=4;
  afe_=esp_afe_handle_from_config(cfg);afe_data_=afe_?afe_->create_from_config(cfg):nullptr;afe_config_free(cfg);
  if(!afe_data_){status("语音前端初始化失败");return false;}
  chunk_=afe_->get_feed_chunksize(afe_data_);
  if(chunk_<=0 || chunk_>2048 || afe_->get_fetch_chunksize(afe_data_)>2048){status("音频帧不兼容");return false;}
  if(!recorder_){status("麦克风不可用","请重启设备以恢复音频驱动");return false;}
  const auto &info=recorder_->get_info();
  if(info.sample_rate!=16000 || info.channels!=2 || (info.bits!=16 && info.bits!=32) || info.mic_layout.find('M')!=1){status("麦克风格式不兼容");return false;}
  recorder_bits_=info.bits;raw_bytes_=chunk_*2*(info.bits/8);
  raw_=static_cast<uint8_t *>(heap_caps_malloc(raw_bytes_,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
  feed_=static_cast<int16_t *>(heap_caps_malloc(chunk_*4,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
  if(!raw_ || !feed_ || !permitted() || !recorder_->open()){status("麦克风打开失败");return false;}
  mic_in_use=true;active_=true;status("离线待唤醒 · 你好小智");return true;
 }
 void cleanup(){
  stop_feed();active_=false;listening_=false;local_audio::offline_duck=false;
  if(recorder_)recorder_->close();
  if(afe_data_)afe_->destroy(afe_data_);
  afe_data_=nullptr;afe_=nullptr;
  close_commands();mn_=nullptr;
  if(models_)esp_srmodel_deinit(models_);
  models_=nullptr;
  heap_caps_free(raw_);raw_=nullptr;heap_caps_free(feed_);feed_=nullptr;
  mic_in_use=false;
 }
 FunctionResult execute(int id){
  if(!brookesia_board_offline_voice_enabled() || local_audio::sleeping || local_audio::owner==local_audio::Assistant)
   return {.success=false,.error_message="Offline voice is unavailable"};
  if(id<1 || id>8)return {.success=false,.error_message="Invalid command"};
  if(id==5 || id==6){
   if(brookesia_board_do_not_disturb() || !child_mode_audiobook_allowed())return {.success=false,.error_message="家长限制或勿扰时段"};
   auto value=invoke("AudioPlayback","GetVolume");if(!value.success || !value.data)return value;
   const double volume=std::holds_alternative<double>(*value.data)?std::get<double>(*value.data):0;
   return invoke("AudioPlayback","SetVolume",{{"Volume",std::clamp(volume+(id==5?10:-10),0.0,100.0)}});
  }
  if(id!=7)invoke("DeviceModes","Wake");
  if(id==1 || id==3 || id==4){
   auto apps=invoke("SystemCore","ListApps");
   if(apps.success && apps.data)for(const auto &app:std::get<boost::json::array>(*apps.data)){
    const auto &a=app.as_object();if(a.at("manifest").as_object().at("id").as_string()=="local.audiobook"){
     auto result=invoke("SystemCore","StartApp",{{"AppId",a.at("app_id")}});if(!result.success)return result;break;
    }
   }
  }
  return invoke("Audiobook","VoiceAction",{{"Command",id}});
 }
 void feed_audio(){
  sr_feeder=xTaskGetCurrentTaskHandle();FILE *fixture=nullptr;
  while(feed_run_ && permitted()){
   if(!recorder_->read_data(raw_,raw_bytes_)){status("麦克风读取失败");break;}
   const auto *input=reinterpret_cast<const int16_t *>(raw_);
   for(int i=0;i<chunk_;++i){feed_[2*i]=recorder_bits_==32?reinterpret_cast<const int32_t *>(raw_)[2*i+1]>>16:input[2*i+1];feed_[2*i+1]=recorder_bits_==32?reinterpret_cast<const int32_t *>(raw_)[2*i]>>16:input[2*i];}
   unsigned peak=0;for(int i=0;i<chunk_;++i)peak=std::max(peak,unsigned(std::abs(int(feed_[2*i]))));mic_peak_=peak;
   if(const int test=diagnostic_.exchange(0);test>0 && !fixture){
    char path[96];snprintf(path,sizeof(path),"/sdcard/offline-voice/diagnostic/test-%02d.pcm",test);fixture=fopen(path,"rb");
    diagnostic_active_=fixture!=nullptr;diagnostic_begin_=fixture!=nullptr;
   }
   if(fixture){
    const size_t samples=fread(raw_,2,chunk_,fixture);auto *pcm=reinterpret_cast<int16_t *>(raw_);
    for(int i=0;i<chunk_;++i){feed_[2*i]=i<int(samples)?pcm[i]:0;feed_[2*i+1]=0;}
    if(samples<size_t(chunk_)){fclose(fixture);fixture=nullptr;diagnostic_active_=false;}
   }
   const int written=afe_->feed(afe_data_,feed_);feed_result_=written;
   if(written<0)break;
   feed_stack_free_=std::min(feed_stack_free_.load(),uint32_t(uxTaskGetStackHighWaterMark(nullptr)));
   ++frames_;vTaskDelay(1);
  }
  if(fixture)fclose(fixture);
  diagnostic_active_=false;sr_feeder=nullptr;feed_live_=false;
 }
 void stop_feed(){
  feed_run_=false;
  while(feed_live_){
   // Drain results so a feeder waiting on a full AFE ring can exit cooperatively.
   if(afe_data_)afe_->fetch_with_delay(afe_data_,pdMS_TO_TICKS(20));
   vTaskDelay(1);
  }
 }
 void listen(){
  feed_run_=true;feed_live_=true;
  if(xTaskCreatePinnedToCoreWithCaps([](void *p){static_cast<OfflineVoice *>(p)->feed_audio();vTaskDeleteWithCaps(nullptr);},"offline_feed",8192,this,5,nullptr,1,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT)!=pdPASS){feed_live_=false;status("采集任务内存不足");return;}
  int64_t deadline=0,cooldown=0;
  while(permitted() && feed_live_){
   if(!mn_data_)restore_image_cache();
   else model_psram_min_=std::min(model_psram_min_.load(),uint32_t(heap_caps_get_free_size(MALLOC_CAP_SPIRAM)));
   if(const int action=pending_action_.exchange(0);action>0){
    auto result=execute(action);std::lock_guard lock(mutex_);last_action_=offline_commands::names[action];error_=result.success?"":result.error_message;
   }
   auto *result=afe_->fetch_with_delay(afe_data_,pdMS_TO_TICKS(100));
   if(result)afe_result_=result->ret_value;
   if(diagnostic_begin_.exchange(false)){
    // Do not reset AFE rings while the producer is feeding them. Silence in
    // the fixture separates utterances just as it does for the microphone.
    cooldown=0;listening_=false;local_audio::offline_duck=false;close_commands();afe_->enable_wakenet(afe_data_);
   }
   if(!result || result->ret_value==ESP_FAIL || !result->data || result->data_size<afe_->get_fetch_chunksize(afe_data_)*2){vTaskDelay(1);continue;}
   ++fetched_;
   const auto now=now_ms();const bool manual=manual_listen_.exchange(false);
   // One-mic AFE may report DETECTED without a separate VERIFIED event.
   if(!listening_ && (manual || (now>=cooldown && (result->wakeup_state==WAKENET_DETECTED || result->wakeup_state==WAKENET_CHANNEL_VERIFIED)))){
    ++wakes_;local_audio::offline_duck=true;afe_->disable_wakenet(afe_data_);
    if(!open_commands()){local_audio::offline_duck=false;afe_->enable_wakenet(afe_data_);cooldown=now_ms()+2500;continue;}
    listening_=true;deadline=now_ms()+12000;mn_->clean(mn_data_);status("请说命令");invoke("DeviceModes","Wake");
    continue; // The verification frame can still contain the end of the wake word.
   }
   if(listening_){
    // MultiNet consumes the continuous AFE stream. VAD onset cache is only
    // needed for VAD-gated uploads; concatenating it here duplicates past audio.
    // AFE and MultiNet frame sizes were checked at creation. Pass the AFE's
    // library-owned aligned frame directly, as in the ESP-BOX SR example.
    if(result->data_size!=mn_->get_samp_chunksize(mn_data_)*int(sizeof(int16_t))){
     listening_=false;local_audio::offline_duck=false;close_commands();
     afe_->enable_wakenet(afe_data_);status("音频帧不兼容");continue;
    }
    const auto state=mn_->detect(mn_data_,result->data);
    if(state==ESP_MN_STATE_DETECTED){
     auto *r=mn_->get_results(mn_data_);int id=r && r->num?r->command_id[0]:0;
     const float score=r && r->num?r->prob[0]:0;int runner=0;float other=0;
     if(r)for(int i=1;i<r->num;++i)if(r->command_id[i]!=id){runner=r->command_id[i];other=r->prob[i];break;}
     last_id_=id;last_score_=score;
     if(offline_commands::accept(id,score,runner,other)){
      ++recognized_;listening_=false;local_audio::offline_duck=false;close_commands();
      auto action=execute(id);{std::lock_guard lock(mutex_);last_action_=offline_commands::names[id];error_=action.success?"":action.error_message;}
      cooldown=now_ms()+2500;afe_->enable_wakenet(afe_data_);status("离线待唤醒 · 你好小智",action.success?"":action.error_message.c_str());
     }else{++rejected_;mn_->clean(mn_data_);status("没听清，请再说一次");}
    }
    if(listening_ && (now>=deadline || state==ESP_MN_STATE_TIMEOUT)){
     listening_=false;local_audio::offline_duck=false;close_commands();status("离线待唤醒 · 你好小智");afe_->enable_wakenet(afe_data_);cooldown=now+500;
    }
   }
   stack_free_=std::min(stack_free_.load(),uint32_t(uxTaskGetStackHighWaterMark(nullptr)));vTaskDelay(1);
  }
  stop_feed();
 }
 void run(){
  sr_worker=xTaskGetCurrentTaskHandle();
  // Hold the HAL interface for the service lifetime, while closing capture on
  // disable. Recreating the shared full-duplex provider can orphan its I2S peer.
  auto recorders=hal::acquire_interfaces<hal::audio::CodecRecorderIface>();
  if(!recorders.empty())recorder_=std::move(recorders.front());
  recorders.clear();
  // Allow native desktop preloads to finish before reserving recognition memory.
  const auto startup=now_ms()+12000;
  while(!stop_ && now_ms()<startup)vTaskDelay(pdMS_TO_TICKS(100));
  while(!stop_){
   if(permitted()){if(prepare())listen();cleanup();}
   else status(brookesia_board_offline_voice_enabled()?"麦克风已让给在线助手或睡眠":"关闭 · 麦克风已释放");
   for(int i=0;i<20&&!stop_;++i)vTaskDelay(pdMS_TO_TICKS(100));
  }
  cleanup();recorder_.reset();sr_worker=nullptr;live_=false;
 }
 bool on_start() override{
  stop_=false;live_=true;
  if(xTaskCreatePinnedToCoreWithCaps([](void *p){static_cast<OfflineVoice *>(p)->run();vTaskDeleteWithCaps(nullptr);},"offline_voice",16384,this,4,nullptr,0,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT)!=pdPASS){live_=false;return false;}
  return true;
 }
 void on_stop() override{stop_=true;while(live_)vTaskDelay(pdMS_TO_TICKS(20));}
 boost::json::object snapshot(){std::lock_guard lock(mutex_);return {
  {"enabled",brookesia_board_offline_voice_enabled()},{"active",active_.load()},{"microphone_open",mic_in_use.load()},
  {"image_cache_limited",cache_limited_.load()},{"image_cache_limit_bytes",cache_limited_?0:CONFIG_LV_CACHE_DEF_SIZE},{"cache_reclaimed_bytes",cache_reclaimed_.load()},{"psram_model_min_bytes",model_psram_min_==UINT32_MAX?0:model_psram_min_.load()},{"command_model_loaded",command_loaded_.load()},{"model_load_ms",model_load_ms_.load()},{"listening",listening_.load()},{"wake_word","你好小智"},{"network_audio_upload",false},
  {"diagnostic_in_progress",diagnostic_active_.load() || diagnostic_.load()!=0},
  {"status",status_},{"error",error_},{"last_action",last_action_},{"last_command",last_id_.load()},{"last_score",last_score_.load()},
  {"frames",frames_.load()},{"fetched_frames",fetched_.load()},{"mic_peak",mic_peak_.load()},{"afe_result",afe_result_.load()},{"feed_result",feed_result_.load()},{"feed_stack_free_min_bytes",feed_stack_free_.load()},{"wake_count",wakes_.load()},{"recognized_count",recognized_.load()},{"rejected_count",rejected_.load()},
  {"stack_free_min_bytes",stack_free_.load()},{"internal_free",heap_caps_get_free_size(MALLOC_CAP_INTERNAL|MALLOC_CAP_8BIT)},
  {"psram_free",heap_caps_get_free_size(MALLOC_CAP_SPIRAM)}};}
 std::vector<FunctionSchema> get_function_schemas() override{return {
  {"GetState","Offline recognition state",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"State"}},
  {"ListenNow","Listen for a local command without requiring a wake phrase",{}},
  {"SetEnabled","Enable local microphone recognition",{{"Enabled","Enabled",FunctionValueType::Boolean}}},
  {"TestPhrase","Inject fixed local speech fixture; not an acoustic microphone test",{{"Command","1..11 (9..11 are negative fixtures)",FunctionValueType::Number}}},
  {"TestAction","Exercise only command routing; does not test speech recognition",{{"Command","1..8",FunctionValueType::Number}}}};}
 FunctionHandlerList get_function_handlers() override{return {
  {"GetState",[this](FunctionParameterMap &&)->FunctionResult{return {.success=true,.data=FunctionValue(snapshot())};}},
  {"ListenNow",[this](FunctionParameterMap &&)->FunctionResult{if(!active_ || diagnostic_active_ || !permitted())return {.success=false,.error_message="请家长在设置中开启离线语音，或等待在线助手关闭"};if(!listening_)manual_listen_=true;return {.success=true};}},
  {"SetEnabled",[](FunctionParameterMap &&p)->FunctionResult{brookesia_board_set_offline_voice(std::get<bool>(p.at("Enabled")));return {.success=true};}},
  {"TestPhrase",[this](FunctionParameterMap &&p)->FunctionResult{double id=std::get<double>(p.at("Command"));if(!active_||listening_||diagnostic_active_||diagnostic_ || !std::isfinite(id)||id<1||id>11||std::floor(id)!=id)return {.success=false,.error_message="Recognizer busy or invalid command"};diagnostic_=int(id);return {.success=true};}},
  {"TestAction",[this](FunctionParameterMap &&p)->FunctionResult{double id=std::get<double>(p.at("Command"));if(!std::isfinite(id)||id<1||id>8||std::floor(id)!=id)return {.success=false,.error_message="Invalid command"};if(!active_ || pending_action_)return {.success=false,.error_message="Recognizer busy"};pending_action_=int(id);return {.success=true};}}};}
};
}
std::shared_ptr<ServiceBase> make_offline_voice_service(){return std::make_shared<OfflineVoice>();}
bool offline_voice_prepare_online(){online_hold_until=now_ms()+6000;for(int i=0;mic_in_use && i<200;++i)vTaskDelay(pdMS_TO_TICKS(20));return !mic_in_use;}
bool offline_voice_quiesce(){for(int i=0;mic_in_use && i<200;++i)vTaskDelay(pdMS_TO_TICKS(20));return !mic_in_use;}

bool offline_voice_worker_thread(){const auto task=sr_worker.load(),feeder=sr_feeder.load();const auto current=xTaskGetCurrentTaskHandle();return (task && current==task) || (feeder && current==feeder);}
