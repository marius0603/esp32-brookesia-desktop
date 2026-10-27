#include "local_voice.hpp"
#include "pcm_protocol.hpp"
#include "../audio_ownership.hpp"
#include "../offline_voice/offline_voice.hpp"
#include "../child_mode/child_mode.hpp"
#include "brookesia/hal_interface/interface.hpp"
#include "brookesia/hal_interface/interfaces/audio/codec_recorder.hpp"
#include "brookesia/hal_interface/interfaces/audio/codec_player.hpp"
#include "esp_websocket_client.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "esp_netif.h"
#include "esp_crt_bundle.h"
#include "nvs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>
#include <cstdio>
#include <mutex>
#include <string_view>

using namespace esp_brookesia;
using namespace esp_brookesia::service;
namespace {
constexpr size_t SAMPLES=960,PCM_BYTES=1920,DEPTH=384,PREFILL=256;
constexpr uint32_t STACK=16*1024;
// Receive can hold the WebSocket mutex for its 3s network timeout.
// Sending must allow that receive to finish before acquiring the same mutex.
constexpr uint32_t SEND_TIMEOUT_MS=5000;
uint32_t u32(const uint8_t *p){return pc_voice::read32(p);}
void put32(uint8_t *p,uint32_t value){for(int i=0;i<4;++i)p[i]=uint8_t(value>>(8*i));}
std::string value(const boost::json::object &j,const char *key){auto *v=j.if_contains(key);return v&&v->is_string()?std::string(v->as_string().c_str(),v->as_string().size()):"";}
std::string clipped(std::string text,size_t limit){if(text.size()>limit){size_t n=limit;while(n && (uint8_t(text[n])&0xc0)==0x80)--n;text.resize(n);}return text;}
struct Block{uint32_t sequence,segment;uint16_t size;uint8_t data[PCM_BYTES];};
class LocalVoice final:public ServiceBase {
public:
    LocalVoice():ServiceBase({.name="LocalVoice",.description="PC ASR, cloud dialogue and PC TTS",.version="0.1.0",.dependencies={"AudioPlayback"}}){}
private:
    std::mutex mutex_,queue_mutex_;
    std::string state_="Idle",message_="点击连接电脑",user_,answer_,error_,url_,token_;
    bool config_dirty_=false;
    bool local_test_=false;
    std::atomic<bool> live_{false},cancel_{false},fatal_{false},connected_{false},channel_{false},done_{false};
    std::atomic<bool> connection_lost_{false};
    std::atomic<bool> ack_live_{false},ack_stop_{false};
    std::atomic<int> command_{0};
    std::atomic<uint32_t> turn_{0},captured_{0},sent_{0},received_{0},played_{0},level_{0},peak_{0},minimum_stack_{STACK};
    esp_websocket_client_handle_t ws_=nullptr;
    hal::InterfaceHandle<hal::audio::CodecRecorderIface> recorder_;
    hal::InterfaceHandle<hal::audio::CodecPlayerIface> player_;
    bool recording_=false,playing_=false;
    uint8_t *raw_=nullptr,*tx_=nullptr,*frame_=nullptr;int16_t *pcm_=nullptr;
    Block *queue_=nullptr,*block_=nullptr;
    size_t head_=0,count_=0,frame_used_=0;int frame_opcode_=0;
    uint32_t input_sequence_=0,output_sequence_=0;
    uint32_t segment_=0,completed_segment_=0,playing_segment_=0,ack_turn_=0,ack_sequence_=0;
    bool ack_pending_=false,segment_end_=false,buffering_=true;
    std::atomic<uint32_t> maximum_gap_ms_{0};
    std::atomic<uint32_t> ack_stack_min_{8192};
    int64_t last_write_=0;uint32_t last_segment_=0;
    void state(const char *name,const std::string &message){
        const std::string_view s=name;
        if(fatal_&&s!="Error")return;
        local_audio::assistant_busy=s!="Idle"&&s!="Ready"&&s!="Error";
        std::lock_guard<std::mutex> lock(mutex_);state_=name;message_=clipped(message,300);
    }
    void fail(const std::string &message){
        fatal_=true;local_audio::assistant_busy=false;
        std::lock_guard<std::mutex> lock(mutex_);state_="Error";message_=error_=clipped(message,300);
    }
    boost::json::object snapshot(){
        char address[16]{};esp_netif_ip_info_t ip{};auto *netif=esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
        if(netif&&esp_netif_get_ip_info(netif,&ip)==ESP_OK)std::snprintf(address,sizeof(address),IPSTR,IP2STR(&ip.ip));
        std::lock_guard<std::mutex> lock(mutex_);
        return {{"state",state_},{"message",message_},{"user_text",user_},{"answer",answer_},{"error",error_},
            {"active",live_.load()},{"connected",connected_.load()},{"channel",channel_.load()},
            {"configured",!url_.empty()&&!token_.empty()},{"endpoint",url_},{"device_ip",address},{"backend","pc"},
            {"captured_frames",captured_.load()},{"sent_packets",sent_.load()},{"received_packets",received_.load()},
            {"played_bytes",played_.load()},{"level",level_.load()},{"peak",peak_.load()},
            {"max_playback_gap_ms",maximum_gap_ms_.load()},
            {"ack_stack_free_min_bytes",ack_stack_min_.load()},
            {"free_psram_bytes",heap_caps_get_free_size(MALLOC_CAP_SPIRAM)},
            {"turn",turn_.load()},{"control_stack_free_min_bytes",minimum_stack_.load()}};
    }
    void clear_queue(){std::lock_guard<std::mutex> lock(queue_mutex_);head_=count_=0;}
    bool pop(){std::lock_guard<std::mutex> lock(queue_mutex_);if(!count_)return false;*block_=queue_[head_];head_=(head_+1)%DEPTH;--count_;return true;}
    bool empty(){std::lock_guard<std::mutex> lock(queue_mutex_);return count_==0;}
    bool buffered(){
        std::lock_guard<std::mutex> lock(queue_mutex_);
        return count_&&(queue_[head_].segment<=completed_segment_||
            (!buffering_&&queue_[head_].segment==playing_segment_)||count_>=PREFILL||done_);
    }
    void acknowledgements(){
        while(!ack_stop_&&!cancel_&&!fatal_){
            ack_stack_min_=std::min(ack_stack_min_.load(),uint32_t(uxTaskGetStackHighWaterMark(nullptr)));
            uint32_t id=0,sequence=0;bool pending=false;
            {std::lock_guard<std::mutex> lock(queue_mutex_);pending=ack_pending_;ack_pending_=false;id=ack_turn_;sequence=ack_sequence_;}
            if(pending&&channel_&&id==turn_)send({{"type","played"},{"turn",id},{"seq",sequence}});
            vTaskDelay(pdMS_TO_TICKS(10));
        }
        ack_live_=false;
    }
    bool send(boost::json::object object){
        if(cancel_||fatal_||!ws_||!connected_)return false;
        const auto text=boost::json::serialize(object);
        if(esp_websocket_client_send_text(ws_,text.c_str(),text.size(),pdMS_TO_TICKS(SEND_TIMEOUT_MS))<0){if(!cancel_)fail("电脑连接已中断");return false;}
        return true;
    }
    void receive(const esp_websocket_event_data_t &data){
        if(cancel_||fatal_||data.data_len<0||data.payload_len<0||data.payload_offset<0)return;
        if(data.op_code!=1&&data.op_code!=2)return;
        if(data.payload_offset==0){frame_used_=0;frame_opcode_=data.op_code;}
        if(size_t(data.payload_len)>4096 || size_t(data.payload_offset)!=frame_used_ || frame_used_+data.data_len>4096){fail("电脑数据分片异常");return;}
        memcpy(frame_+frame_used_,data.data_ptr,data.data_len);frame_used_+=data.data_len;
        if(frame_used_!=size_t(data.payload_len))return;
        if(frame_opcode_==2){
            if(pc_voice::inspect(frame_,frame_used_,turn_)==pc_voice::Frame::Invalid){fail("电脑音频格式异常");return;}
            const auto sequence=u32(frame_+8);
            bool full=false,bad=false;
            {std::lock_guard<std::mutex> lock(queue_mutex_);if(u32(frame_+4)!=turn_)return;
                bad=sequence!=output_sequence_;full=count_==DEPTH;
                if(!bad&&!full){++output_sequence_;auto &p=queue_[(head_+count_)%DEPTH];p.sequence=sequence;p.segment=segment_;p.size=frame_used_-12;memcpy(p.data,frame_+12,p.size);++count_;++received_;}}
            if(bad)fail("电脑音频顺序异常");
            if(full)fail("音频缓冲已满，请重新连接");
            return;
        }
        boost::system::error_code ec;auto json=boost::json::parse(std::string(reinterpret_cast<char *>(frame_),frame_used_),ec);
        if(ec||!json.is_object()){fail("电脑控制消息异常");return;}
        const auto &j=json.as_object();const auto type=value(j,"type");
        std::lock_guard<std::mutex> turn_lock(queue_mutex_);
        if(auto *id=j.if_contains("turn");id && id->is_int64() && uint32_t(id->as_int64())!=turn_)return;
        if(type=="ready"){channel_=true;state("Ready","点击说话，再次点击发送");}
        else if(type=="status")state(value(j,"state").c_str(),value(j,"message"));
        else if(type=="user_text"){std::lock_guard<std::mutex> lock(mutex_);user_=clipped(value(j,"text"),600);}
        else if(type=="answer"){std::lock_guard<std::mutex> lock(mutex_);answer_=clipped(value(j,"text"),1600);}
        else if(type=="audio_start"){++segment_;segment_end_=false;state("Speaking","正在回答");}
        else if(type=="audio_end"){segment_end_=true;completed_segment_=segment_;}
        else if(type=="done"||type=="cancelled")done_=true;
        else if(type=="error"){done_=true;std::lock_guard<std::mutex> lock(mutex_);message_=error_=clipped(value(j,"message"),300);state_="Error";}
    }
    static void event(void *context,esp_event_base_t,int32_t id,void *data){
        auto &self=*static_cast<LocalVoice *>(context);
        if(id==WEBSOCKET_EVENT_CONNECTED)self.connected_=true;
        else if(id==WEBSOCKET_EVENT_DATA&&data)self.receive(*static_cast<esp_websocket_event_data_t *>(data));
        else if((id==WEBSOCKET_EVENT_DISCONNECTED||id==WEBSOCKET_EVENT_ERROR)&&!self.cancel_&&!self.fatal_){self.connected_=false;self.channel_=false;self.connection_lost_=true;}
    }
    void close_recorder(){if(recording_){recorder_->close();recording_=false;}level_=0;}
    void close_player(){if(playing_){if(player_->is_pa_on_off_supported())player_->set_pa_on_off(false);player_->close();playing_=false;}}
    bool open_player(){if(playing_)return true;player_->close();if(!player_->open({.bits=16,.channels=1,.sample_rate=16000})){fail("无法打开喇叭");return false;}playing_=true;if(player_->is_pa_on_off_supported())player_->set_pa_on_off(true);return true;}
    bool capture(){
        const auto &info=recorder_->get_info();
        if(info.sample_rate!=16000||info.channels<1||info.channels>4||(info.bits!=16&&info.bits!=32)){fail("麦克风格式不兼容");return false;}
        if(!recorder_->read_data(raw_,SAMPLES*info.channels*(info.bits/8))){fail("麦克风读取失败");return false;}
        const auto m=info.mic_layout.find('M');const unsigned channel=m<info.channels?m:info.channels-1;
        uint64_t energy=0;uint32_t peak=0;
        for(size_t i=0;i<SAMPLES;++i){int sample=info.bits==32?reinterpret_cast<int32_t *>(raw_)[i*info.channels+channel]>>16:reinterpret_cast<int16_t *>(raw_)[i*info.channels+channel];pcm_[i]=sample;peak=std::max(peak,uint32_t(std::abs(sample)));energy+=int64_t(sample)*sample;}
        peak_=std::max(peak_.load(),peak);level_=std::min(100u,unsigned(std::sqrt(double(energy)/SAMPLES)*100/6000));captured_+=SAMPLES;return true;
    }
    bool preferences(std::string &url,std::string &token){
        std::lock_guard<std::mutex> lock(mutex_);nvs_handle_t h;
        if(nvs_open("LocalVoice",NVS_READWRITE,&h)==ESP_OK){
            if(config_dirty_){
                const bool ok=nvs_set_str(h,"url",url_.c_str())==ESP_OK && nvs_set_str(h,"token",token_.c_str())==ESP_OK && nvs_commit(h)==ESP_OK;
                if(!ok){nvs_close(h);return false;}config_dirty_=false;
            }else if(url_.empty()){
                char address[257]{},key[97]{};size_t a=sizeof(address),b=sizeof(key);
                if(nvs_get_str(h,"url",address,&a)==ESP_OK && nvs_get_str(h,"token",key,&b)==ESP_OK){url_=address;token_=key;}
            }
            nvs_close(h);
        }else return false;
        url=url_;token=token_;return !url.empty()&&!token.empty();
    }
    bool prepare(){
        auto rec=hal::acquire_interfaces<hal::audio::CodecRecorderIface>();auto play=hal::acquire_interfaces<hal::audio::CodecPlayerIface>();
        if(rec.empty()||play.empty()){fail("未找到麦克风或喇叭");return false;}
        recorder_=std::move(rec.front());player_=std::move(play.front());
        auto alloc=[](size_t bytes){return heap_caps_calloc(1,bytes,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);};
        raw_=static_cast<uint8_t *>(alloc(SAMPLES*4*4));pcm_=static_cast<int16_t *>(alloc(PCM_BYTES));
        tx_=static_cast<uint8_t *>(alloc(PCM_BYTES+12));frame_=static_cast<uint8_t *>(alloc(4097));
        queue_=static_cast<Block *>(alloc(sizeof(Block)*DEPTH));block_=static_cast<Block *>(alloc(sizeof(Block)));
        if(!raw_||!pcm_||!tx_||!frame_||!queue_||!block_){fail("语音缓冲内存不足");return false;}return true;
    }
    void conversation(const std::string &url,const std::string &token){
        wifi_ap_record_t ap{};if(esp_wifi_sta_get_ap_info(&ap)!=ESP_OK){fail("请先连接Wi-Fi");return;}
        esp_websocket_client_config_t config{};config.uri=url.c_str();config.buffer_size=4096;
        if(url.starts_with("wss://"))config.crt_bundle_attach=esp_crt_bundle_attach;
        config.task_stack=8192;config.disable_auto_reconnect=false;config.reconnect_timeout_ms=3000;config.network_timeout_ms=3000;
        ws_=esp_websocket_client_init(&config);
        if(!ws_){fail("无法创建电脑连接");return;}
        esp_websocket_register_events(ws_,WEBSOCKET_EVENT_ANY,event,this);
        if(esp_websocket_client_start(ws_)!=ESP_OK){fail("电脑连接启动失败");return;}
        ack_stop_=false;ack_live_=true;
        TaskHandle_t ack_task=nullptr;
        if(xTaskCreatePinnedToCore([](void *ctx){static_cast<LocalVoice *>(ctx)->acknowledgements();vTaskDelete(nullptr);},"voice_ack",8192,this,3,&ack_task,0)!=pdPASS){
            ack_live_=false;fail("播放确认任务内存不足");return;}
        bool hello=false;int64_t connected_at=esp_timer_get_time(),recorded_at=0,waiting=0;
        while(!cancel_&&!fatal_){
            minimum_stack_=std::min(minimum_stack_.load(),uint32_t(uxTaskGetStackHighWaterMark(nullptr)));
            if(!child_mode_voice_allowed()){fail("语音助手已被家长限制");break;}
            if(connection_lost_.exchange(false)){
                close_recorder();close_player();
                {std::lock_guard<std::mutex> lock(queue_mutex_);++turn_;head_=count_=0;output_sequence_=0;done_=false;ack_pending_=false;segment_end_=false;}
                buffering_=true;last_write_=0;maximum_gap_ms_=0;
                if(hello){connected_at=esp_timer_get_time();}
                hello=false;waiting=0;input_sequence_=0;
                state("Connecting","网络断开，正在重新连接电脑");
            }
            if(connected_&&!hello){hello=send({{"type","hello"},{"token",token},{"sample_rate",16000},{"channels",1},{"bits",16}});}
            if(!channel_){if(esp_timer_get_time()-connected_at>90000000){fail("电脑准备超时，请重新连接");break;}vTaskDelay(pdMS_TO_TICKS(20));continue;}
            const int cmd=command_.exchange(0);
            if(cmd==1||cmd==3||cmd==4){
                send({{"type","cancel"},{"turn",turn_.load()}});close_recorder();close_player();
                {std::lock_guard<std::mutex> lock(queue_mutex_);++turn_;head_=count_=0;output_sequence_=0;done_=false;ack_pending_=false;segment_end_=false;}
                buffering_=true;last_write_=0;maximum_gap_ms_=0;
                input_sequence_=0;waiting=0;
                {std::lock_guard<std::mutex> lock(mutex_);error_.clear();if(cmd!=3){user_.clear();answer_.clear();}}
                if(cmd==1){
                    if(!send({{"type","listen_start"},{"turn",turn_.load()}}))break;
                    if(!recorder_->open()){fail("无法打开麦克风");break;}recording_=true;recorded_at=esp_timer_get_time();state("Listening","正在录音，再点一下发送");
                }else if(cmd==4){
                    send({{"type","text"},{"turn",turn_.load()},{"text","请只回复：语音助手连接成功。"}});waiting=esp_timer_get_time();state("Thinking","正在测试电脑回答");
                }else state("Ready","已停止，点击继续说话");
            }
            if(cmd==2 || (recording_&&esp_timer_get_time()-recorded_at>=30000000)){
                if(recording_){close_recorder();send({{"type","listen_end"},{"turn",turn_.load()}});waiting=esp_timer_get_time();state("Recognizing","正在识别");}
            }
            if(recording_){
                if(!capture())break;
                memcpy(tx_,"VPC1",4);put32(tx_+4,turn_);put32(tx_+8,input_sequence_++);memcpy(tx_+12,pcm_,PCM_BYTES);
                if(esp_websocket_client_send_bin(ws_,reinterpret_cast<char *>(tx_),PCM_BYTES+12,pdMS_TO_TICKS(SEND_TIMEOUT_MS))<0){fail("录音发送失败");break;}
                ++sent_;vTaskDelay(1);continue;
            }
            if(buffered()&&pop()){
                buffering_=false;playing_segment_=block_->segment;
                if(!open_player())break;
                if(!player_->write_data(block_->data,block_->size)){fail("喇叭播放失败");break;}
                const auto now=esp_timer_get_time();
                if(last_write_&&last_segment_==block_->segment)maximum_gap_ms_=std::max(maximum_gap_ms_.load(),uint32_t((now-last_write_)/1000));
                last_write_=now;last_segment_=block_->segment;
                played_+=block_->size;
                {std::lock_guard<std::mutex> lock(queue_mutex_);ack_turn_=turn_;ack_sequence_=block_->sequence;ack_pending_=true;}
                waiting=esp_timer_get_time();state("Speaking","正在回答");
            }else{
                if(empty())buffering_=true;
                if(done_&&empty()){
                    close_player();done_=false;waiting=0;
                    bool error=false;{std::lock_guard<std::mutex> lock(mutex_);error=!error_.empty();}
                    if(!error)state("Ready","点击继续说话");else local_audio::assistant_busy=false;
                }
                if(waiting&&esp_timer_get_time()-waiting>120000000){fail("回答超时，请停止后重试");break;}
                vTaskDelay(pdMS_TO_TICKS(10));
            }
        }
        ack_stop_=true;while(ack_live_)vTaskDelay(pdMS_TO_TICKS(10));
    }
    void run(){
        std::string url,token;
        if(local_test_){
            if(prepare()){
                auto *recording=static_cast<int16_t *>(heap_caps_malloc(50*PCM_BYTES,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT));
                if(!recording)fail("录音测试内存不足");
                else if(!recorder_->open()){heap_caps_free(recording);fail("无法打开麦克风");}
                else{
                    recording_=true;size_t frames=0;state("Testing","请说话，录音三秒后回放");
                    for(;frames<50&&!cancel_&&!fatal_&&child_mode_voice_allowed();++frames){if(!capture())break;memcpy(recording+frames*SAMPLES,pcm_,PCM_BYTES);}
                    close_recorder();
                    if(!cancel_&&!fatal_&&child_mode_voice_allowed()&&open_player())for(size_t i=0;i<frames&&!cancel_&&child_mode_voice_allowed();++i){if(!player_->write_data(reinterpret_cast<uint8_t *>(recording+i*SAMPLES),PCM_BYTES)){fail("录音回放失败");break;}played_+=PCM_BYTES;}
                    heap_caps_free(recording);if(!cancel_&&!fatal_)state("Idle","录音测试完成，点击连接电脑");
                }
            }
        }else if(!preferences(url,token))fail("请先在电脑端配置设备连接");
        else if(prepare())conversation(url,token);
        const bool requested=cancel_.load();cancel_=true;channel_=false;
        ack_stop_=true;while(ack_live_)vTaskDelay(pdMS_TO_TICKS(10));
        close_recorder();close_player();
        if(ws_){esp_websocket_client_stop(ws_);esp_websocket_client_destroy(ws_);ws_=nullptr;}
        {std::lock_guard<std::mutex> lock(queue_mutex_);heap_caps_free(queue_);queue_=nullptr;head_=count_=0;}
        heap_caps_free(raw_);heap_caps_free(pcm_);heap_caps_free(tx_);heap_caps_free(frame_);heap_caps_free(block_);
        raw_=tx_=frame_=nullptr;pcm_=nullptr;block_=nullptr;recorder_.reset();player_.reset();
        connected_=false;level_=0;if(requested)state("Idle","已断开，点击连接电脑");
        local_audio::release(local_audio::Assistant);live_=false;
    }
    std::expected<void,std::string> launch(bool local_test=false){
        if(!child_mode_voice_allowed())return std::unexpected("家长尚未授权语音助手，或已到休息时间");
        bool expected=false;if(!live_.compare_exchange_strong(expected,true))return std::unexpected("助手正在运行或关闭中");
        if(!offline_voice_prepare_online()){live_=false;return std::unexpected("麦克风正在释放，请稍后重试");}
        if(!local_audio::claim(local_audio::Assistant)){live_=false;return std::unexpected("请先停止听书或其他助手");}
        cancel_=fatal_=connected_=channel_=done_=connection_lost_=false;command_=0;turn_=0;captured_=sent_=received_=played_=level_=peak_=0;minimum_stack_=STACK;
        local_test_=local_test;
        ack_pending_=false;segment_end_=false;buffering_=true;last_write_=0;segment_=completed_segment_=playing_segment_=0;maximum_gap_ms_=0;ack_stack_min_=8192;
        {std::lock_guard<std::mutex> lock(mutex_);user_.clear();answer_.clear();error_.clear();}
        state(local_test?"Testing":"Connecting",local_test?"准备本地录音测试":"正在连接电脑");TaskHandle_t task=nullptr;
        if(xTaskCreatePinnedToCore([](void *ctx){static_cast<LocalVoice *>(ctx)->run();vTaskDelete(nullptr);},"local_voice",STACK,this,4,&task,0)!=pdPASS){
            local_audio::release(local_audio::Assistant);fail("内部内存不足");live_=false;return std::unexpected("Audio task allocation failed");}
        return {};
    }
    void disconnect(){cancel_=true;channel_=false;command_=0;if(live_)state("Stopping","正在断开电脑");}
    std::expected<void,std::string> command(int value){
        if(value==1&&!child_mode_voice_allowed())return std::unexpected("语音采集已被家长限制");
        if(!live_||cancel_||fatal_||!channel_)return std::unexpected("请先连接电脑并等待模型就绪");
        int empty=0;if(!command_.compare_exchange_strong(empty,value))return std::unexpected("正在处理，请稍候");return {};
    }
    void on_stop() override {disconnect();while(live_)vTaskDelay(pdMS_TO_TICKS(20));}
    std::vector<FunctionSchema> get_function_schemas() override {
        return {{"Connect","Connect to the paired PC",{}},{"Disconnect","Release microphone and playback",{}},
            {"StartListening","Start microphone upload",{}},{"StopListening","Submit recorded speech",{}},{"Interrupt","Cancel this turn",{}},
            {"GetState","Read local assistant state",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Assistant"}},
            {"SetConnection","Set paired LAN endpoint",{{"Url","WebSocket URL",FunctionValueType::String},{"Token","Device pairing token",FunctionValueType::String}}},
            {"TestReply","Test cloud reply and downlink without microphone",{}},{"TestMicrophone","Record and replay locally without upload",{}}};
    }
    FunctionHandlerList get_function_handlers() override {
        return {BROOKESIA_SERVICE_FUNC_HANDLER_0("Connect",launch()),
            {"Disconnect",[this](FunctionParameterMap &&)->FunctionResult{disconnect();return {.success=true};}},
            BROOKESIA_SERVICE_FUNC_HANDLER_0("StartListening",command(1)),BROOKESIA_SERVICE_FUNC_HANDLER_0("StopListening",command(2)),
            BROOKESIA_SERVICE_FUNC_HANDLER_0("Interrupt",command(3)),
            {"GetState",[this](FunctionParameterMap &&)->FunctionResult{return {.success=true,.data=FunctionValue(snapshot())};}},
            {"SetConnection",[this](FunctionParameterMap &&p)->FunctionResult{
                if(live_)return {.success=false,.error_message="请先断开助手"};
                const auto url=std::get<std::string>(p.at("Url")),token=std::get<std::string>(p.at("Token"));
                if(url.size()>256 || !(url.starts_with("ws://")||url.starts_with("wss://")) || token.size()<24 || token.size()>96)
                    return {.success=false,.error_message="Invalid paired endpoint"};
                std::lock_guard<std::mutex> lock(mutex_);url_=url;token_=token;config_dirty_=true;return {.success=true};}},
            BROOKESIA_SERVICE_FUNC_HANDLER_0("TestReply",command(4)),BROOKESIA_SERVICE_FUNC_HANDLER_0("TestMicrophone",launch(true))};
    }
};
}
std::shared_ptr<ServiceBase> make_local_voice_service(){return std::make_shared<LocalVoice>();}
