#include "child_mode.hpp"
#include "policy.hpp"
#include "../audio_ownership.hpp"
#include <atomic>
#include <array>
#include <cmath>
#include <cstring>
#include <ctime>
#include <mutex>
#include "esp_random.h"
#include "esp_timer.h"
#include "nvs.h"
#include "psa/crypto.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "brookesia/system_core/system.hpp"
#include "brookesia/hal_interface/interface.hpp"
#include "brookesia/hal_interface/interfaces/audio/codec_player.hpp"
#include "brookesia/service_helper/media/audio.hpp"

using namespace esp_brookesia;
using namespace esp_brookesia::service;
namespace {
struct Preferences {
    uint32_t version=1, used_reserved=0, day=0;
    uint8_t enabled=0, mask=7, volume=30, minutes=30;
    uint8_t night=0, start=21, end=8, has_pin=0, failures=0;
    std::array<uint8_t,16> salt{};
    std::array<uint8_t,32> hash{};
};
std::mutex state_mutex;
Preferences prefs;
unsigned used=0;
std::string token,storage_error;
int64_t token_until=0,locked_until=0;
std::atomic<bool> ready{false},enabled{false},resting{false};
std::atomic<unsigned> mask{7},volume{30},revision{0},foreground{0},foreground_id{0};
std::atomic<system::core::System *> system_ptr{nullptr};
std::atomic<uint32_t> worker_stack_free{6144};

bool valid_pin(const std::string &pin) {
    return pin.size()==6 && pin.find_first_not_of("0123456789")==std::string::npos;
}
// PBKDF2-HMAC-SHA256, one 32-byte block, 10000 iterations. PIN never goes to disk.
bool derive(const std::string &pin,const std::array<uint8_t,16> &salt,std::array<uint8_t,32> &out) {
    if(psa_crypto_init()!=PSA_SUCCESS)return false;
    auto attributes=psa_key_attributes_init();
    psa_set_key_type(&attributes,PSA_KEY_TYPE_HMAC);
    psa_set_key_usage_flags(&attributes,PSA_KEY_USAGE_SIGN_MESSAGE);
    psa_set_key_algorithm(&attributes,PSA_ALG_HMAC(PSA_ALG_SHA_256));
    mbedtls_svc_key_id_t key=0;
    auto result=psa_import_key(&attributes,reinterpret_cast<const uint8_t *>(pin.data()),pin.size(),&key);
    psa_reset_key_attributes(&attributes);
    if(result!=PSA_SUCCESS)return false;
    const auto hmac=[&](const uint8_t *bytes,size_t size,uint8_t *output) {
        size_t written=0;
        return psa_mac_compute(key,PSA_ALG_HMAC(PSA_ALG_SHA_256),bytes,size,output,32,&written)==PSA_SUCCESS && written==32;
    };
    std::array<uint8_t,20> input{};
    std::copy(salt.begin(),salt.end(),input.begin());input[19]=1;
    std::array<uint8_t,32> u{};
    if(!hmac(input.data(),input.size(),u.data())){psa_destroy_key(key);return false;}
    out=u;
    for(unsigned i=1;i<10000;++i) {
        std::array<uint8_t,32> next{};
        if(!hmac(u.data(),u.size(),next.data())){psa_destroy_key(key);return false;}
        u=next;for(unsigned k=0;k<out.size();++k)out[k]^=u[k];
        if(i%256==0)vTaskDelay(1);
    }
    psa_destroy_key(key);return true;
}
bool crypto_self_test() {
    std::array<uint8_t,16> salt{};for(unsigned i=0;i<salt.size();++i)salt[i]=i;
    std::array<uint8_t,32> actual{};
    constexpr std::array<uint8_t,32> expected{0xe7,0xb2,0x8c,0xf2,0x15,0x98,0xb0,0x3d,0xc8,0x3d,0x4b,0x90,0x4b,0xa3,0x6f,0x7b,0xf0,0xf6,0x05,0xaf,0x31,0x34,0xc5,0x12,0x1f,0x28,0xf2,0x99,0x59,0x7e,0x81,0xc6};
    return derive("012345",salt,actual) && actual==expected;
}
bool save_locked() {
    nvs_handle_t h;
    esp_err_t e=nvs_open("ChildModeV1",NVS_READWRITE,&h);
    if(e==ESP_OK) {
        e=nvs_set_blob(h,"policy",&prefs,sizeof(prefs));
        if(e==ESP_OK)e=nvs_commit(h);
        nvs_close(h);
    }
    storage_error=e==ESP_OK?"":"设置保存失败，请重试";
    return e==ESP_OK;
}
std::pair<uint32_t,int> local_clock() {
    const time_t now=time(nullptr);
    if(now<1735689600)return {0,-1};
    // Existing desktop uses Beijing time independent of the process TZ.
    const time_t beijing=now+8*3600;struct tm t{};gmtime_r(&beijing,&t);
    return {static_cast<uint32_t>((t.tm_year+1900)*10000+(t.tm_mon+1)*100+t.tm_mday),t.tm_hour};
}
void publish_locked() {
    enabled=prefs.enabled!=0;mask=prefs.mask;volume=prefs.volume;
    const auto [day,hour]=local_clock();
    resting=prefs.enabled && (!storage_error.empty() || (prefs.minutes && used>=unsigned(prefs.minutes)*60) ||
            (prefs.night && (hour<0 || child_policy::night(hour,prefs.start,prefs.end))));
}
bool authorize_locked(const std::string &candidate) {
    if(token.empty() || candidate!=token || esp_timer_get_time()>=token_until)return false;
    token_until=esp_timer_get_time()+60000000;return true;
}
FunctionResult failed(const char *message) {return {.success=false,.error_message=message};}
FunctionResult auth_result_locked() {
    std::array<uint8_t,24> random{};esp_fill_random(random.data(),random.size());
    static constexpr char HEX[]="0123456789abcdef";token.clear();
    for(auto byte:random) {token+=HEX[byte>>4];token+=HEX[byte&15];}
    token_until=esp_timer_get_time()+60000000;
    return {.success=true,.data=FunctionValue(boost::json::object{{"token",token}})};
}
void apply_volume_cap() {
    if(!enabled)return;
    using Audio=service::helper::AudioPlayback;
    auto current=Audio::call_function_sync<double>(Audio::FunctionId::GetVolume,service::helper::Timeout(2000));
    if(current)(void)Audio::call_function_sync(Audio::FunctionId::SetVolume,*current,service::helper::Timeout(2000));
}
class ChildMode final : public ServiceBase {
public:
    ChildMode():ServiceBase({.name="ChildMode",.description="PIN protected child desktop policy",.version="0.1.0",.dependencies={}}){}
private:
    std::atomic<bool> live_{false},stop_{false},initialized_{false};
    bool initialize() {
        if(!crypto_self_test())return false;
        {
            std::lock_guard<std::mutex> lock(state_mutex);
            nvs_handle_t h;auto e=nvs_open("ChildModeV1",NVS_READONLY,&h);
            if(e==ESP_OK) {
                size_t size=sizeof(prefs);e=nvs_get_blob(h,"policy",&prefs,&size);nvs_close(h);
                if(e==ESP_ERR_NVS_NOT_FOUND){prefs=Preferences{};e=ESP_OK;size=sizeof(prefs);}
                if(e!=ESP_OK || size!=sizeof(prefs) || prefs.version!=1 || prefs.volume>60 ||
                        prefs.minutes>120 || prefs.start>23 || prefs.end>23 || prefs.mask>15 ||
                        (prefs.enabled && !prefs.has_pin))return false;
            } else if(e!=ESP_ERR_NVS_NOT_FOUND)return false;
            used=prefs.used_reserved;
            if(prefs.failures>=5)locked_until=esp_timer_get_time()+60000000;
            publish_locked();ready=true;
        }
        return true;
    }
    bool on_start() override {
        // Even NVS blob reads can disable the cache. Startup is invoked from a
        // PSRAM setup thread, so all initialization belongs to the internal task.
        live_=true;stop_=false;initialized_=false;
        if(xTaskCreatePinnedToCore([](void *p){static_cast<ChildMode *>(p)->run();vTaskDelete(nullptr);},
                "child_policy",6144,this,1,nullptr,0)!=pdPASS){live_=false;ready=false;return false;}
        while(!initialized_)vTaskDelay(pdMS_TO_TICKS(10));
        return ready;
    }
    void on_stop() override {stop_=true;while(live_)vTaskDelay(pdMS_TO_TICKS(10));}
    void run() {
        if(!initialize()){ready=false;initialized_=true;live_=false;return;}
        initialized_=true;
        while(!stop_) {
            {
                std::lock_guard<std::mutex> lock(state_mutex);
                const auto [day,hour]=local_clock();
                bool changed=false;
                if(day && day>prefs.day) {
                    if(prefs.day) {used=0;prefs.used_reserved=0;}
                    prefs.day=day;changed=true;
                }
                if(prefs.enabled && (foreground || local_audio::owner!=local_audio::Free) && !resting) {
                    ++used;
                    const auto reserve=child_policy::reserve(used);
                    if(reserve>prefs.used_reserved) {prefs.used_reserved=reserve;changed=true;}
                }
                if(changed && !save_locked())resting=true;
                publish_locked();
                if(!storage_error.empty() && prefs.enabled)resting=true;
            }
            const auto app=foreground_id.load();
            const auto bit=foreground.load();
            if(enabled && bit && (resting || !(mask.load()&bit))) {
                if(auto *sys=system_ptr.load();sys && app) {
                    (void)sys->stop_app(app);
                }
            }
            worker_stack_free=std::min(worker_stack_free.load(),static_cast<uint32_t>(uxTaskGetStackHighWaterMark(nullptr)));
            vTaskDelay(pdMS_TO_TICKS(1000));
        }
        live_=false;
    }
    FunctionResult state() {
        std::lock_guard<std::mutex> lock(state_mutex);
        publish_locked();
        const auto [day,hour]=local_clock();
        const unsigned remaining=prefs.minutes?std::max(0,int(prefs.minutes)*60-int(used)):0;
        boost::json::object o{{"configured",prefs.has_pin!=0},{"enabled",prefs.enabled!=0},
            {"allow_audiobook",(prefs.mask&1)!=0},{"allow_weather",(prefs.mask&2)!=0},
            {"allow_clock",(prefs.mask&4)!=0},{"allow_assistant",(prefs.mask&8)!=0},
            {"max_volume",prefs.volume},{"daily_minutes",prefs.minutes},{"used_seconds",used},
            {"remaining_seconds",remaining},{"night_enabled",prefs.night!=0},
            {"night_start",prefs.start},{"night_end",prefs.end},{"clock_ready",day!=0},
            {"resting",resting.load()},{"locked_seconds",std::max<int64_t>(0,(locked_until-esp_timer_get_time()+999999)/1000000)},
            {"error",storage_error},{"worker_stack_free_min_bytes",worker_stack_free.load()}};
        return {.success=true,.data=FunctionValue(std::move(o))};
    }
    FunctionResult login(FunctionParameterMap &&p,bool setup) {
        const auto pin=std::get<std::string>(p.at("Pin"));
        if(!valid_pin(pin))return failed("请输入六位数字 PIN");
        std::lock_guard<std::mutex> lock(state_mutex);
        if(setup && prefs.has_pin)return failed("PIN 已设置，请先验证");
        if(!setup && !prefs.has_pin)return failed("请先设置家长 PIN");
        if(esp_timer_get_time()<locked_until)return failed("尝试次数过多，请一分钟后再试");
        std::array<uint8_t,32> hash{};
        auto salt=prefs.salt;
        if(setup)esp_fill_random(salt.data(),salt.size());
        if(!derive(pin,salt,hash))return failed("PIN 校验暂不可用");
        uint8_t diff=0;for(unsigned i=0;i<hash.size();++i)diff|=hash[i]^prefs.hash[i];
        if(!setup && diff) {
            if(++prefs.failures>=5){locked_until=esp_timer_get_time()+60000000;prefs.failures=5;}
            save_locked();return failed("PIN 不正确");
        }
        const auto old=prefs;
        if(setup){prefs.salt=salt;prefs.hash=hash;prefs.has_pin=1;}
        prefs.failures=0;
        if(!save_locked()){prefs=old;return failed("PIN 保存失败，请重试");}
        return auth_result_locked();
    }
    FunctionResult configure(FunctionParameterMap &&p) {
        const auto settings=std::get<boost::json::object>(p.at("Settings"));
        {
            std::lock_guard<std::mutex> lock(state_mutex);
            if(!authorize_locked(std::get<std::string>(p.at("Token"))))return failed("请重新验证家长 PIN");
            auto next=prefs;
            auto number=[&](const char *key,int low,int high,uint8_t &v) {
                auto it=settings.find(key);if(it==settings.end())return true;
                if(!it->value().is_number())return false;
                double n=boost::json::value_to<double>(it->value());
                if(!std::isfinite(n) || n<low || n>high || n!=std::floor(n))return false;
                v=static_cast<uint8_t>(n);return true;
            };
            auto boolean=[&](const char *key,uint8_t &v) {
                auto it=settings.find(key);if(it==settings.end())return true;
                if(!it->value().is_bool())return false;
                v=it->value().as_bool();return true;
            };
            if(!boolean("enabled",next.enabled) || !boolean("night_enabled",next.night) ||
                    !number("max_volume",10,60,next.volume) || !number("daily_minutes",0,120,next.minutes) ||
                    !number("night_start",0,23,next.start) || !number("night_end",0,23,next.end))return failed("设置数值无效");
            for(const auto &[key,bit]:std::initializer_list<std::pair<const char *,unsigned>>{
                    {"allow_audiobook",1},{"allow_weather",2},{"allow_clock",4},{"allow_assistant",8}}) {
                uint8_t on=(next.mask&bit)!=0;
                if(!boolean(key,on))return failed("应用开关无效");
                if(on)next.mask|=bit;else next.mask&=~bit;
            }
            if(next.enabled && !next.has_pin)return failed("请先设置家长 PIN");
            if(next.night && next.start==next.end)return failed("休息开始和结束时间不能相同");
            const auto old=prefs;prefs=next;
            if(!save_locked()){prefs=old;return failed("设置保存失败，请重试");}
            publish_locked();++revision;
        }
        apply_volume_cap();return {.success=true};
    }
    FunctionResult protected_action(FunctionParameterMap &&p,int operation) {
        std::lock_guard<std::mutex> lock(state_mutex);
        if(!authorize_locked(std::get<std::string>(p.at("Token"))))return failed("请重新验证家长 PIN");
        if(operation==0){token.clear();token_until=0;return {.success=true};}
        const auto old=prefs;const auto old_used=used;
        if(operation==1){used=0;prefs.used_reserved=0;}
        if(operation==2) {
            const auto pin=std::get<std::string>(p.at("Pin"));
            if(!valid_pin(pin))return failed("请输入六位数字 PIN");
            esp_fill_random(prefs.salt.data(),prefs.salt.size());
            if(!derive(pin,prefs.salt,prefs.hash)){prefs=old;return failed("PIN 处理失败");}
        }
        if(operation==3) {
            if(prefs.enabled)return failed("请先关闭儿童模式");
            prefs.has_pin=0;prefs.hash.fill(0);prefs.salt.fill(0);prefs.failures=0;
            locked_until=0;token.clear();
        }
        if(!save_locked()){prefs=old;used=old_used;return failed("保存失败，请重试");}
        publish_locked();return {.success=true};
    }
    std::vector<FunctionSchema> get_function_schemas() override {
        const FunctionReturnSchema object{FunctionValueType::Object,"Child policy"};
        return {{"GetState","Get public child settings",{},true,std::nullopt,object},
            {"SetupPin","Set first six digit parent PIN",{{"Pin","PIN",FunctionValueType::String}},true,std::nullopt,object},
            {"VerifyPin","Verify parent PIN",{{"Pin","PIN",FunctionValueType::String}},true,std::nullopt,object},
            {"Configure","Save authorized settings",{{"Token","Session",FunctionValueType::String},{"Settings","Options",FunctionValueType::Object}}},
            {"Lock","End parent session",{{"Token","Session",FunctionValueType::String}}},
            {"ResetUsage","Reset today's usage",{{"Token","Session",FunctionValueType::String}}},
            {"ChangePin","Change parent PIN",{{"Token","Session",FunctionValueType::String},{"Pin","New PIN",FunctionValueType::String}}},
            {"ClearPin","Remove PIN only with authorization and child mode off",{{"Token","Session",FunctionValueType::String}}}};
    }
    FunctionHandlerList get_function_handlers() override {
        return {{"GetState",[this](FunctionParameterMap &&){return state();}},
            {"SetupPin",[this](FunctionParameterMap &&p){return login(std::move(p),true);}},
            {"VerifyPin",[this](FunctionParameterMap &&p){return login(std::move(p),false);}},
            {"Configure",[this](FunctionParameterMap &&p){return configure(std::move(p));}},
            {"Lock",[this](FunctionParameterMap &&p){return protected_action(std::move(p),0);}},
            {"ResetUsage",[this](FunctionParameterMap &&p){return protected_action(std::move(p),1);}},
            {"ChangePin",[this](FunctionParameterMap &&p){return protected_action(std::move(p),2);}},
            {"ClearPin",[this](FunctionParameterMap &&p){return protected_action(std::move(p),3);}}};
    }
};
}
std::shared_ptr<ServiceBase> make_child_mode_service(){return std::make_shared<ChildMode>();}
void child_mode_attach_system(system::core::System *system){system_ptr=system;}
bool child_mode_voice_allowed(){return ready && (!enabled || ((mask.load()&8) && !resting));}
bool child_mode_audiobook_allowed(){return ready && (!enabled || ((mask.load()&1) && !resting));}
extern "C" bool brookesia_child_visible(const char *id) {
    return child_policy::administrative(id) || (ready && child_policy::visible(enabled,mask,id));
}
extern "C" const char *brookesia_child_launch_error(const char *id) {
    if(child_policy::administrative(id))return nullptr;
    if(!ready)return "儿童模式正在初始化";
    if(!enabled)return nullptr;
    if(!child_policy::visible(true,mask,id))return "该应用未获家长授权";
    if(resting)return "现在是休息时间，请到儿童模式查看或由家长调整";
    return nullptr;
}
extern "C" unsigned brookesia_child_revision(){return revision;}
extern "C" void brookesia_child_foreground(const char *id,unsigned app_id) {
    foreground=child_policy::app_bit(id);foreground_id=app_id;
}
extern "C" int brookesia_child_cap_volume(int requested) {
    return enabled ? std::min(requested,int(volume.load())) : requested;
}
extern "C" bool brookesia_child_requires_internal(const char *id) {
    return std::strcmp(id,"local.childmode")==0;
}
