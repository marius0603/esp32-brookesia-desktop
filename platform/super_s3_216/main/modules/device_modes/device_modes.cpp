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
#include "esp_lcd_panel_ops.h"
#include "esp_lv_adapter.h"
#include "esp_timer.h"
#include "nvs.h"
#include "lvgl.h"

using namespace esp_brookesia;
using namespace esp_brookesia::service;
namespace {
constexpr uint32_t IDLE_MS = 600000;
std::atomic<bool> ready{false}, automatic{true}, dnd{true}, asleep{false};
std::atomic<bool> wake_requested{false}, sleep_requested{false}, consume_touch{false};
std::atomic<bool> dirty{false}, audio_dirty{false};
std::atomic<int> desired_volume{75};
std::atomic<bool> manual_dnd{false},quiet_enabled{false};
std::atomic<int> quiet_start{1320},quiet_end{420};
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
        return {{"auto_sleep_enabled",automatic.load()},{"timeout_seconds",600},
                {"screen_asleep",asleep.load()},{"do_not_disturb",dnd.load()},
                {"manual_do_not_disturb",manual_dnd.load()},{"quiet_hours_enabled",quiet_enabled.load()},
                {"quiet_start_minute",quiet_start.load()},{"quiet_end_minute",quiet_end.load()},
                {"local_minute",local_minute()},{"clock_synced",local_minute()>=0},{"timezone","Asia/Shanghai"},
                {"idle_seconds",(now_ms()-last_touch_ms.load())/1000},
                {"wake_touch_consumed",swallowed.load()},{"sleep_count",sleeps.load()},
                {"wake_count",wakes.load()},{"panel_errors",panel_errors.load()},
                {"pending_save",dirty.load()},{"audio_pending",audio_dirty.load()},
                {"resume_volume",desired_volume.load()}};
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
                if(count==24 || count==60){
                    const auto font=lv_obj_get_style_text_font(object,LV_PART_MAIN);
                    auto *list=lv_dropdown_get_list(object);const auto popup=lv_obj_get_style_text_font(list,LV_PART_MAIN);
                    const auto selected=lv_obj_get_style_text_font(list,LV_PART_SELECTED);
                    char text[24]{};lv_dropdown_get_selected_str(object,text,sizeof(text));
                    layers.push_back(boost::json::object{{"kind","time_picker"},{"options",count},{"selected",lv_dropdown_get_selected(object)},
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
        return {{"GetWeatherLayers","Read visible native layer opacity for weather diagnostics",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Visible surfaces"}},
                {"GetState","Get screen and sound mode state",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Modes"}},
                {"SetAutoSleep","Enable ten minute inactivity timeout",{{"Enabled","Enabled",FunctionValueType::Boolean}}},
                {"SetDoNotDisturb","Mute speaker while retaining its volume",{{"Enabled","Enabled",FunctionValueType::Boolean}}},
                {"SetQuietHours","Set daily quiet hours in Beijing time",{{"Enabled","Schedule enabled",FunctionValueType::Boolean},{"StartMinute","0-1439 inclusive",FunctionValueType::Number},{"EndMinute","0-1439 exclusive; equal means all day",FunctionValueType::Number}}},
                {"SleepNow","Turn screen off without stopping apps",{}},
                {"Wake","Wake screen for maintenance",{}}};
    }
    FunctionHandlerList get_function_handlers() override {
        return {{"GetWeatherLayers",[this](FunctionParameterMap &&)->FunctionResult{return visual_layers();}},
                {"GetState",[this](FunctionParameterMap &&)->FunctionResult{return {.success=true,.data=FunctionValue(state())};}},
                {"SetAutoSleep",[](FunctionParameterMap &&p)->FunctionResult{brookesia_board_set_auto_sleep(std::get<bool>(p.at("Enabled")));return {.success=true};}},
                {"SetDoNotDisturb",[](FunctionParameterMap &&p)->FunctionResult{brookesia_board_set_do_not_disturb(std::get<bool>(p.at("Enabled")));return {.success=true};}},
                {"SetQuietHours",[](FunctionParameterMap &&p)->FunctionResult{
                    const double a=std::get<double>(p.at("StartMinute")),b=std::get<double>(p.at("EndMinute"));
                    if(!std::isfinite(a)||!std::isfinite(b)||a<0||a>=1440||b<0||b>=1440||std::floor(a)!=a||std::floor(b)!=b)return {.success=false,.error_message="Times must be whole minutes from 0 to 1439"};
                    brookesia_board_set_quiet_hours(std::get<bool>(p.at("Enabled")),int(a),int(b));return {.success=true};}},
                {"SleepNow",[](FunctionParameterMap &&)->FunctionResult{sleep_requested=true;return {.success=true};}},
                {"Wake",[](FunctionParameterMap &&)->FunctionResult{wake_requested=true;return {.success=true};}}};
    }
};
}

std::shared_ptr<ServiceBase> make_device_modes_service(){return std::make_shared<DeviceModes>();}
extern "C" bool brookesia_board_screen_asleep(){return asleep;}
extern "C" bool brookesia_board_do_not_disturb(){return dnd;}
extern "C" bool brookesia_board_auto_sleep_enabled(){return automatic;}
extern "C" void brookesia_board_set_auto_sleep(bool on){automatic=on;dirty=true;wake_requested=true;}
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
extern "C" int brookesia_board_volume_filter(int volume){if(!dnd)desired_volume=volume;return dnd?0:volume;}
// HAL calls this even on release. Consume the entire first contact so waking
// cannot also click an app, submit a PIN or start microphone recording.
extern "C" bool brookesia_board_filter_touch(bool pressed){
    if(!pressed){consume_touch=false;return false;}
    last_touch_ms=now_ms();
    if(asleep){wake_requested=true;if(!consume_touch.exchange(true))++swallowed;}
    return consume_touch;
}

void device_modes_poll(){
    if(!ready)return;
    // Service start runs on a PSRAM-backed thread. Even NVS reads must run
    // here on the orientation worker's internal stack while flash cache pauses.
    static bool loaded=false;
    if(!loaded){
        nvs_handle_t h;uint8_t a=1,d=0;int32_t resume=75;
        if(nvs_open("DeviceModes",NVS_READONLY,&h)==ESP_OK){
            nvs_get_u8(h,"auto_sleep",&a);nvs_get_u8(h,"dnd",&d);nvs_get_i32(h,"resume_volume",&resume);
            uint8_t q=0;int32_t start=1320,end=420;nvs_get_u8(h,"quiet_on",&q);nvs_get_i32(h,"quiet_start",&start);nvs_get_i32(h,"quiet_end",&end);
            quiet_enabled=q!=0;quiet_start=std::clamp<int>(start,0,1439);quiet_end=std::clamp<int>(end,0,1439);nvs_close(h);
        }
        automatic=a!=0;manual_dnd=d!=0;update_quiet();desired_volume=std::clamp<int>(resume,0,100);
        last_touch_ms=now_ms();audio_dirty=true;loaded=true;
    }
    update_quiet();
    const bool waking=wake_requested.exchange(false);
    const bool sleeping=sleep_requested.exchange(false);
    const bool target=waking?false:(asleep || sleeping || (automatic && now_ms()-last_touch_ms.load()>=IDLE_MS));
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
    if(waking && !asleep)last_touch_ms=now_ms();
    if(waking && asleep)wake_requested=true;
    if(sleeping && !asleep)sleep_requested=true;
    if(audio_dirty.exchange(false)){
        auto player=hal::acquire_first_interface<hal::audio::CodecPlayerIface>();
        if(!player || !player->set_volume(static_cast<uint8_t>(desired_volume.load())))audio_dirty=true;
    }
    if(dirty.exchange(false)){
        nvs_handle_t h;bool saved=false;
        if(nvs_open("DeviceModes",NVS_READWRITE,&h)==ESP_OK){
            saved=nvs_set_u8(h,"auto_sleep",automatic?1:0)==ESP_OK && nvs_set_u8(h,"dnd",manual_dnd?1:0)==ESP_OK && nvs_set_i32(h,"resume_volume",desired_volume.load())==ESP_OK && nvs_set_u8(h,"quiet_on",quiet_enabled?1:0)==ESP_OK && nvs_set_i32(h,"quiet_start",quiet_start.load())==ESP_OK && nvs_set_i32(h,"quiet_end",quiet_end.load())==ESP_OK && nvs_commit(h)==ESP_OK;
            nvs_close(h);
        }
        if(!saved)dirty=true;
    }
}
