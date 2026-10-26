#include "device_modes.hpp"
#include <atomic>
#include <algorithm>
#include <ctime>
#include <cmath>
#include "quiet_hours.hpp"
#include "brookesia/hal_interface.hpp"
#include "brookesia/gui_lvgl.hpp"
#include "esp_board_manager.h"
#include "dev_display_lcd.h"
#include "esp_board_manager_includes.h"
#include "esp_codec_dev.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lv_adapter.h"
#include "esp_timer.h"
#include "esp_app_desc.h"
#include "nvs.h"
#include "lvgl.h"
#include "../display.hpp"
#include "deep_sleep.hpp"
#include "idle_deep_sleep.hpp"
#include "screen_lock.hpp"
#include "../audio_ownership.hpp"
#include "../audiobook/audiobook.hpp"
#include "driver/gpio.h"
#include "esp_attr.h"
#include "brookesia/hal_interface/interfaces/display/backlight.hpp"
#include "brookesia/service_helper/media/audio.hpp"

extern "C" int brookesia_child_cap_volume(int);

using namespace esp_brookesia;
using namespace esp_brookesia::service;
namespace {
constexpr uint32_t IDLE_MS = 600000;
std::atomic<bool> ready{false}, automatic{true}, dnd{true}, asleep{false};
std::atomic<bool> wake_requested{false}, sleep_requested{false}, consume_touch{false};
std::atomic<bool> dirty{false}, audio_dirty{false};
std::atomic<int> desired_volume{75};
std::atomic<uint32_t> key_applied{0};std::atomic<int> key_last_gpio{-1},key_last_target{-1};
std::atomic<bool> manual_dnd{false},quiet_enabled{false};
std::atomic<int> quiet_start{1320},quiet_end{420};
std::atomic<int> deep_minutes{0};
std::atomic<uint32_t> deep_activity_ms{0};
std::atomic<bool> preferences_loaded{false},test_idle_deep{false};
std::atomic<int> story_dim{1000};
std::atomic<bool> offline_enabled{false};
std::atomic<unsigned> key_presses{0};
std::atomic<bool> keys_ready{false},keys_reinitialize{false};
std::atomic<bool> screen_locked{false},lock_reset{false};
std::atomic<unsigned> lock_count{0},unlock_count{0},unlock_taps{0},locked_touches{0};
screen_lock::DoublePress unlock_pattern;
int local_minute(){const time_t now=time(nullptr);if(now<1735689600)return -1;const time_t local=now+8*3600;tm t{};gmtime_r(&local,&t);return t.tm_hour*60+t.tm_min;}
void update_quiet(){const bool active=manual_dnd || (quiet_enabled && quiet_hours::contains(local_minute(),quiet_start,quiet_end));if(dnd.exchange(active)!=active)audio_dirty=true;}
std::atomic<uint32_t> last_touch_ms{0}, sleeps{0}, wakes{0}, swallowed{0}, panel_errors{0};
uint32_t now_ms() { return static_cast<uint32_t>(esp_timer_get_time()/1000); }

class DeviceModes final : public ServiceBase {
public:
    DeviceModes():ServiceBase({.name="DeviceModes",.description="Ten minute screen timeout and do not disturb",
                              .version="0.1.0",.dependencies={}}) {}
private:
    bool on_start() override {
        ready=true;return true;
    }
    boost::json::object state() {
        uint8_t brightness=0;auto backlight=hal::acquire_first_interface<hal::display::BacklightIface>();
        const bool brightness_valid=backlight && backlight->get_brightness(brightness);
        return {{"firmware_version",esp_app_get_description()->version},
                {"deep_sleep",board_deep_sleep_state()},{"auto_sleep_enabled",automatic.load()},{"timeout_seconds",600},
                {"auto_deep_sleep_minutes",deep_minutes.load()},{"auto_deep_sleep_audio_busy",local_audio::busy()},
                {"auto_deep_sleep_remaining_seconds",idle_deep_sleep::remaining(now_ms(),deep_activity_ms.load(),deep_minutes.load()*60)},
                {"preferences_loaded",preferences_loaded.load()},{"test_idle_deep_sleep",test_idle_deep.load()},
                {"brightness_percent",brightness_valid?int(brightness):-1},{"story_dim_per_mille",story_dim.load()},{"volume_keys_ready",keys_ready.load()},{"volume_key_presses",key_presses.load()},{"volume_key_applied",key_applied.load()},{"volume_key_last_gpio",key_last_gpio.load()},{"volume_key_last_target",key_last_target.load()},
                {"screen_asleep",asleep.load()},{"screen_locked",screen_locked.load()},
                {"screen_lock_count",lock_count.load()},{"screen_unlock_count",unlock_count.load()},
                {"screen_unlock_taps",unlock_taps.load()},{"locked_touches",locked_touches.load()},
                {"do_not_disturb",dnd.load()},
                {"manual_do_not_disturb",manual_dnd.load()},{"quiet_hours_enabled",quiet_enabled.load()},
                {"quiet_start_minute",quiet_start.load()},{"quiet_end_minute",quiet_end.load()},
                {"local_minute",local_minute()},{"clock_synced",local_minute()>=0},{"timezone","Asia/Shanghai"},
                {"idle_seconds",(now_ms()-last_touch_ms.load())/1000},
                {"wake_touch_consumed",swallowed.load()},{"sleep_count",sleeps.load()},
                {"wake_count",wakes.load()},{"panel_errors",panel_errors.load()},
                {"pending_save",dirty.load()},{"audio_pending",audio_dirty.load()},
                {"resume_volume",desired_volume.load()}};
    }
    FunctionResult speaker_volume(){
        void *handle=nullptr;
        if(esp_board_manager_get_device_handle("audio_dac",&handle)!=ESP_OK || !handle)
            return {.success=false,.error_message="Audio DAC unavailable"};
        auto codec=static_cast<dev_audio_codec_handles_t *>(handle)->codec_dev;
        int volume=-1,reg=-1;bool muted=false;
        const bool valid=esp_codec_dev_get_out_vol(codec,&volume)==ESP_CODEC_DEV_OK;
        const bool read=esp_codec_dev_read_reg(codec,0x32,&reg)==ESP_CODEC_DEV_OK;
        const bool mute_valid=esp_codec_dev_get_out_mute(codec,&muted)==ESP_CODEC_DEV_OK;
        return {.success=true,.data=FunctionValue(boost::json::object{{"codec_open",valid},{"codec_volume",volume},
            {"dac_register_valid",read},{"dac_volume_register",reg},{"mute_valid",mute_valid},{"muted",muted}})};
    }
    FunctionResult visual_layers(){
        if(esp_lv_adapter_lock(100)!=ESP_OK)return {.success=false,.error_message="GUI busy"};
        boost::json::array layers;unsigned order=0;
        auto visit=[&](auto &&self,lv_obj_t *object,int depth,int inherited)->void{
            if(!object || depth>32 || lv_obj_has_flag(object,LV_OBJ_FLAG_HIDDEN))return;
            const int opacity=lv_obj_get_style_opa(object,LV_PART_MAIN);
            const int effective=inherited*opacity/255;
            const auto color=lv_color_to_u32(lv_obj_get_style_bg_color(object,LV_PART_MAIN)) & 0xffffff;
            const int bg=lv_obj_get_style_bg_opa(object,LV_PART_MAIN);
            lv_area_t area{};lv_obj_get_coords(object,&area);const int w=lv_area_get_width(&area),h=lv_area_get_height(&area);
            const char *kind=color==0x020913?"shade":color==0xd3e9ff?"moon":color==0xffce65?"sun":color==0xadc1d3?"cloud":"surface";
            ++order;
            if(layers.size()<32 && lv_obj_check_type(object,&lv_image_class) && w==486 && h==486){
                const auto *source=lv_image_get_src(object);
                const auto *image=source && lv_image_src_get_type(source)==LV_IMAGE_SRC_VARIABLE?static_cast<const lv_image_dsc_t *>(source):nullptr;
                layers.push_back(boost::json::object{{"kind","wallpaper"},{"x",area.x1},{"y",area.y1},
                    {"width",w},{"height",h},{"effective_opacity",effective},
                    {"pixel_format",image?int(image->header.cf):0},{"source_width",image?int(image->header.w):0},
                    {"source_height",image?int(image->header.h):0},{"scale_x",lv_image_get_scale_x(object)},
                    {"scale_y",lv_image_get_scale_y(object)}});
            }
            if(layers.size()<32 && lv_obj_check_type(object,&lv_dropdown_class)){
                const auto count=lv_dropdown_get_option_count(object);
                if(count==4 || count==24 || count==60){
                    const auto font=lv_obj_get_style_text_font(object,LV_PART_MAIN);
                    auto *list=lv_dropdown_get_list(object);const auto popup=lv_obj_get_style_text_font(list,LV_PART_MAIN);
                    const auto selected=lv_obj_get_style_text_font(list,LV_PART_SELECTED);
                    char text[24]{};lv_dropdown_get_selected_str(object,text,sizeof(text));
                    layers.push_back(boost::json::object{{"kind",count==4?"sleep_picker":"time_picker"},{"options",count},{"selected",lv_dropdown_get_selected(object)},
                        {"text",text},{"font_height",font?font->line_height:0},{"popup_font_height",popup?popup->line_height:0},
                        {"selected_font_height",selected?selected->line_height:0},{"symbol_present",lv_dropdown_get_symbol(object)!=nullptr},
                        {"background_rgb",color},{"text_rgb",lv_color_to_u32(lv_obj_get_style_text_color(object,LV_PART_MAIN)) & 0xffffff},
                        {"popup_background_rgb",lv_color_to_u32(lv_obj_get_style_bg_color(list,LV_PART_MAIN)) & 0xffffff},
                        {"popup_text_rgb",lv_color_to_u32(lv_obj_get_style_text_color(list,LV_PART_MAIN)) & 0xffffff},
                        {"selected_background_rgb",lv_color_to_u32(lv_obj_get_style_bg_color(list,LV_PART_SELECTED)) & 0xffffff},
                        {"selected_text_rgb",lv_color_to_u32(lv_obj_get_style_text_color(list,LV_PART_SELECTED)) & 0xffffff}});
                }
            }
            if(layers.size()<32 && effective>0 && bg>0 && (kind[0]!='s' || color==0x020913 || color==0xffce65 || (w>=400 && h>=400))){
                layers.push_back(boost::json::object{{"kind",kind},{"order",order},{"x",area.x1},{"y",area.y1},{"width",w},{"height",h},
                    {"opacity",opacity},{"effective_opacity",effective},{"background_opacity",bg},{"rgb",color}});
            }
            for(uint32_t i=0;i<lv_obj_get_child_count(object);++i)self(self,lv_obj_get_child(object,i),depth+1,effective);
        };
        visit(visit,lv_layer_bottom(),0,255);visit(visit,lv_screen_active(),0,255);visit(visit,lv_layer_top(),0,255);visit(visit,lv_layer_sys(),0,255);
        esp_lv_adapter_unlock();return {.success=true,.data=FunctionValue(boost::json::object{{"layers",std::move(layers)}})};
    }
    std::vector<FunctionSchema> get_function_schemas() override {
        return {{"GetSpeakerVolume","Read actual codec volume, mute and DAC register",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Speaker volume diagnostics"}},
                {"ProfileRefresh","Measure native full-screen refresh",{{"Force","Force one whole-screen redraw",FunctionValueType::Boolean}},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Refresh timing"}},
                {"GetWeatherLayers","Read visible native layer opacity for weather diagnostics",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Visible surfaces"}},
                {"GetState","Get screen and sound mode state",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Modes"}},
                {"SetAutoSleep","Enable ten minute inactivity timeout",{{"Enabled","Enabled",FunctionValueType::Boolean}}},
                {"SetDoNotDisturb","Mute speaker while retaining its volume",{{"Enabled","Enabled",FunctionValueType::Boolean}}},
                {"SetQuietHours","Set daily quiet hours in Beijing time",{{"Enabled","Schedule enabled",FunctionValueType::Boolean},{"StartMinute","0-1439 inclusive",FunctionValueType::Number},{"EndMinute","0-1439 exclusive; equal means all day",FunctionValueType::Number}}},
                {"SleepNow","Turn screen off without stopping apps",{}},
                {"LockScreen","Lock touch and turn screen off; double press volume+ to unlock",{}},
                {"Wake","Wake screen for maintenance",{}},
                {"DeepSleepNow","Stop apps and enter deep sleep; touch/key wakes",{}},
                {"TestDeepSleep","Deep sleep with a 20 second recovery timer",{}},
                {"SetAutoDeepSleep","Set idle duration: 0,10,20,30,60,120,240 minutes",{{"Minutes","0 disables",FunctionValueType::Number}}},
                {"TestIdleDeepSleep","Exercise idle policy after five quiet seconds with twenty second recovery",{}}};
    }
    FunctionHandlerList get_function_handlers() override {
        return {{"GetSpeakerVolume",[this](FunctionParameterMap &&)->FunctionResult{return speaker_volume();}},
                {"ProfileRefresh",[](FunctionParameterMap &&p)->FunctionResult{
                    if(esp_lv_adapter_lock(1000)!=ESP_OK)return {.success=false,.error_message="GUI busy"};
                    auto result=board_display_profile(std::get<bool>(p.at("Force")));
                    esp_lv_adapter_unlock();return {.success=true,.data=FunctionValue(std::move(result))};}},
                {"GetWeatherLayers",[this](FunctionParameterMap &&)->FunctionResult{return visual_layers();}},
                {"GetState",[this](FunctionParameterMap &&)->FunctionResult{return {.success=true,.data=FunctionValue(state())};}},
                {"SetAutoSleep",[](FunctionParameterMap &&p)->FunctionResult{brookesia_board_set_auto_sleep(std::get<bool>(p.at("Enabled")));return {.success=true};}},
                {"SetDoNotDisturb",[](FunctionParameterMap &&p)->FunctionResult{brookesia_board_set_do_not_disturb(std::get<bool>(p.at("Enabled")));return {.success=true};}},
                {"SetQuietHours",[](FunctionParameterMap &&p)->FunctionResult{
                    const double a=std::get<double>(p.at("StartMinute")),b=std::get<double>(p.at("EndMinute"));
                    if(!std::isfinite(a)||!std::isfinite(b)||a<0||a>=1440||b<0||b>=1440||std::floor(a)!=a||std::floor(b)!=b)return {.success=false,.error_message="Times must be whole minutes from 0 to 1439"};
                    brookesia_board_set_quiet_hours(std::get<bool>(p.at("Enabled")),int(a),int(b));return {.success=true};}},
                {"SleepNow",[](FunctionParameterMap &&)->FunctionResult{sleep_requested=true;return {.success=true};}},
                {"LockScreen",[](FunctionParameterMap &&)->FunctionResult{
                    if(brookesia_board_deep_sleep_pending())return {.success=false,.error_message="Device is entering deep sleep"};
                    if(!keys_ready)return {.success=false,.error_message="Volume keys are not ready"};
                    if(!screen_locked.exchange(true))++lock_count;
                    lock_reset=true;unlock_taps=0;wake_requested=false;sleep_requested=true;
                    return {.success=true};}},
                {"Wake",[](FunctionParameterMap &&)->FunctionResult{wake_requested=true;return {.success=true};}},
                {"DeepSleepNow",[](FunctionParameterMap &&)->FunctionResult{const auto e=brookesia_board_request_deep_sleep(0);return {.success=e==ESP_OK,.error_message=e==ESP_OK?"":esp_err_to_name(e)};}},
                {"TestDeepSleep",[](FunctionParameterMap &&)->FunctionResult{const auto e=brookesia_board_request_deep_sleep(20);return {.success=e==ESP_OK,.error_message=e==ESP_OK?"":esp_err_to_name(e)};}},
                {"SetAutoDeepSleep",[](FunctionParameterMap &&p)->FunctionResult{
                    const double value=std::get<double>(p.at("Minutes"));
                    if(!std::isfinite(value) || value<0 || value>240 || std::floor(value)!=value ||
                       !brookesia_board_set_auto_deep_sleep_index(idle_deep_sleep::index(int(value))))
                        return {.success=false,.error_message="Use 0,10,20,30,60,120,240 minutes after preferences load"};
                    return {.success=true};}},
                {"TestIdleDeepSleep",[](FunctionParameterMap &&)->FunctionResult{
                    if(!preferences_loaded || brookesia_board_deep_sleep_pending())return {.success=false,.error_message="Device is not ready"};
                    deep_activity_ms=now_ms();test_idle_deep=true;return {.success=true};}}};
    }
};
}

std::shared_ptr<ServiceBase> make_device_modes_service(){return std::make_shared<DeviceModes>();}
extern "C" void brookesia_board_volume_keys_resume(){keys_reinitialize=true;}
extern "C" void brookesia_board_story_dim(int value){story_dim=std::clamp(value,100,1000);}
extern "C" void brookesia_board_story_sleep_done(){story_dim=1000;sleep_requested=true;}
extern "C" bool brookesia_board_screen_asleep(){return asleep;}
extern "C" bool brookesia_board_do_not_disturb(){return dnd;}
extern "C" bool brookesia_board_auto_sleep_enabled(){return automatic;}
extern "C" void brookesia_board_set_auto_sleep(bool on){automatic=on;dirty=true;wake_requested=true;}
extern "C" int brookesia_board_auto_deep_sleep_index(){return std::max(0,idle_deep_sleep::index(deep_minutes.load()));}
extern "C" bool brookesia_board_set_auto_deep_sleep_index(int index){
    if(!preferences_loaded || index<0 || unsigned(index)>=idle_deep_sleep::minutes.size())return false;
    deep_minutes=idle_deep_sleep::minutes[index];deep_activity_ms=now_ms();test_idle_deep=false;dirty=true;return true;
}
extern "C" void brookesia_board_set_do_not_disturb(bool on){manual_dnd=on;update_quiet();dirty=true;audio_dirty=true;}
extern "C" bool brookesia_board_manual_dnd(){return manual_dnd;}
extern "C" bool brookesia_board_quiet_enabled(){return quiet_enabled;}
extern "C" int brookesia_board_quiet_start(){return quiet_start;}
extern "C" int brookesia_board_quiet_end(){return quiet_end;}
extern "C" int brookesia_board_local_minute(){return local_minute();}
extern "C" void brookesia_board_set_quiet_hours(bool on,int start,int end){
    if(start<0 || start>=1440 || end<0 || end>=1440)return;
    quiet_start=start;quiet_end=end;quiet_enabled=on;update_quiet();dirty=true;
}
extern "C" bool brookesia_board_offline_voice_enabled(){return preferences_loaded && offline_enabled;}
extern "C" void brookesia_board_set_offline_voice(bool value){offline_enabled=value;dirty=true;}
extern "C" int brookesia_board_user_volume(){return preferences_loaded?desired_volume.load():-1;}
extern "C" int brookesia_board_volume_filter(int volume){
    if(!dnd && preferences_loaded && desired_volume.exchange(volume)!=volume)dirty=true;
    return dnd?0:volume;
}
// HAL calls this even on release. Consume the entire first contact so waking
// cannot also click an app, submit a PIN or start microphone recording.
extern "C" bool brookesia_board_filter_touch(bool pressed){
    if(brookesia_board_deep_sleep_pending())return true;
    if(screen_locked){if(pressed)++locked_touches;consume_touch=pressed;return true;}
    if(!pressed){consume_touch=false;return false;}
    last_touch_ms=now_ms();deep_activity_ms=now_ms();
    if(asleep){wake_requested=true;if(!consume_touch.exchange(true))++swallowed;}
    return consume_touch;
}

namespace {
std::atomic<unsigned> key_edges{0};
void IRAM_ATTR volume_key_edge(void *context){key_edges.fetch_or(unsigned(uintptr_t(context)),std::memory_order_relaxed);}
void volume_keys_poll() {
    // Leave the middle PMU power key untouched. GPIO0 keeps its boot strap role.
    static bool initialized=false;
    struct Key{gpio_num_t pin;unsigned bit;int step;bool armed=false,held=false;uint32_t fired=0,repeat=0;};
    static Key keys[]={{GPIO_NUM_0,1,-5},{GPIO_NUM_18,2,5}};
    if(brookesia_board_deep_sleep_pending())return;
    if(lock_reset.exchange(false)){unlock_pattern.reset();unlock_taps=0;}
    if(keys_reinitialize.exchange(false))initialized=false;
    if(!initialized) {
        gpio_config_t config{};config.pin_bit_mask=(1ULL<<0)|(1ULL<<18);
        config.mode=GPIO_MODE_INPUT;config.pull_up_en=GPIO_PULLUP_ENABLE;
        config.intr_type=GPIO_INTR_NEGEDGE;
        if(gpio_config(&config)!=ESP_OK)return;
        const auto installed=gpio_install_isr_service(0);
        if(installed!=ESP_OK && installed!=ESP_ERR_INVALID_STATE)return;
        if(gpio_isr_handler_add(GPIO_NUM_0,volume_key_edge,reinterpret_cast<void *>(1))!=ESP_OK ||
           gpio_isr_handler_add(GPIO_NUM_18,volume_key_edge,reinterpret_cast<void *>(2))!=ESP_OK)return;
        for(auto &key:keys){key.armed=false;key.held=false;key.fired=key.repeat=0;}
        key_edges=0;initialized=true;keys_ready=true;
    }
    const auto now=now_ms();const unsigned edges=key_edges.exchange(0);
    unlock_pattern.expire(now);unlock_taps=unlock_pattern.pending();
    auto unlock=[&](){
        screen_locked=false;unlock_pattern.reset();unlock_taps=0;++unlock_count;
        sleep_requested=false;wake_requested=true;consume_touch=true;
    };
    for(auto &key:keys) {
        const bool pressed=gpio_get_level(key.pin)==0;
        const bool tap=(edges & key.bit)!=0;
        // Release is required for a real double press. A long hold and its
        // repeat events never advance the unlock gesture or change volume.
        if(screen_locked && key.step>0 && key.held && !pressed){
            const bool done=unlock_pattern.release(now);unlock_taps=unlock_pattern.pending();
            if(done){key.held=false;key.armed=true;unlock();continue;}
        }
        if(!pressed){key.armed=true;key.held=false;}
        const bool initial=(tap || pressed) && key.armed && (!key.fired || now-key.fired>=(screen_locked?50U:180U));
        const bool repeat=pressed && key.held && now-key.repeat>=350 && now-key.fired>=650;
        if(!initial && !repeat)continue;
        if(initial){key.fired=now;key.held=pressed;key.armed=false;}
        key.repeat=now;++key_presses;last_touch_ms=now;deep_activity_ms=now;
        if(screen_locked){
            if(key.step>0 && initial){
                unlock_pattern.press(now);
                if(!pressed && unlock_pattern.release(now))unlock();
                unlock_taps=unlock_pattern.pending();
            }else if(initial){
                unlock_pattern.reset();unlock_taps=0;
            }
            continue;
        }
        if(asleep){wake_requested=true;key.armed=false;key.held=false;continue;}
        if(dnd || brookesia_board_deep_sleep_pending())continue;
        // Keys update the board target directly. A cloud assistant has its own
        // writer; control must not wait on another playback service's RPC queue.
        const int current=brookesia_child_cap_volume(desired_volume.load());
        const int target=brookesia_child_cap_volume(std::clamp(current+key.step,0,100));
        key_last_gpio=int(key.pin);key_last_target=target;
        if(desired_volume.exchange(target)!=target){dirty=true;++key_applied;}
        audio_dirty=true; // Idle codec, and the active writer also synchronizes each PCM write.
    }
}
void story_brightness_poll() {
    static int saved=-1,applied=-1;
    const int factor=story_dim.load();
    if(factor==1000 && saved<0)return;
    auto backlight=hal::acquire_first_interface<hal::display::BacklightIface>();
    if(!backlight || esp_lv_adapter_lock(30)!=ESP_OK)return;
    if(saved<0){uint8_t value=0;if(backlight->get_brightness(value)){saved=value;applied=value;}}
    if(saved>=0) {
        const int target=factor==1000?saved:saved==0?0:std::max(1,saved*factor/1000);
        if(target==applied || backlight->set_brightness(target)) {
            applied=target;if(factor==1000){saved=-1;applied=-1;}
        }
    }
    esp_lv_adapter_unlock();
}
}
void device_modes_poll(){
    if(!ready)return;
    // Service start runs on a PSRAM-backed thread. Even NVS reads must run
    // here on the orientation worker's internal stack while flash cache pauses.
    if(!preferences_loaded){
        nvs_handle_t h;uint8_t a=1,d=0;int32_t resume=75;
        if(nvs_open("DeviceModes",NVS_READONLY,&h)==ESP_OK){
            uint8_t off=0;nvs_get_u8(h,"offline_voice",&off);offline_enabled=off!=0;
            uint16_t minutes=0;nvs_get_u16(h,"deep_min",&minutes);deep_minutes=idle_deep_sleep::index(minutes)>=0?minutes:0;
            nvs_get_u8(h,"auto_sleep",&a);nvs_get_u8(h,"dnd",&d);nvs_get_i32(h,"resume_volume",&resume);
            uint8_t q=0;int32_t start=1320,end=420;nvs_get_u8(h,"quiet_on",&q);nvs_get_i32(h,"quiet_start",&start);nvs_get_i32(h,"quiet_end",&end);
            quiet_enabled=q!=0;quiet_start=std::clamp<int>(start,0,1439);quiet_end=std::clamp<int>(end,0,1439);nvs_close(h);
        }
        automatic=a!=0;manual_dnd=d!=0;update_quiet();desired_volume=std::clamp<int>(resume,0,100);
        last_touch_ms=now_ms();deep_activity_ms=now_ms();audio_dirty=true;preferences_loaded=true;
    }
    update_quiet();
    volume_keys_poll();audiobook_sleep_poll();
    const bool waking=wake_requested.exchange(false) && !screen_locked.load();
    const bool sleeping=sleep_requested.exchange(false);
    const bool target=screen_locked || (waking?false:(asleep || sleeping || (automatic && now_ms()-last_touch_ms.load()>=IDLE_MS)));
    if(target!=asleep && esp_lv_adapter_lock(30)==ESP_OK){
        void *handle=nullptr;
        const auto found=esp_board_manager_get_device_handle("display_lcd",&handle);
        const auto lcd=static_cast<dev_display_lcd_handles_t *>(handle);
        if(found==ESP_OK && lcd && lcd->panel_handle && esp_lcd_panel_disp_on_off(lcd->panel_handle,!target)==ESP_OK){
            asleep=target;
            if(target)++sleeps;
            else {++wakes;last_touch_ms=now_ms();lv_obj_invalidate(lv_screen_active());}
        }else ++panel_errors;
        esp_lv_adapter_unlock();
    }
    if(waking && !asleep){last_touch_ms=now_ms();deep_activity_ms=now_ms();}
    if(waking && asleep)wake_requested=true;
    if(sleeping && !asleep)sleep_requested=true;
    story_brightness_poll();
    if(audio_dirty.exchange(false)){
        auto player=hal::acquire_first_interface<hal::audio::CodecPlayerIface>();
        if(!player || !player->set_volume(static_cast<uint8_t>(desired_volume.load())))audio_dirty=true;
    }
    if(dirty.exchange(false)){
        nvs_handle_t h;bool saved=false;
        if(nvs_open("DeviceModes",NVS_READWRITE,&h)==ESP_OK){
            saved=nvs_set_u8(h,"offline_voice",offline_enabled?1:0)==ESP_OK && nvs_set_u8(h,"auto_sleep",automatic?1:0)==ESP_OK && nvs_set_u8(h,"dnd",manual_dnd?1:0)==ESP_OK && nvs_set_i32(h,"resume_volume",desired_volume.load())==ESP_OK && nvs_set_u8(h,"quiet_on",quiet_enabled?1:0)==ESP_OK && nvs_set_i32(h,"quiet_start",quiet_start.load())==ESP_OK && nvs_set_i32(h,"quiet_end",quiet_end.load())==ESP_OK && nvs_set_u16(h,"deep_min",deep_minutes.load())==ESP_OK && nvs_commit(h)==ESP_OK;
            nvs_close(h);
        }
        if(!saved)dirty=true;
    }
    const auto now=now_ms();
    if(local_audio::busy() || screen_locked)deep_activity_ms=now;
    const auto seconds=test_idle_deep.load()?5U:uint32_t(deep_minutes.load()*60);
    if(!dirty && !brookesia_board_deep_sleep_pending() && idle_deep_sleep::due(now,deep_activity_ms.load(),seconds)) {
        const auto recovery=test_idle_deep.exchange(false)?20U:0U;
        // A failed attempt waits a fresh interval instead of retrying each poll.
        deep_activity_ms=now;
        (void)brookesia_board_request_deep_sleep(recovery);
    }
}
