#include "deep_sleep.hpp"
#include "device_modes.hpp"
#include "../audio_ownership.hpp"
#include <atomic>
#include <string_view>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/rtc_io.h"
#include "esp_sleep.h"
#include "esp_wifi.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_board_manager.h"
#include "dev_display_lcd.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lv_adapter.h"
#include "brookesia/service_manager/service/manager.hpp"
#include "lvgl.h"

using namespace esp_brookesia::service;
namespace {
constexpr gpio_num_t TOUCH_IRQ=GPIO_NUM_11, WAKE_KEY=GPIO_NUM_18;
constexpr uint64_t WAKE_MASK=(1ULL<<TOUCH_IRQ)|(1ULL<<WAKE_KEY);
RTC_DATA_ATTR uint32_t entries=0;
std::atomic<bool> pending{false};
std::atomic<int> failure{ESP_OK};
std::atomic<unsigned> test_seconds{0};

FunctionResult invoke(const char *service,const char *function,const boost::json::object &args={}) {
    auto value=ServiceManager::get_instance().get_service(service);
    if(!value || !value->is_running())return {.success=false,.error_message="Service unavailable"};
    return value->call_function_sync(function,args,8000);
}
bool close_apps() {
    auto result=invoke("SystemCore","ListApps");
    if(!result.success || !result.data || !std::holds_alternative<boost::json::array>(*result.data))return false;
    for(const auto &value:std::get<boost::json::array>(*result.data)) {
        const auto &app=value.as_object();
        if(app.at("manifest").as_object().at("id").as_string()=="brookesia.system.super.shell")continue;
        const auto &state=app.at("state").as_string();
        if(state=="Running" || state=="Paused" || state=="Starting") {
            if(!invoke("SystemCore","RequestCloseApp",{{"AppId",app.at("app_id")}}).success)return false;
        }
    }
    const auto deadline=esp_timer_get_time()+15000000;
    while(esp_timer_get_time()<deadline) {
        result=invoke("SystemCore","ListApps");
        if(!result.success || !result.data)return false;
        bool active=false;
        for(const auto &value:std::get<boost::json::array>(*result.data)) {
            const auto &app=value.as_object();
            if(app.at("manifest").as_object().at("id").as_string()=="brookesia.system.super.shell")continue;
            const auto &state=app.at("state").as_string();
            active|=state=="Running" || state=="Paused" || state=="Starting" || state=="Stopping";
        }
        if(!active)return true;
        vTaskDelay(pdMS_TO_TICKS(100));
    }
    return false;
}
bool stop_audio() {
    for(const auto *name:{"VoiceAssistant","Audiobook"}) {
        auto service=ServiceManager::get_instance().get_service(name);
        if(!service || !service->is_running())continue;
        if(!invoke(name,std::string_view(name)=="Audiobook"?"Stop":"Disconnect").success)return false;
    }
    const auto deadline=esp_timer_get_time()+10000000;
    while(local_audio::owner.load()!=local_audio::Free && esp_timer_get_time()<deadline)vTaskDelay(pdMS_TO_TICKS(50));
    return local_audio::owner.load()==local_audio::Free;
}
esp_err_t enter_sleep() {
    // Do not cut power or stop Wi-Fi while apps still own files or audio buffers.
    if(!close_apps() || !stop_audio())return ESP_ERR_TIMEOUT;
    // The idle timeout is a one-shot choice. Persist OFF before any real sleep.
    if(!brookesia_board_set_auto_deep_sleep_index(0))return ESP_ERR_INVALID_STATE;
    // Existing internal workers finish their pending NVS saves during this grace period.
    vTaskDelay(pdMS_TO_TICKS(1500));
    for(const auto *name:{"DeviceModes","AutoRotation"}) {
        auto state=invoke(name,"GetState");
        if(!state.success || !state.data || !std::holds_alternative<boost::json::object>(*state.data))return ESP_ERR_TIMEOUT;
        const auto *saving=std::get<boost::json::object>(*state.data).if_contains("pending_save");
        if(saving && saving->is_bool() && saving->as_bool())return ESP_ERR_INVALID_STATE;
    }
    gpio_config_t key{};key.pin_bit_mask=1ULL<<WAKE_KEY;key.mode=GPIO_MODE_INPUT;key.pull_up_en=GPIO_PULLUP_ENABLE;
    esp_err_t error=gpio_config(&key);if(error!=ESP_OK)return error;
    if(gpio_get_level(TOUCH_IRQ)==0 || gpio_get_level(WAKE_KEY)==0)return ESP_ERR_INVALID_STATE;
    error=esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL);if(error!=ESP_OK)return error;
    for(auto pin:{TOUCH_IRQ,WAKE_KEY}) {
        if((error=rtc_gpio_init(pin))!=ESP_OK)return error;
        if((error=rtc_gpio_set_direction(pin,RTC_GPIO_MODE_INPUT_ONLY))!=ESP_OK)return error;
        rtc_gpio_pullup_en(pin);rtc_gpio_pulldown_dis(pin);
    }
    error=esp_sleep_enable_ext1_wakeup_io(WAKE_MASK,ESP_EXT1_WAKEUP_ANY_LOW);if(error!=ESP_OK)return error;
    const auto seconds=test_seconds.load();
    if(seconds && (error=esp_sleep_enable_timer_wakeup(uint64_t(seconds)*1000000))!=ESP_OK)return error;
    if(esp_lv_adapter_lock(1000)!=ESP_OK)return ESP_ERR_TIMEOUT;
    void *handle=nullptr;error=esp_board_manager_get_device_handle("display_lcd",&handle);
    const auto lcd=static_cast<dev_display_lcd_handles_t *>(handle);
    if(error==ESP_OK && lcd && lcd->panel_handle)error=esp_lcd_panel_disp_on_off(lcd->panel_handle,false);
    else error=ESP_ERR_INVALID_STATE;
    esp_lv_adapter_unlock();
    if(error!=ESP_OK)return error;
    // Keep both reset lines high and the amplifier off while digital GPIO powers down.
    for(auto pin:{GPIO_NUM_39,GPIO_NUM_40,GPIO_NUM_46}) {
        gpio_set_level(pin,pin==GPIO_NUM_46?0:1);gpio_hold_en(pin);
    }
    gpio_deep_sleep_hold_en();
    // Use the service state machine so a planned stop is not treated as a
    // Wi-Fi failure and restarted while the CPU prepares to sleep.
    auto wifi=ServiceManager::get_instance().get_service("Wifi");
    if(wifi && wifi->is_running()) {
        auto result=invoke("Wifi","TriggerGeneralAction",{{"Action","Stop"}});
        if(!result.success)return ESP_FAIL;
        const auto deadline=esp_timer_get_time()+10000000;
        bool stopped=false;
        while(esp_timer_get_time()<deadline) {
            result=invoke("Wifi","GetGeneralState");
            if(result.success && result.data && std::holds_alternative<std::string>(*result.data)) {
                const auto &state=std::get<std::string>(*result.data);
                if(state=="Inited" || state=="Idle"){stopped=true;break;}
            }
            vTaskDelay(pdMS_TO_TICKS(100));
        }
        if(!stopped)return ESP_ERR_TIMEOUT;
    } else {
        const auto error=esp_wifi_stop();
        if(error!=ESP_OK && error!=ESP_ERR_WIFI_NOT_INIT)return error;
    }
    // App shutdown has already closed its files. Picolibc tinystdio does not
    // support fflush(NULL); calling it dereferences NULL on this IDF runtime.
    ++entries;
    ESP_LOGI("S3_SLEEP","Entering deep sleep; touch/key wake; test timer=%u",seconds);
    esp_deep_sleep_start();
    return ESP_FAIL;
}
void worker(void *) {
    // Let the GUI confirmation and USB reply finish before closing apps.
    vTaskDelay(pdMS_TO_TICKS(700));
    const auto error=enter_sleep();
    board_deep_sleep_boot();
    esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL);
    if(esp_lv_adapter_lock(1000)==ESP_OK) {
        void *handle=nullptr;
        if(esp_board_manager_get_device_handle("display_lcd",&handle)==ESP_OK && handle) {
            auto *lcd=static_cast<dev_display_lcd_handles_t *>(handle);
            if(lcd->panel_handle)esp_lcd_panel_disp_on_off(lcd->panel_handle,true);
        }
        lv_obj_invalidate(lv_screen_active());esp_lv_adapter_unlock();
    }
    failure=error;
    pending=false;local_audio::sleeping=false;brookesia_board_volume_keys_resume();
    ESP_LOGE("S3_SLEEP","Deep sleep cancelled: %s",esp_err_to_name(error));
    vTaskDelete(nullptr);
}
}
void board_deep_sleep_boot() {
    gpio_deep_sleep_hold_dis();
    for(auto pin:{GPIO_NUM_39,GPIO_NUM_40,GPIO_NUM_46})gpio_hold_dis(pin);
    rtc_gpio_deinit(TOUCH_IRQ);rtc_gpio_deinit(WAKE_KEY);
}
bool brookesia_board_deep_sleep_pending(){return pending.load();}
int brookesia_board_request_deep_sleep(unsigned seconds) {
    if(seconds!=0 && seconds!=20)return ESP_ERR_INVALID_ARG;
    bool expected=false;if(!pending.compare_exchange_strong(expected,true))return ESP_ERR_INVALID_STATE;
    failure=ESP_OK;test_seconds=seconds;local_audio::sleeping=true;
    if(xTaskCreatePinnedToCore(worker,"deep_sleep",12288,nullptr,3,nullptr,0)!=pdPASS) {
        pending=false;local_audio::sleeping=false;failure=ESP_ERR_NO_MEM;return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}
boost::json::object board_deep_sleep_state() {
    const auto cause=esp_sleep_get_wakeup_cause();
    return {{"pending",pending.load()},{"entries",entries},{"wake_cause",int(cause)},
            {"wake_pins",cause==ESP_SLEEP_WAKEUP_EXT1?esp_sleep_get_ext1_wakeup_status():0},
            {"error",failure.load()==ESP_OK?"":esp_err_to_name(failure.load())},
            {"touch_wakeup_gpio",11},{"key_wakeup_gpio",18}};
}
