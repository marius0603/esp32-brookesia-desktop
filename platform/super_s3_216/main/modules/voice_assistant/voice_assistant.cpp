#include "voice_assistant.hpp"
#include "../audio_ownership.hpp"
#include "../child_mode/child_mode.hpp"
#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>
#include <ctime>
#include <mutex>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "freertos/idf_additions.h"
#include "esp_event.h"
#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "esp_xiaozhi_chat.h"
#include "esp_xiaozhi_info.h"
#include "esp_mcp_engine.h"
#include "esp_opus_enc.h"
#include "esp_opus_dec.h"
#include "brookesia/hal_interface/interface.hpp"
#include "brookesia/hal_interface/interfaces/audio/codec_recorder.hpp"
#include "brookesia/hal_interface/interfaces/audio/codec_player.hpp"

using namespace esp_brookesia;
using namespace esp_brookesia::service;
namespace {
constexpr int RATE = 16000, FRAME = 960, PACKET_MAX = 1500, QUEUE_SIZE = 96;
// esp_audio_codec documents about 40 KiB stack for encoding and 20 KiB for decoding.
// Only the codec task uses this PSRAM stack. NVS/TLS stay on a separate internal stack.
constexpr uint32_t VOICE_STACK_BYTES = 48 * 1024;
constexpr uint32_t VOICE_STACK_LIMIT_BYTES = 40 * 1024;
constexpr uint32_t CONTROL_STACK_BYTES = 16 * 1024;
struct Packet { uint16_t len; uint8_t data[PACKET_MAX]; };
void *psram(size_t size) { return heap_caps_calloc(1, size, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT); }
bool wifi_ready() { wifi_ap_record_t ap{}; return esp_wifi_sta_get_ap_info(&ap) == ESP_OK; }
std::string short_text(const char *text, size_t limit = 1600) {
    if (!text) return {};
    size_t n = strlen(text);
    if (n > limit) { n = limit; while (n && (static_cast<unsigned char>(text[n]) & 0xc0) == 0x80) --n; }
    return std::string(text, n);
}
class VoiceAssistant final : public ServiceBase {
public:
    VoiceAssistant() : ServiceBase({.name="VoiceAssistant", .description="Manual XiaoZhi voice assistant", .version="0.1.0", .dependencies={"AudioPlayback"}}) {}
private:
    std::mutex mutex_, queue_mutex_;
    std::string state_="Idle", message_="点击连接小智", code_, user_, answer_, error_;
    std::atomic<bool> live_{false}, cancel_{false}, connected_{false}, channel_{false}, fatal_{false};
    std::atomic<bool> accept_audio_{false}, tts_{false};
    std::atomic<int> command_{0};
    std::atomic<uint32_t> captured_{0}, sent_{0}, received_{0}, played_{0}, level_{0}, peak_{0};
    std::atomic<uint32_t> mic0_{0}, mic1_{0};
    std::atomic<uint32_t> stack_free_min_{VOICE_STACK_BYTES};
    std::atomic<uint32_t> control_stack_free_min_{CONTROL_STACK_BYTES};
    std::atomic<uint32_t> codec_test_frames_{0};
    std::atomic<bool> stack_limit_hit_{false};
    std::string stop_reason_;
    void sample_stack() { control_stack_free_min_=std::min(control_stack_free_min_.load(),static_cast<uint32_t>(uxTaskGetStackHighWaterMark(nullptr))); }
    bool stack_limit_reached() {
        sample_stack();
        if(stack_free_min_<=VOICE_STACK_BYTES-VOICE_STACK_LIMIT_BYTES)stack_limit_hit_=true;
        return stack_limit_hit_;
    }
    Packet *queue_ = nullptr;
    size_t head_=0, count_=0;
    int local_test_=0;
    esp_xiaozhi_chat_handle_t chat_=0;
    esp_event_handler_instance_t event_=nullptr;
    hal::InterfaceHandle<hal::audio::CodecRecorderIface> recorder_;
    hal::InterfaceHandle<hal::audio::CodecPlayerIface> player_;
    bool recording_=false, playing_=false;
    void *encoder_=nullptr, *decoder_=nullptr;
    enum class CodecOp { Open, Encode, Decode, Reset, Close };
    CodecOp codec_op_=CodecOp::Open;
    TaskHandle_t codec_task_=nullptr;
    SemaphoreHandle_t codec_done_=nullptr;
    std::atomic<bool> codec_live_{false};
    esp_audio_err_t codec_status_=ESP_AUDIO_ERR_OK;
    uint32_t encoded_size_=0, decoded_size_=0;
    uint8_t *raw_=nullptr, *encoded_=nullptr, *decoded_=nullptr;
    int16_t *pcm_=nullptr;
    Packet *packet_=nullptr;
    void state(const char *s, const std::string &message) {
        std::lock_guard<std::mutex> lock(mutex_); state_=s; message_=message;
    }
    void fail(const std::string &message) {
        {std::lock_guard<std::mutex> lock(mutex_);state_="Error";message_=message;error_=message;}
        fatal_=true; accept_audio_=false;
    }
    boost::json::object snapshot() {
        std::lock_guard<std::mutex> lock(mutex_);
        return {{"state",state_},{"message",message_},{"activation_code",code_},{"user_text",user_},{"answer",answer_},
                {"error",error_},{"active",live_.load()},{"connected",connected_.load()},{"channel",channel_.load()},
                {"captured_frames",captured_.load()},{"sent_packets",sent_.load()},{"received_packets",received_.load()},
                {"played_bytes",played_.load()},{"level",level_.load()},{"peak",peak_.load()},
                {"mic0_peak",mic0_.load()},{"mic1_peak",mic1_.load()},
                {"stack_total_bytes",VOICE_STACK_BYTES},{"stack_free_min_bytes",stack_free_min_.load()},
                {"control_stack_total_bytes",CONTROL_STACK_BYTES},{"control_stack_free_min_bytes",control_stack_free_min_.load()},
                {"codec_test_frames",codec_test_frames_.load()},
                {"stack_limit_bytes",VOICE_STACK_LIMIT_BYTES},{"stack_peak_used_bytes",VOICE_STACK_BYTES-stack_free_min_.load()},
                {"stack_limit_hit",stack_limit_hit_.load()},{"stop_reason",stop_reason_},
                {"internal_free_bytes",heap_caps_get_free_size(MALLOC_CAP_INTERNAL)},
                {"internal_largest_bytes",heap_caps_get_largest_free_block(MALLOC_CAP_INTERNAL)}};
    }
    void clear_queue() { std::lock_guard<std::mutex> lock(queue_mutex_);head_=count_=0; }
    bool pop() {
        std::lock_guard<std::mutex> lock(queue_mutex_);
        if (!queue_ || !count_) return false;
        *packet_=queue_[head_];head_=(head_+1)%QUEUE_SIZE;--count_;return true;
    }
    void receive(const uint8_t *data, int length) {
        if (!accept_audio_ || cancel_ || fatal_) return;
        if (length<=0 || length>PACKET_MAX) {fail("语音数据格式异常，请重新连接");return;}
        bool full=false;
        {std::lock_guard<std::mutex> lock(queue_mutex_);
            if (!queue_) return;
            if (count_==QUEUE_SIZE) full=true;
            else {auto &p=queue_[(head_+count_)%QUEUE_SIZE];p.len=length;memcpy(p.data,data,length);++count_;++received_;}
        }
        if (full) fail("语音缓冲已满，请停止后重试");
    }
    void on_chat(esp_xiaozhi_chat_event_t event, void *data) {
        if (cancel_) return;
        if (event==ESP_XIAOZHI_CHAT_EVENT_CHAT_ERROR) {fail("小智连接异常，请重新连接");return;}
        if (event==ESP_XIAOZHI_CHAT_EVENT_CHAT_TEXT && data) {
            const auto *text=static_cast<esp_xiaozhi_chat_text_data_t *>(data);
            std::lock_guard<std::mutex> lock(mutex_);
            if (text->role==ESP_XIAOZHI_CHAT_TEXT_ROLE_USER) user_=short_text(text->text,600);
            else if (accept_audio_) answer_=short_text(text->text);
        }
        if (event==ESP_XIAOZHI_CHAT_EVENT_CHAT_TTS_STATE && data && accept_audio_) {
            const auto *tts=static_cast<esp_xiaozhi_chat_tts_state_t *>(data);
            if (tts->state==ESP_XIAOZHI_CHAT_TTS_STATE_START) {tts_=true;state("Speaking","正在回答");}
            else if (tts->state==ESP_XIAOZHI_CHAT_TTS_STATE_STOP) tts_=false;
        }
    }
    std::expected<void,std::string> launch(int local_test) {
        if(!child_mode_voice_allowed())return std::unexpected("家长尚未授权语音助手，或已到休息时间");
        // A completed worker publishes live=false only after all callbacks and codecs are released.
        bool expected=false;
        if (!live_.compare_exchange_strong(expected,true)) return std::unexpected("助手正在运行或关闭中");
        if (!local_audio::claim(local_audio::Assistant)) {live_=false;return std::unexpected("请先停止听书，再连接助手");}
        local_test_=local_test;cancel_=false;fatal_=false;connected_=false;channel_=false;stack_free_min_=VOICE_STACK_BYTES;control_stack_free_min_=CONTROL_STACK_BYTES;codec_test_frames_=0;stack_limit_hit_=false;
        tts_=false;accept_audio_=false;command_=0;captured_=0;sent_=0;received_=0;played_=0;level_=0;peak_=0;mic0_=0;mic1_=0;
        {std::lock_guard<std::mutex> lock(mutex_);code_.clear();user_.clear();answer_.clear();error_.clear();stop_reason_.clear();}
        state(local_test?"Testing":"Connecting",local_test?"录音测试：请说话三秒":"正在连接小智");
        TaskHandle_t task=nullptr;
        if (xTaskCreatePinnedToCore([](void *ctx){static_cast<VoiceAssistant *>(ctx)->run();vTaskDelete(nullptr);},
                "voice_assistant",CONTROL_STACK_BYTES,this,4,&task,0)!=pdPASS) {
            local_audio::release(local_audio::Assistant);fail("内部内存不足，请稍后重试");live_=false;return std::unexpected("Audio task allocation failed");
        }
        return {};
    }
    void disconnect() {cancel_=true;accept_audio_=false;command_=0;if(live_)state("Stopping","正在关闭连接");}
    std::expected<void,std::string> command(int value) {
        if(value==1 && !child_mode_voice_allowed())return std::unexpected("语音采集已被家长限制");
        if (!live_ || cancel_ || !channel_ || fatal_) return std::unexpected("请先连接并激活小智");
        if(value==1&&stack_limit_hit_)return std::unexpected("栈保护已触发，请先断开再连接");
        // Preserve a queued command rather than silently overwrite rapid taps.
        int empty=0;if(!command_.compare_exchange_strong(empty,value))return std::unexpected("正在处理，请稍候");
        return {};
    }
    void on_stop() override {
        disconnect();
        while(live_)vTaskDelay(pdMS_TO_TICKS(20));
    }
    std::vector<FunctionSchema> get_function_schemas() override {
        return {{"Connect","Connect and obtain XiaoZhi activation code",{}},
                {"Disconnect","Cancel connection and release audio",{}},
                {"StartListening","Begin manual microphone upload",{}},
                {"StopListening","Finish microphone upload",{}},
                {"Interrupt","Stop the current answer",{}},
                {"TestMicrophone","Record and locally replay three seconds; no upload",{}},
                {"TestCodec","Encode/decode synthetic audio and measure stack; no capture/upload/playback",{}},
                {"GetState","Get assistant status",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Assistant state"}}};
    }
    FunctionHandlerList get_function_handlers() override {
        // The framework binds by position; legacy handler names are discarded.
        // Keep this list in exactly the same order as get_function_schemas().
        return {BROOKESIA_SERVICE_FUNC_HANDLER_0("Connect",launch(false)),
                {"Disconnect",[this](FunctionParameterMap &&)->FunctionResult{disconnect();return {.success=true};}},
                BROOKESIA_SERVICE_FUNC_HANDLER_0("StartListening",command(1)),
                BROOKESIA_SERVICE_FUNC_HANDLER_0("StopListening",command(2)),
                BROOKESIA_SERVICE_FUNC_HANDLER_0("Interrupt",command(3)),
                BROOKESIA_SERVICE_FUNC_HANDLER_0("TestMicrophone",launch(true)),
                BROOKESIA_SERVICE_FUNC_HANDLER_0("TestCodec",launch(2)),
                {"GetState",[this](FunctionParameterMap &&)->FunctionResult{return {.success=true,.data=FunctionValue(snapshot())};}}};
    }
    void close_recorder() {if(recording_){recorder_->close();recording_=false;}level_=0;}
    void close_player() {
        if(playing_){if(player_->is_pa_on_off_supported())player_->set_pa_on_off(false);player_->close();playing_=false;}
    }
    bool open_player() {
        if(playing_)return true;
        player_->close();
        if(!player_->open({.bits=16,.channels=1,.sample_rate=RATE})){fail("无法打开喇叭");return false;}
        playing_=true;
        if(player_->is_pa_on_off_supported())player_->set_pa_on_off(true);
        return true;
    }
    bool capture() {
        const auto &info=recorder_->get_info();
        if(info.sample_rate!=RATE || info.channels<1 || info.channels>4 || (info.bits!=16 && info.bits!=32)){
            fail("麦克风采样配置不兼容");return false;
        }
        const size_t bytes=FRAME*info.channels*(info.bits/8);
        if(!recorder_->read_data(raw_,bytes)){fail("麦克风读取失败");return false;}
        const size_t m=info.mic_layout.find('M');
        const unsigned channel=m<info.channels?m:info.channels-1;
        uint32_t peaks[4]={};uint64_t energy=0;
        for(int i=0;i<FRAME;++i){
            for(unsigned c=0;c<info.channels;++c){
                const int sample=info.bits==32?reinterpret_cast<int32_t *>(raw_)[i*info.channels+c]>>16:reinterpret_cast<int16_t *>(raw_)[i*info.channels+c];
                peaks[c]=std::max(peaks[c],static_cast<uint32_t>(std::abs(sample)));
                if(c==channel){pcm_[i]=sample;energy+=static_cast<int64_t>(sample)*sample;}
            }
        }
        mic0_=std::max(mic0_.load(),peaks[0]);mic1_=std::max(mic1_.load(),peaks[1]);
        peak_=std::max(peak_.load(),peaks[channel]);
        level_=std::min(100u,static_cast<unsigned>(std::sqrt(static_cast<double>(energy)/FRAME)*100/6000));
        captured_+=FRAME;return true;
    }
    bool prepare_audio() {
        auto recorders=hal::acquire_interfaces<hal::audio::CodecRecorderIface>();
        auto players=hal::acquire_interfaces<hal::audio::CodecPlayerIface>();
        if(recorders.empty()||players.empty()){fail("未找到麦克风或喇叭");return false;}
        recorder_=std::move(recorders.front());player_=std::move(players.front());
        raw_=static_cast<uint8_t *>(psram(FRAME*4*4));pcm_=static_cast<int16_t *>(psram(FRAME*2));
        encoded_=static_cast<uint8_t *>(psram(4096));decoded_=static_cast<uint8_t *>(psram(7680));
        packet_=static_cast<Packet *>(psram(sizeof(Packet)));
        queue_=static_cast<Packet *>(psram(sizeof(Packet)*QUEUE_SIZE));clear_queue();
        if(!raw_||!pcm_||!encoded_||!decoded_||!packet_||!queue_){fail("语音缓冲内存不足");return false;}
        return true;
    }
    bool prepare_opus() {
        // Semaphore storage stays with this permanently registered service, avoiding deletion
        // races with the codec task's last completion notification across repeated sessions.
        if(!codec_done_)codec_done_=xSemaphoreCreateBinary();
        if(!codec_done_){fail("无法创建编解码同步对象");return false;}
        while(xSemaphoreTake(codec_done_,0)==pdTRUE){}
        codec_live_=true;
        if(xTaskCreatePinnedToCoreWithCaps([](void *ctx){static_cast<VoiceAssistant *>(ctx)->codec_worker();vTaskDeleteWithCaps(nullptr);},
               "voice_codec",VOICE_STACK_BYTES,this,4,&codec_task_,0,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT)!=pdPASS){
            codec_live_=false;codec_task_=nullptr;fail("无法分配语音编解码任务");return false;
        }
        if(!codec_call(CodecOp::Open)){fail("语音编解码器初始化失败");return false;}
        return true;
    }
    bool codec_call(CodecOp operation) {
        if(!codec_live_||!codec_task_)return false;
        codec_op_=operation;
        xTaskNotifyGive(codec_task_);
        xSemaphoreTake(codec_done_,portMAX_DELAY);
        return codec_status_==ESP_AUDIO_ERR_OK;
    }
    void codec_worker() {
        // All codec entry points, including allocation/reset/close, stay on this stack.
        // This worker never accesses NVS, flash files, networking or the microphone.
        const auto completion=codec_done_;
        for(;;){
            ulTaskNotifyTake(pdTRUE,portMAX_DELAY);
            const auto operation=codec_op_;
            codec_status_=ESP_AUDIO_ERR_OK;
            if(operation==CodecOp::Open){
                esp_opus_enc_config_t enc=ESP_OPUS_ENC_CONFIG_DEFAULT();
                enc.sample_rate=RATE;enc.channel=1;enc.bitrate=24000;enc.frame_duration=ESP_OPUS_ENC_FRAME_DURATION_60_MS;enc.complexity=0;
                codec_status_=esp_opus_enc_open(&enc,sizeof(enc),&encoder_);
                if(codec_status_==ESP_AUDIO_ERR_OK){
                    esp_opus_dec_cfg_t dec=ESP_OPUS_DEC_CONFIG_DEFAULT();
                    dec.sample_rate=RATE;dec.channel=1;dec.frame_duration=ESP_OPUS_DEC_FRAME_DURATION_120_MS;
                    codec_status_=esp_opus_dec_open(&dec,sizeof(dec),&decoder_);
                }
            }else if(operation==CodecOp::Encode){
                esp_audio_enc_in_frame_t in{.buffer=reinterpret_cast<uint8_t *>(pcm_),.len=FRAME*2};
                esp_audio_enc_out_frame_t out{};out.buffer=encoded_;out.len=4096;
                codec_status_=esp_opus_enc_process(encoder_,&in,&out);encoded_size_=out.encoded_bytes;
            }else if(operation==CodecOp::Decode){
                esp_audio_dec_in_raw_t in{};in.buffer=packet_->data;in.len=packet_->len;
                esp_audio_dec_out_frame_t out{};out.buffer=decoded_;out.len=7680;
                esp_audio_dec_info_t info{};
                codec_status_=esp_opus_dec_decode(decoder_,&in,&out,&info);decoded_size_=out.decoded_size;
                if(codec_status_==ESP_AUDIO_ERR_OK&&in.consumed!=packet_->len)codec_status_=ESP_AUDIO_ERR_FAIL;
            }else if(operation==CodecOp::Reset){
                if(decoder_)codec_status_=esp_opus_dec_reset(decoder_);
            }else{
                if(encoder_){esp_opus_enc_close(encoder_);encoder_=nullptr;}
                if(decoder_){esp_opus_dec_close(decoder_);decoder_=nullptr;}
            }
            stack_free_min_=std::min(stack_free_min_.load(),static_cast<uint32_t>(uxTaskGetStackHighWaterMark(nullptr)));
            if(operation==CodecOp::Close){
                codec_live_=false;
                xSemaphoreGive(completion);
                return;
            }
            xSemaphoreGive(completion);
        }
    }
    void microphone_test() {
        auto *recording=static_cast<int16_t *>(psram(50*FRAME*2));
        if(!recording){fail("录音测试内存不足");return;}
        if(!recorder_->open()){heap_caps_free(recording);fail("无法打开麦克风");return;}
        recording_=true;
        for(int n=0;n<50&&!cancel_&&!fatal_;++n){if(!capture())break;memcpy(recording+n*FRAME,pcm_,FRAME*2);vTaskDelay(1);}
        close_recorder();
        if(!cancel_&&!fatal_){
            state("Testing","正在回放刚才的录音");
            if(open_player())for(int n=0;n<50&&!cancel_;++n){
                if(!player_->write_data(reinterpret_cast<uint8_t *>(recording+n*FRAME),FRAME*2)){fail("录音回放失败");break;}
                played_+=FRAME*2;vTaskDelay(1);
            }
        }
        heap_caps_free(recording);
        if(!fatal_&&!cancel_)state("Tested",peak_>20?"录音回放完成，请确认声音":"未检测到有效声音，请重试");
    }
    void codec_test() {
        state("Testing","正在运行本地编解码自检");
        if(!prepare_opus())return;
        for(unsigned n=0;n<120&&!cancel_;++n){
            // Exercise silence, a tone and bounded pseudo-noise without sampling the microphone.
            for(int i=0;i<FRAME;++i){
                const unsigned k=n*FRAME+i;
                pcm_[i]=n<40?0:n<80?static_cast<int16_t>(3000*std::sin(2*3.14159265*440*k/RATE)):
                    static_cast<int16_t>((k*1103515245u+12345u)>>18);
            }
            if(!codec_call(CodecOp::Encode)||!encoded_size_||encoded_size_>PACKET_MAX){fail("语音编码自检失败");return;}
            packet_->len=encoded_size_;memcpy(packet_->data,encoded_,encoded_size_);
            if(!codec_call(CodecOp::Decode)||decoded_size_!=FRAME*2){fail("语音解码自检失败");return;}
            ++codec_test_frames_;sample_stack();vTaskDelay(1);
        }
        if(!cancel_)state("Tested","本地编解码自检通过");
    }
    bool activate(bool &mqtt, bool &websocket) {
        for(int n=0;!cancel_ && n<60;++n){
            if(!wifi_ready()){fail("Wi-Fi 未连接，请先在设置中联网");return false;}
            state("Connecting","正在检查小智激活状态");
            esp_xiaozhi_chat_info_t info{};const auto result=esp_xiaozhi_chat_get_info(&info);
            const bool pending=info.has_activation_code||info.has_activation_challenge;
            mqtt=info.has_mqtt_config;websocket=info.has_websocket_config;
            {std::lock_guard<std::mutex> lock(mutex_);code_=short_text(info.activation_code,32);}
            esp_xiaozhi_chat_free_info(&info);
            if(cancel_)return false;
            if(result!=ESP_OK){fail("无法连接小智平台，请检查网络后重试");return false;}
            if(!pending&&(mqtt||websocket))return true;
            state("Activation","请在 xiaozhi.me 添加设备并输入激活码");
            for(int t=0;t<50&&!cancel_;++t)vTaskDelay(pdMS_TO_TICKS(100));
        }
        if(!cancel_)fail("激活等待超时，请重新连接获取激活码");
        return false;
    }
    void conversation() {
        bool mqtt=false,websocket=false;
        // Let the existing SNTP service establish a valid clock for TLS verification.
        for(int t=0;t<100&&!cancel_&&time(nullptr)<1700000000;++t)vTaskDelay(pdMS_TO_TICKS(100));
        if(cancel_||!activate(mqtt,websocket)||!prepare_opus())return;
        if(esp_event_handler_instance_register(ESP_XIAOZHI_CHAT_EVENTS,ESP_EVENT_ANY_ID,
            [](void *ctx,esp_event_base_t,int32_t id,void *){
                auto *s=static_cast<VoiceAssistant *>(ctx);
                if(id==ESP_XIAOZHI_CHAT_EVENT_CONNECTED)s->connected_=true;
                if(id==ESP_XIAOZHI_CHAT_EVENT_DISCONNECTED){s->connected_=false;if(s->channel_&&!s->cancel_)s->fail("连接已断开，请重新连接");}
                if(id==ESP_XIAOZHI_CHAT_EVENT_AUDIO_CHANNEL_CLOSED || id==ESP_XIAOZHI_CHAT_EVENT_SERVER_GOODBYE){
                    if(s->channel_&&!s->cancel_)s->fail("本次会话已结束，请重新连接");
                    s->channel_=false;
                }
            },this,&event_)!=ESP_OK){fail("无法注册语音事件");return;}
        esp_mcp_t *engine=nullptr;
        if(esp_mcp_create(&engine)!=ESP_OK){fail("语音协议初始化失败");return;}
        esp_xiaozhi_chat_config_t cfg=ESP_XIAOZHI_CHAT_DEFAULT_CONFIG();
        cfg.audio_callback=[](const uint8_t *d,int n,void *ctx){static_cast<VoiceAssistant *>(ctx)->receive(d,n);};
        cfg.event_callback=[](esp_xiaozhi_chat_event_t e,void *d,void *ctx){static_cast<VoiceAssistant *>(ctx)->on_chat(e,d);};
        cfg.audio_callback_ctx=this;cfg.event_callback_ctx=this;cfg.mcp_engine=engine;cfg.owns_mcp_engine=true;
        // Prefer secure WebSocket where supplied; the SDK also supports the platform's MQTT/UDP transport.
        cfg.has_websocket_config=websocket;cfg.has_mqtt_config=mqtt&&!websocket;
        if(esp_xiaozhi_chat_init(&cfg,&chat_)!=ESP_OK){esp_mcp_destroy(engine);fail("语音连接初始化失败");return;}
        state("Connecting","正在建立语音连接");
        if(esp_xiaozhi_chat_start(chat_)!=ESP_OK){fail("小智语音连接失败");return;}
        for(int t=0;t<150&&!cancel_&&!fatal_&&!connected_;++t)vTaskDelay(pdMS_TO_TICKS(100));
        if(cancel_||fatal_)return;
        if(!connected_){fail("小智连接超时，请重试");return;}
        esp_xiaozhi_chat_audio_t params{};
        params.format="opus";params.sample_rate=RATE;params.channels=1;params.frame_duration=60;
        if(esp_xiaozhi_chat_open_audio_channel(chat_,&params,nullptr,0)!=ESP_OK){fail("无法打开语音通道");return;}
        channel_=true;state("Ready","点击说话，再次点击发送");
        int64_t started=0,waiting=0;bool answering=false;uint32_t turn_packets=0;
        auto submit=[&](const char *reason){
            if(!recording_)return;
            close_recorder();
            {std::lock_guard<std::mutex> lock(mutex_);stop_reason_=reason;}
            if(!turn_packets){
                accept_audio_=false;waiting=0;
                esp_xiaozhi_chat_send_abort_speaking(chat_,ESP_XIAOZHI_CHAT_ABORT_SPEAKING_REASON_STOP_LISTENING);
                state("Ready",stack_limit_hit_?"栈保护已触发，请重新连接":"尚未采集到语音，请再试一次");return;
            }
            // Audio frames have already streamed to the server; stop completes that utterance.
            accept_audio_=true;waiting=esp_timer_get_time();
            if(esp_xiaozhi_chat_send_stop_listening(chat_)!=ESP_OK){fail("提交录音失败");return;}
            state("Thinking",stack_limit_hit_?"已达40KB栈限制，语音已提交":"正在思考");
        };
        while(!cancel_&&!fatal_){
            if(!child_mode_voice_allowed()){disconnect();break;}
            if(!wifi_ready()){fail("Wi-Fi 已断开，请联网后重新连接");break;}
            const int cmd=command_.exchange(0);
            if(cmd==1){
                if(stack_limit_reached()){state("Ready","栈保护已触发，请重新连接");continue;}
                accept_audio_=false;tts_=false;clear_queue();close_recorder();close_player();
                codec_call(CodecOp::Reset);
                esp_xiaozhi_chat_send_abort_speaking(chat_,ESP_XIAOZHI_CHAT_ABORT_SPEAKING_REASON_STOP_LISTENING);
                if(!recorder_->open()){fail("无法打开麦克风");break;}recording_=true;
                if(esp_xiaozhi_chat_send_start_listening(chat_,ESP_XIAOZHI_CHAT_LISTENING_MODE_MANUAL)!=ESP_OK){fail("开始录音失败");break;}
                {std::lock_guard<std::mutex> lock(mutex_);user_.clear();answer_.clear();}
                started=esp_timer_get_time();waiting=0;answering=false;turn_packets=0;state("Listening","正在聆听，点击发送");
            }
            if(cmd==2 || (recording_&&esp_timer_get_time()-started>30000000)){
                submit(cmd==2?"manual":"duration");
                if(fatal_)break;
            }
            if(cmd==3){
                accept_audio_=false;tts_=false;close_recorder();close_player();clear_queue();codec_call(CodecOp::Reset);
                esp_xiaozhi_chat_send_abort_speaking(chat_,ESP_XIAOZHI_CHAT_ABORT_SPEAKING_REASON_STOP_LISTENING);
                waiting=0;answering=false;state("Ready","已停止，点击继续说话");
            }
            if(recording_){
                if(stack_limit_reached()){submit("stack_limit");continue;}
                if(!capture())break;
                if(stack_limit_reached()){submit("stack_limit");continue;}
                if(!codec_call(CodecOp::Encode)||!encoded_size_){fail("语音编码失败");break;}
                const bool limit_hit=stack_limit_reached();
                if(cancel_)break;
                if(esp_xiaozhi_chat_send_audio_data(chat_,reinterpret_cast<const char *>(encoded_),encoded_size_)!=ESP_OK){fail("语音上传失败");break;}
                ++sent_;++turn_packets;
                if(limit_hit||stack_limit_reached())submit("stack_limit");
                vTaskDelay(1);continue;
            }
            if(pop()){
                if(!codec_call(CodecOp::Decode)){fail("语音解码失败");break;}
                if(!open_player())break;
                if(!player_->write_data(decoded_,decoded_size_)){fail("喇叭播放失败");break;}
                played_+=decoded_size_;sample_stack();answering=true;waiting=esp_timer_get_time();state("Speaking","正在回答");vTaskDelay(1);
            }else{
                if(answering&&!tts_&&esp_timer_get_time()-waiting>150000){
                    close_player();answering=false;waiting=0;accept_audio_=false;
                    state("Ready",stack_limit_hit_?"栈保护已触发，请重新连接后再说话":"点击继续说话");
                }
                if(waiting&&esp_timer_get_time()-waiting>60000000){fail("回答超时，请重新连接");break;}
                vTaskDelay(pdMS_TO_TICKS(10));
            }
        }
    }
    void run() {
        if(prepare_audio()) {sample_stack();if(local_test_==2)codec_test();else if(local_test_==1)microphone_test();else conversation();}
        accept_audio_=false;channel_=false;close_recorder();close_player();
        // Quiesce network callbacks before freeing their destination buffers.
        if(chat_){esp_xiaozhi_chat_stop(chat_);esp_xiaozhi_chat_deinit(chat_);chat_=0;}
        if(event_){esp_event_handler_instance_unregister(ESP_XIAOZHI_CHAT_EVENTS,ESP_EVENT_ANY_ID,event_);event_=nullptr;}
        if(codec_live_)codec_call(CodecOp::Close);
        codec_task_=nullptr;
        {std::lock_guard<std::mutex> lock(queue_mutex_);heap_caps_free(queue_);queue_=nullptr;head_=count_=0;}
        heap_caps_free(raw_);heap_caps_free(pcm_);heap_caps_free(encoded_);heap_caps_free(decoded_);heap_caps_free(packet_);
        raw_=encoded_=decoded_=nullptr;pcm_=nullptr;packet_=nullptr;recorder_.reset();player_.reset();
        connected_=false;channel_=false;level_=0;
        if(cancel_)state("Idle","已断开，点击重新连接");
        local_audio::release(local_audio::Assistant);live_=false;
    }
};
}
std::shared_ptr<ServiceBase> make_voice_assistant_service(){return std::make_shared<VoiceAssistant>();}
