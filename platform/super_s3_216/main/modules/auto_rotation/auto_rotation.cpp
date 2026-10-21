#include "auto_rotation.hpp"
#include "orientation.hpp"
#include "../device_modes/device_modes.hpp"
#include <atomic>
#include <mutex>
#include <string>
#include "driver/i2c_master.h"
#include "esp_board_manager.h"
#include "dev_display_lcd.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lv_adapter.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs.h"
#include "lvgl.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "brookesia/gui_lvgl.hpp"

using namespace esp_brookesia;
using namespace esp_brookesia::service;
namespace {
std::atomic<bool> enabled{true}, available{false}, dirty{false};
std::atomic<int> angle{0}, offset{0}, pending{-1};
constexpr uint32_t STACK_BYTES = 6144;
constexpr int64_t SETTLE_US = 500000, COOLDOWN_US = 1000000;
const char *TAG = "AutoRotate";

class AutoRotation final : public ServiceBase {
public:
    AutoRotation() : ServiceBase({.name="AutoRotation", .description="QMI8658 gravity screen orientation",
                                  .version="0.1.1", .dependencies={}}) {}
private:
    std::atomic<bool> live_{false}, stop_{false};
    std::atomic<uint32_t> samples_{0}, changes_{0}, failures_{0}, stack_free_{STACK_BYTES};
    std::mutex mutex_;
    float x_=0, y_=0, z_=0;
    std::string error_;
    i2c_master_dev_handle_t imu_=nullptr;
    dev_display_lcd_handles_t *lcd_=nullptr;
    std::atomic<uint8_t> address_{0};
    int64_t next_save_us_=0;
    void error(std::string message) { std::lock_guard<std::mutex> lock(mutex_); error_=std::move(message); }
    bool write(uint8_t reg, uint8_t value) {
        const uint8_t bytes[]{reg,value};
        return i2c_master_transmit(imu_,bytes,sizeof(bytes),20)==ESP_OK;
    }
    bool read(uint8_t reg, uint8_t *bytes, size_t size) {
        return i2c_master_transmit_receive(imu_,&reg,1,bytes,size,20)==ESP_OK;
    }
    bool initialize() {
        void *bus=nullptr, *panel=nullptr;
        if(esp_board_manager_get_periph_handle("i2c_master",&bus)!=ESP_OK ||
           esp_board_manager_get_device_handle("display_lcd",&panel)!=ESP_OK || !bus || !panel) {
            error("Display/I2C hardware unavailable"); return false;
        }
        lcd_=static_cast<dev_display_lcd_handles_t *>(panel);
        for(const uint8_t candidate : {uint8_t(0x6b),uint8_t(0x6a)}) {
            i2c_device_config_t config{};
            config.dev_addr_length=I2C_ADDR_BIT_LEN_7;
            config.device_address=candidate; config.scl_speed_hz=100000;
            if(i2c_master_bus_add_device(static_cast<i2c_master_bus_handle_t>(bus),&config,&imu_)!=ESP_OK)continue;
            uint8_t who=0;
            if(read(0,&who,1) && who==0x05) { address_=candidate; break; }
            i2c_master_bus_rm_device(imu_); imu_=nullptr;
        }
        if(!imu_) {error("QMI8658 not detected");return false;}
        // Auto-increment, +/-4g, 31.25Hz, acceleration LPF. Gyroscope stays off.
        if(!write(0x08,0) || !write(0x02,0x60) || !write(0x03,0x18) ||
           !write(0x06,0x01) || !write(0x08,0x01)) {
            error("QMI8658 configuration failed"); return false;
        }
        available=true;
        ESP_LOGI(TAG,"QMI8658 ready at 0x%02x; four-way rotation, settle=500ms",address_.load());
        return true;
    }
    bool apply(int next) {
        if(next==angle) return true;
        if(brookesia_board_screen_asleep())return false;
        if(!lcd_ || !lcd_->panel_handle || esp_lv_adapter_lock(30)!=ESP_OK)return false;
        auto &source=gui::lvgl::DisplaySource::get_instance();
        if(source.input() && lv_indev_get_state(source.input())==LV_INDEV_STATE_PRESSED) {
            esp_lv_adapter_unlock();return false;
        }
        const int old=angle;
        const bool swap=next==90 || next==270;
        const bool mx=next==90 || next==180;
        const bool my=next==180 || next==270;
        // Panel orientation is hardware accelerated. LVGL remains 480x480 at
        // rotation 0; the HAL transforms touch once for both GUI and gestures.
        esp_err_t result=esp_lcd_panel_swap_xy(lcd_->panel_handle,swap);
        if(result==ESP_OK) result=esp_lcd_panel_mirror(lcd_->panel_handle,mx,my);
        if(result==ESP_OK) {
            angle=next; ++changes_;
            if(source.input())lv_indev_reset(source.input(),nullptr);
            lv_obj_invalidate(lv_layer_bottom());
            lv_obj_invalidate(lv_screen_active());
            lv_obj_invalidate(lv_layer_top());
            lv_obj_invalidate(lv_layer_sys());
        } else {
            esp_lcd_panel_swap_xy(lcd_->panel_handle,old==90 || old==270);
            esp_lcd_panel_mirror(lcd_->panel_handle,old==90 || old==180,old==180 || old==270);
        }
        esp_lv_adapter_unlock();
        if(result!=ESP_OK)error("Display rotation failed");
        else ESP_LOGI(TAG,"Orientation: %d degrees",next);
        return result==ESP_OK;
    }
    void load() {
        nvs_handle_t handle;
        if(nvs_open("AutoRotate",NVS_READONLY,&handle)!=ESP_OK)return;
        uint8_t on=1; int32_t off=0,locked=0;
        nvs_get_u8(handle,"enabled",&on); nvs_get_i32(handle,"offset",&off);nvs_get_i32(handle,"locked",&locked);
        nvs_close(handle);
        enabled=on!=0;
        if(off>=0 && off<360 && off%90==0)offset=off;
        if(!enabled && locked>=0 && locked<360 && locked%90==0)pending=locked;
    }
    void persist() {
        if(pending>=0 || esp_timer_get_time()<next_save_us_ || !dirty.exchange(false))return;
        nvs_handle_t handle;
        esp_err_t result=nvs_open("AutoRotate",NVS_READWRITE,&handle);
        if(result==ESP_OK) {
            result=nvs_set_u8(handle,"enabled",enabled?1:0);
            if(result==ESP_OK)result=nvs_set_i32(handle,"offset",offset);
            if(result==ESP_OK)result=nvs_set_i32(handle,"locked",angle);
            if(result==ESP_OK)result=nvs_commit(handle);
            nvs_close(handle);
        }
        if(result!=ESP_OK) {
            dirty=true;next_save_us_=esp_timer_get_time()+5000000;
            error("Unable to save rotation preference");
        }
    }
    void run() {
        load();
        {
            const bool imu_ready=initialize();
            int candidate=-1; int64_t since=0,last=0; bool filtered=false;
            float fx=0,fy=0,fz=0;
            while(!stop_) {
                uint8_t bytes[6];
                device_modes_poll();
                if(imu_ready && read(0x35,bytes,sizeof(bytes))) {
                    const auto sample=[&](int at){return static_cast<int16_t>(bytes[at] | (bytes[at+1]<<8))/8192.F;};
                    float x=sample(0),y=sample(2),z=sample(4);
                    {std::lock_guard<std::mutex> lock(mutex_);x_=x;y_=y;z_=z;}
                    ++samples_;
                    if(!filtered) {fx=x;fy=y;fz=z;filtered=true;}
                    else {fx+=.25F*(x-fx);fy+=.25F*(y-fy);fz+=.25F*(z-fz);}
                    const int64_t now=esp_timer_get_time();
                    int requested=pending.load();
                    if(requested>=0 && apply(requested)) {
                        pending.compare_exchange_strong(requested,-1);last=now;
                    }
                    if(enabled && pending<0) {
                        const int raw=board_orientation::classify(fx,fy,fz);
                        const int next=raw<0?-1:board_orientation::screen_angle(raw,offset);
                        if(next<0 || next==angle) {candidate=-1;since=0;}
                        else if(candidate!=next) {candidate=next;since=now;}
                        else if(now-since>=SETTLE_US && now-last>=COOLDOWN_US && apply(next)) {
                            last=now;candidate=-1;since=0;
                        }
                    } else {candidate=-1;since=0;}
                } else {
                    ++failures_;candidate=-1;since=0;filtered=false;
                    if(failures_%20==0)error("QMI8658 read failed; orientation held");
                }
                persist();
                stack_free_=std::min(stack_free_.load(),static_cast<uint32_t>(uxTaskGetStackHighWaterMark(nullptr)));
                vTaskDelay(pdMS_TO_TICKS(100));
            }
        }
        available=false;
        if(imu_){i2c_master_bus_rm_device(imu_);imu_=nullptr;}
        live_=false;
    }
    bool on_start() override {
        stop_=false;live_=true;
        if(xTaskCreatePinnedToCore([](void *ctx){static_cast<AutoRotation *>(ctx)->run();vTaskDelete(nullptr);},
             "auto_rotate",STACK_BYTES,this,2,nullptr,0)!=pdPASS) {
            live_=false;error("Unable to allocate orientation task");return false;
        }
        return true;
    }
    void on_stop() override {stop_=true;while(live_)vTaskDelay(pdMS_TO_TICKS(10));}
    boost::json::object snapshot() {
        std::lock_guard<std::mutex> lock(mutex_);
        return {{"enabled",enabled.load()},{"available",available.load()},{"degrees",angle.load()},
                {"offset_degrees",offset.load()},{"address",address_.load()},{"ax_g",x_},{"ay_g",y_},{"az_g",z_},
                {"samples",samples_.load()},{"changes",changes_.load()},{"read_failures",failures_.load()},
                {"pending_save",dirty.load()},{"error",error_},{"stack_free_min_bytes",stack_free_.load()}};
    }
    std::vector<FunctionSchema> get_function_schemas() override {
        return {{"GetState","Get gravity and orientation state",{},true,std::nullopt,FunctionReturnSchema{FunctionValueType::Object,"Orientation"}},
                {"SetEnabled","Enable automatic orientation",{{"Enabled","Automatic rotation",FunctionValueType::Boolean}}},
                {"SetRotation","Set locked orientation",{{"Degrees","0,90,180,270",FunctionValueType::Number}}},
                {"CalibrateUpright","Use the current upright pose as the normal screen direction",{}}};
    }
    FunctionHandlerList get_function_handlers() override {
        return {
            {"GetState",[this](FunctionParameterMap &&)->FunctionResult{return {.success=true,.data=FunctionValue(snapshot())};}},
            {"SetEnabled",[](FunctionParameterMap &&p)->FunctionResult{enabled=std::get<bool>(p.at("Enabled"));dirty=true;return {.success=true};}},
            {"SetRotation",[](FunctionParameterMap &&p)->FunctionResult{
                const double value=std::get<double>(p.at("Degrees"));
                if(enabled || !std::isfinite(value) || value<0 || value>270 || std::fmod(value,90)!=0)
                    return {.success=false,.error_message="Disable automatic rotation and use 0/90/180/270"};
                pending=static_cast<int>(value);dirty=true;return {.success=true};}},
            {"CalibrateUpright",[this](FunctionParameterMap &&)->FunctionResult{
                int pose;{std::lock_guard<std::mutex> lock(mutex_);pose=board_orientation::classify(x_,y_,z_);}
                if(!available || pose<0)return {.success=false,.error_message="Hold device upright before calibrating"};
                offset=(360-pose)%360;pending=0;dirty=true;return {.success=true};}}
        };
    }
};
}
std::shared_ptr<ServiceBase> make_auto_rotation_service() {return std::make_shared<AutoRotation>();}
extern "C" bool brookesia_board_auto_rotation_available() {return available;}
extern "C" bool brookesia_board_auto_rotation_enabled() {return enabled;}
extern "C" void brookesia_board_auto_rotation_set_enabled(bool value) {enabled=value;dirty=true;}
extern "C" void brookesia_board_touch_transform(int16_t *x,int16_t *y) {board_orientation::inverse_touch(*x,*y,angle);}
