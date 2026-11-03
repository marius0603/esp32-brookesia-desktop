#include "radio.hpp"
#include "stations.hpp"
#include "playlist.hpp"
#include "../audio_ownership.hpp"
#include "../child_mode/child_mode.hpp"
#include "../device_modes/device_modes.hpp"
#include "../audiobook/buffered_pcm.hpp"
#include "../audiobook/dr_mp3.h"
#include "brookesia/hal_interface/interface.hpp"
#include "brookesia/hal_interface/interfaces/audio/codec_player.hpp"
#include "esp_http_client.h"
#include "esp_crt_bundle.h"
#include "esp_wifi.h"
#include "lwip/sockets.h"
#include "lwip/inet.h"
#include "esp_audio_dec_default.h"
#include "esp_audio_simple_dec.h"
#include "esp_audio_simple_dec_default.h"
#include "esp_aac_dec.h"
#include <cmath>
#include <mutex>
#include <memory>
#include <cstring>
#include <algorithm>
#include <cerrno>

using namespace esp_brookesia;
using namespace esp_brookesia::service;
namespace {
class Radio final:public ServiceBase {
public:
 Radio():ServiceBase({.name="Radio",.description="Buffered Wi-Fi radio",.version="0.1.0",.dependencies={"AudioPlayback"}}){}
private:
 std::mutex operation_,mutex_;
 std::string state_="Idle",error_,station_,peer_;
 std::atomic<bool> live_{false},reader_live_{false},cancel_{false},paused_{false},reader_failed_{false};
 std::atomic<uint32_t> bytes_{0},received_{0},retries_{0},starvations_{0},gap_{0},epoch_{0},rate_{0},channels_{0},decoder_free_{0},reader_free_{0};
 std::atomic<uint32_t> decode_errors_{0},decode_frames_{0},decode_max_us_{0},input_stalls_{0};
 std::atomic<int> wifi_ps_{-1};
 std::atomic<int> read_result_{0},read_errno_{0},http_status_{0};
 std::atomic<uint32_t> read_calls_{0},read_max_us_{0};
 std::atomic<uint64_t> decode_total_us_{0},read_total_us_{0};
 std::atomic<int64_t> deadline_{0};
 RingbufHandle_t net_=nullptr;
 const radio_catalog::Station *source_=nullptr;
 bool on_start()override{return true;}
 void on_stop()override{stop();}
 bool abort(){
  if(cancel_||local_audio::sleeping||!child_mode_radio_allowed())return true;
  const auto end=deadline_.load();if(end && esp_timer_get_time()>=end){set_state("TimerEnded");cancel_=true;return true;}return false;
 }
 void set_state(const std::string &s,const std::string &error=""){std::lock_guard lock(mutex_);state_=s;error_=error;}
 std::expected<void,std::string> stop(){
  std::lock_guard op(operation_);cancel_=true;paused_=false;
  for(unsigned i=0;live_&&i<1600;++i)vTaskDelay(pdMS_TO_TICKS(10));
  if(live_)return std::unexpected("Radio is closing; retry shortly");
  deadline_=0;set_state("Idle");return {};
 }
 std::expected<void,std::string> play(const std::string &id){
  const radio_catalog::Station *chosen=nullptr;for(const auto &s:radio_catalog::stations)if(id==s.id){chosen=&s;break;}
  if(!chosen)return std::unexpected("Unknown station");
  if(!child_mode_radio_allowed())return std::unexpected("网络电台暂未开放给儿童模式");
  auto stopped=stop();if(!stopped)return stopped;
  std::lock_guard op(operation_);
  if(!local_audio::claim(local_audio::Radio))return std::unexpected("请先关闭听书或语音助手");
  source_=chosen;{std::lock_guard lock(mutex_);station_=id;state_="Connecting";error_.clear();}
  cancel_=false;paused_=false;reader_failed_=false;bytes_=0;received_=0;retries_=0;starvations_=0;gap_=0;rate_=0;channels_=0;deadline_=0;decoder_free_=0;reader_free_=0;
  decode_errors_=0;decode_frames_=0;decode_max_us_=0;input_stalls_=0;
  read_result_=0;read_errno_=0;http_status_=0;read_calls_=0;read_max_us_=0;decode_total_us_=0;read_total_us_=0;
  local_audio::radio_busy=true;live_=true;
  if(xTaskCreatePinnedToCore([](void *p){static_cast<Radio *>(p)->run();vTaskDelete(nullptr);},"radio_decode",16384,this,4,nullptr,1)!=pdPASS){
   local_audio::release(local_audio::Radio);live_=false;set_state("Error","Not enough internal RAM for radio task");return std::unexpected("Radio task allocation failed");
  }return {};
 }
 std::expected<void,std::string> timer(double minutes){
  if(!std::isfinite(minutes)||(minutes!=0&&minutes!=15&&minutes!=30&&minutes!=45))return std::unexpected("Use 0,15,30,45 minutes");
  if(minutes&&!live_)return std::unexpected("请先播放电台");
  deadline_=minutes?esp_timer_get_time()+int64_t(minutes)*60000000:0;return {};
 }
 boost::json::object snapshot(){
  std::lock_guard lock(mutex_);const auto end=deadline_.load();
  wifi_ap_record_t ap{};const int rssi=esp_wifi_sta_get_ap_info(&ap)==ESP_OK?ap.rssi:-127;
  return {{"state",state_},{"error",error_},{"station",station_},{"active",live_.load()},{"paused",paused_.load()},
   {"bytes_written",bytes_.load()},{"bytes_received",received_.load()},{"reconnects",retries_.load()},{"pcm_starvations",starvations_.load()},{"write_gap_max_us",gap_.load()},
   {"sample_rate",rate_.load()},{"channels",channels_.load()},{"decoder_stack_free",decoder_free_.load()},{"reader_stack_free",reader_free_.load()},
   {"decode_errors",decode_errors_.load()},{"decoded_frames",decode_frames_.load()},{"decode_max_us",decode_max_us_.load()},{"input_stalls",input_stalls_.load()},
   {"wifi_ps_mode",wifi_ps_.load()},
   {"http_status",http_status_.load()},{"network_read_result",read_result_.load()},{"network_errno",read_errno_.load()},
   {"network_read_calls",read_calls_.load()},{"network_read_max_us",read_max_us_.load()},
   {"network_read_total_us",read_total_us_.load()},{"decode_total_us",decode_total_us_.load()},
   {"wifi_rssi",rssi},{"internal_largest_block",heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL)},
   {"server_address",peer_},
   {"sleep_remaining_seconds",end?std::max<int64_t>(0,(end-esp_timer_get_time()+999999)/1000000):0},
   {"sleep_active",end!=0},{"internal_free",heap_caps_get_free_size(MALLOC_CAP_INTERNAL)},{"psram_free",heap_caps_get_free_size(MALLOC_CAP_SPIRAM)}};
 }
 std::vector<FunctionSchema> get_function_schemas()override{return {
  {"Play","Play a verified catalog station",{{"Station","Catalog station ID",FunctionValueType::String}}},
  {"Stop","Stop and join radio workers",{}},{"Pause","Pause output",{}},{"Resume","Resume output",{}},
  {"SetSleepTimer","Stop after wall-clock minutes",{{"Minutes","0,15,30,45",FunctionValueType::Number}}},
  {"GetState","Read radio state",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Radio state"}},
  {"TestSleepTimer","Diagnostic: stop after ten seconds",{}}
 };}
 FunctionHandlerList get_function_handlers()override{return {
  BROOKESIA_SERVICE_FUNC_HANDLER_1("Play","Station",std::string,play(PARAM)),
  BROOKESIA_SERVICE_FUNC_HANDLER_0("Stop",stop()),
  {"Pause",[this](FunctionParameterMap &&)->FunctionResult{if(!live_)return {.success=false,.error_message="Nothing is playing"};paused_=true;local_audio::radio_busy=false;set_state("Paused");return {.success=true};}},
  {"Resume",[this](FunctionParameterMap &&)->FunctionResult{if(!live_)return {.success=false,.error_message="Nothing is playing"};paused_=false;local_audio::radio_busy=true;set_state("Buffering");return {.success=true};}},
  BROOKESIA_SERVICE_FUNC_HANDLER_1("SetSleepTimer","Minutes",double,timer(PARAM)),
  {"GetState",[this](FunctionParameterMap &&)->FunctionResult{return {.success=true,.data=FunctionValue(snapshot())};}},
  {"TestSleepTimer",[this](FunctionParameterMap &&)->FunctionResult{if(!live_)return {.success=false,.error_message="Nothing is playing"};deadline_=esp_timer_get_time()+10000000;return {.success=true};}}
 };}
 // A bounded read is performed only on the reader task's internal stack. No
 // certificate bypass, credentials, downloaded book or PC relay is needed.
 bool fetch(const std::string &url,std::string *text=nullptr){
  // Streaming needs continuous receive service. Restore the board's previous
  // modem-save choice when the radio worker exits, including failure paths.
  if(esp_wifi_set_ps(WIFI_PS_NONE)==ESP_OK)wifi_ps_=int(WIFI_PS_NONE);
  esp_http_client_config_t config{};config.url=url.c_str();config.timeout_ms=4000;config.buffer_size=4096;
  config.crt_bundle_attach=esp_crt_bundle_attach;config.user_agent="XiaomaRadio/0.1";config.max_redirection_count=5;config.keep_alive_enable=true;
  auto *client=esp_http_client_init(&config);if(!client)return false;
  bool okay=false;auto *buffer=static_cast<char *>(heap_caps_malloc(4096,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
  if(buffer){
   for(int redirect=0;redirect<=5&&!abort();++redirect){
    if(esp_http_client_open(client,0)!=ESP_OK)break;
    esp_http_client_fetch_headers(client);const int status=esp_http_client_get_status_code(client);http_status_=status;
    if(status>=300&&status<400){esp_http_client_close(client);if(esp_http_client_set_redirection(client)!=ESP_OK)break;continue;}
    if(status!=200)break;
    // A live body is delivered in small bursts. Do not hold already received
    // bytes for the connection's four-second timeout while filling a block.
    esp_http_client_set_timeout_ms(client,250);
    // The HTTP setter only changes poll_read; TLS keeps the socket timeout
    // installed during connect. Bound recv too, while preserving TLS state.
    const int socket=esp_http_client_get_socket(client);timeval receive_timeout{0,250000};
    if(socket>=0)setsockopt(socket,SOL_SOCKET,SO_RCVTIMEO,&receive_timeout,sizeof(receive_timeout));
    sockaddr_in remote{};socklen_t remote_size=sizeof(remote);char address[INET_ADDRSTRLEN]{};
    if(socket>=0&&getpeername(socket,reinterpret_cast<sockaddr *>(&remote),&remote_size)==0&&remote.sin_family==AF_INET&&inet_ntop(AF_INET,&remote.sin_addr,address,sizeof(address))){std::lock_guard lock(mutex_);peer_=address;}
    okay=true;auto last_data=esp_timer_get_time();
    while(!abort()){
     const auto began=esp_timer_get_time();int n=esp_http_client_read(client,buffer,1024);
     const auto duration=uint32_t(esp_timer_get_time()-began);read_result_=n;read_errno_=errno;++read_calls_;read_total_us_+=duration;read_max_us_=std::max(read_max_us_.load(),duration);
     reader_free_=uxTaskGetStackHighWaterMark(nullptr);
     if(n==-ESP_ERR_HTTP_EAGAIN || (n==0&&!esp_http_client_is_complete_data_received(client))){
      if(esp_timer_get_time()-last_data<12000000){vTaskDelay(pdMS_TO_TICKS(20));continue;}
      okay=false;break;
     }
     if(n<0){okay=false;break;}
     if(n==0)break;
     last_data=esp_timer_get_time();
     if(text){if(text->size()+n>32768){okay=false;break;}text->append(buffer,n);}
     else {
      received_+=n;
      while(!abort()&&xRingbufferSend(net_,buffer,n,pdMS_TO_TICKS(50))!=pdTRUE){}
     }
    }break;
   }
  }
  heap_caps_free(buffer);esp_http_client_close(client);esp_http_client_cleanup(client);return okay;
 }
 void read_network(){
  const bool hls=std::string_view(source_->format)=="hls_ts";
  std::string playlist_url=source_->url;uint64_t last=0;bool have_last=false;unsigned failures=0,nested=0;
  while(!abort()){
   bool okay=true;
   if(!hls)okay=fetch(source_->url);
   else {
    std::string text;okay=fetch(playlist_url,&text);
    if(okay){
     auto list=radio_playlist::parse(playlist_url,text);
     if(!list.error.empty()){set_state("Error",list.error);reader_failed_=true;break;}
     if(!list.nested.empty()){if(++nested>4){set_state("Error","HLS nesting limit exceeded");reader_failed_=true;break;}playlist_url=list.nested;continue;}
     if(list.segments.empty())okay=false;
     if(have_last&&!list.segments.empty()&&list.segments.back().sequence<last){have_last=false;++retries_;}
     // Start two segments behind the live edge. Subsequent polls use sequence
     // numbers, rather than repeating the last segment on every playlist fetch.
     size_t start=have_last?0:(list.segments.size()>2?list.segments.size()-2:0);
     for(size_t i=start;i<list.segments.size()&&!abort();++i){
      const auto &s=list.segments[i];if(have_last&&s.sequence<=last)continue;
      if(!fetch(s.url)){okay=false;break;}last=s.sequence;have_last=true;
     }
    }
   }
   if(abort())break;
   if(!hls||!okay){
    ++retries_;if(!okay&&++failures>=6){set_state("Error","音源暂不可用，请切换频道或重试");reader_failed_=true;break;}
    if(!paused_)set_state("Reconnecting");
    for(unsigned i=0;i<std::min(30u,5u*(1+failures))&&!abort();++i)vTaskDelay(pdMS_TO_TICKS(100));
   }else {failures=0;for(int i=0;i<10&&!abort();++i)vTaskDelay(pdMS_TO_TICKS(100));}
  }
  reader_live_=false;
 }
 void run(){
  wifi_ps_type_t previous_ps=WIFI_PS_MIN_MODEM;const bool restore_ps=esp_wifi_get_ps(&previous_ps)==ESP_OK;
  if(esp_wifi_set_ps(WIFI_PS_NONE)==ESP_OK)wifi_ps_=int(WIFI_PS_NONE);
  net_=xRingbufferCreateWithCaps(128*1024,RINGBUF_TYPE_BYTEBUF,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
  auto *pcm=static_cast<uint8_t *>(heap_caps_malloc(32768,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
  auto *stereo=static_cast<int16_t *>(heap_caps_malloc(32768,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
  auto *input=static_cast<uint8_t *>(heap_caps_malloc(16384,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
  auto codecs=hal::acquire_interfaces<hal::audio::CodecPlayerIface>();
  auto codec=codecs.empty()?hal::InterfaceHandle<hal::audio::CodecPlayerIface>{}:std::move(codecs.front());
  esp_audio_simple_dec_handle_t decoder=nullptr;std::unique_ptr<StoryPcmBuffer> output;
  auto *mp3_decoder=static_cast<drmp3dec *>(heap_caps_malloc(sizeof(drmp3dec),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
  auto fail=[&](const char *why){set_state("Error",why);cancel_=true;};
  do {
   if(!net_||!pcm||!stereo||!input||!codec||!mp3_decoder){fail("Not enough audio memory");break;}
   esp_audio_dec_register_default();esp_audio_simple_dec_register_default();
   const bool ts=std::string_view(source_->format)=="hls_ts";
   const bool mp3=std::string_view(source_->format)=="mp3";
   esp_aac_dec_cfg_t aac=ESP_AAC_DEC_CONFIG_DEFAULT();aac.aac_plus_enable=true;
   esp_audio_simple_dec_cfg_t config{};config.dec_type=ts?ESP_AUDIO_SIMPLE_DEC_TYPE_TS:mp3?ESP_AUDIO_SIMPLE_DEC_TYPE_MP3:ESP_AUDIO_SIMPLE_DEC_TYPE_AAC;
   if(!ts&&!mp3){config.dec_cfg=&aac;config.cfg_size=sizeof(aac);}
   if(!mp3&&esp_audio_simple_dec_open(&config,&decoder)!=ESP_AUDIO_ERR_OK){fail("Audio decoder unavailable");break;}
   codec->close();if(!codec->open({.bits=16,.channels=2,.sample_rate=16000})){fail("Speaker unavailable");break;}
   if(codec->is_pa_on_off_supported())codec->set_pa_on_off(true);
   output=std::make_unique<StoryPcmBuffer>([&](const uint8_t *p,size_t size,uint32_t,uint32_t){
    if(!codec->write_data(p,size))return false;
    bytes_+=size;return true;
   },paused_,epoch_,starvations_,gap_,[&](){return abort();});
   if(!output->start()){fail("PCM output allocation failed");break;}
   reader_live_=true;
   if(xTaskCreatePinnedToCore([](void *p){static_cast<Radio *>(p)->read_network();vTaskDelete(nullptr);},"radio_http",12288,this,4,nullptr,0)!=pdPASS){reader_live_=false;fail("Network task allocation failed");break;}
   set_state("Buffering");uint64_t phase=0;unsigned bad_frames=0;size_t input_size=0;
   // Several seconds of compressed data cover TLS/server burst delivery. The
   // PCM queue alone covers only half a second before output starts.
   const size_t prefill=ts?32768:mp3?65536:49152;
   while(!abort()&&reader_live_&&xRingbufferGetCurFreeSize(net_)>128*1024-prefill)vTaskDelay(pdMS_TO_TICKS(20));
   if(mp3)drmp3dec_init(mp3_decoder);
   auto emit=[&](size_t decoded,const esp_audio_simple_dec_info_t &info){
    if(info.bits_per_sample!=16||(info.channel!=1&&info.channel!=2)||info.sample_rate<8000||info.sample_rate>96000){fail("Unsupported audio format");return false;}
    rate_=info.sample_rate;channels_=info.channel;++decode_frames_;auto *samples=reinterpret_cast<int16_t *>(pcm);const size_t frames=decoded/(info.channel*2);size_t count=0;
    for(;phase<frames*16000;phase+=info.sample_rate){
     const size_t at=phase/16000,next=std::min(at+1,frames-1);const int fraction=phase%16000;int a=0,b=0;
     for(unsigned ch=0;ch<info.channel;++ch){a+=samples[at*info.channel+ch];b+=samples[next*info.channel+ch];}
     int sample=(int64_t(a)*(16000-fraction)+int64_t(b)*fraction)/(16000*info.channel);if(local_audio::offline_duck)sample/=4;
     if(count+2>16384){fail("Resample output exceeds bound");return false;}stereo[count++]=sample;stereo[count++]=sample;
    }
    phase-=frames*16000;
    if(!abort()&&!output->send(stereo,count*2,0,[&](){return abort();})){if(!abort())fail("PCM queue failed");return false;}
    if(!paused_&&!abort())set_state("Playing");
    return !abort();
   };
   while(!abort()){
    if(output->failed()){fail("Speaker output failed");break;}
    while(paused_&&!abort())vTaskDelay(pdMS_TO_TICKS(20));
    if(input_size>=16384){fail("Audio parser input exceeded bound");break;}
    size_t size=0;auto *data=static_cast<uint8_t *>(xRingbufferReceiveUpTo(net_,&size,pdMS_TO_TICKS(100),std::min<size_t>(4096,16384-input_size)));
    if(!data){if(!reader_live_){fail("音源暂不可用，请切换频道或重试");break;}continue;}
    memcpy(input+input_size,data,size);input_size+=size;vRingbufferReturnItem(net_,data);
    esp_audio_simple_dec_raw_t raw{};raw.buffer=input;raw.len=input_size;
    while(raw.len&&!abort()){
     // minimp3's push API treats an incomplete tail as unsynchronised data.
     // Keep enough look-ahead across network blocks, just as dr_mp3's file
     // reader does; never discard a partial MP3 frame at each HTTP boundary.
     if(mp3&&raw.len<4096)break;
     esp_audio_simple_dec_out_t frame{};frame.buffer=pcm;frame.len=32768;
     raw.consumed=0;const auto began=esp_timer_get_time();esp_audio_err_t result=ESP_AUDIO_ERR_OK;esp_audio_simple_dec_info_t info{};
     if(mp3){
      // Push complete frames from our bounded network staging buffer. The
      // file-oriented pull API refills 64KiB at a time, stalling a live stream.
      drmp3dec_frame_info decoded{};const int frames=drmp3dec_decode_frame(mp3_decoder,raw.buffer,raw.len,pcm,&decoded);
      raw.consumed=std::max(0,decoded.frame_bytes);frame.decoded_size=std::max(0,frames)*std::max(0,decoded.channels)*2;
      info.bits_per_sample=16;info.channel=decoded.channels;info.sample_rate=decoded.sample_rate;
     }else result=esp_audio_simple_dec_process(decoder,&raw,&frame);
     const auto decode_us=uint32_t(esp_timer_get_time()-began);decode_total_us_+=decode_us;decode_max_us_=std::max(decode_max_us_.load(),decode_us);
     decoder_free_=uxTaskGetStackHighWaterMark(nullptr);
     if(result==ESP_AUDIO_ERR_BUFF_NOT_ENOUGH){fail("Audio frame exceeds bounded PCM buffer");break;}
     if(raw.consumed>raw.len){fail("Invalid decoder consumed size");break;}
     raw.buffer+=raw.consumed;raw.len-=raw.consumed;
     if(result==ESP_AUDIO_ERR_DATA_LACK||result==ESP_AUDIO_ERR_CONTINUE){if(!raw.consumed)break;continue;}
     if(result!=ESP_AUDIO_ERR_OK){++decode_errors_;if(++bad_frames>200){fail("Unsupported or damaged audio stream");break;}if(!raw.consumed)break;continue;}
     if(frame.decoded_size){
      bad_frames=0;
      if(!mp3&&esp_audio_simple_dec_get_info(decoder,&info)!=ESP_AUDIO_ERR_OK){fail("Unsupported audio format");break;}
      if(!emit(frame.decoded_size,info))break;
     }
     if(!raw.consumed&&!frame.decoded_size){++input_stalls_;break;}
    }
    input_size=raw.len;if(input_size&&raw.buffer!=input)memmove(input,raw.buffer,input_size);vTaskDelay(1);
   }
  }while(false);
  cancel_=true;paused_=false;
  while(reader_live_)vTaskDelay(pdMS_TO_TICKS(10));
  if(output){output->finish(false);output.reset();}
  if(codec){if(codec->is_pa_on_off_supported())codec->set_pa_on_off(false);codec->close();}
  if(decoder)esp_audio_simple_dec_close(decoder);
  heap_caps_free(mp3_decoder);
  heap_caps_free(pcm);heap_caps_free(stereo);heap_caps_free(input);if(net_){vRingbufferDeleteWithCaps(net_);net_=nullptr;}
  if(restore_ps){esp_wifi_set_ps(previous_ps);wifi_ps_=int(previous_ps);}
  {std::lock_guard lock(mutex_);if(state_!="Error"&&state_!="TimerEnded")state_="Idle";}
  deadline_=0;local_audio::release(local_audio::Radio);live_=false;
 }
};
}
std::shared_ptr<ServiceBase> make_radio_service(){return std::make_shared<Radio>();}
