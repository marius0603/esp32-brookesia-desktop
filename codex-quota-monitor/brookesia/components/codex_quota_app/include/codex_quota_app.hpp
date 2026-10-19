#pragma once
#include <cstdint>
#include "systems/phone/esp_brookesia_phone_app.hpp"
namespace esp_brookesia::apps {
class CodexQuota final : public systems::phone::App {
public:
    CodexQuota();
protected:
    bool run() override;
    bool back() override;
    bool close() override;
    bool pause() override;
    bool resume() override;
private:
    void refreshView();
    void toggleDetails();
    void adjustVolume(int delta);
    void showPowerDialog();
    void dismissPowerDialog();
    void confirmPowerOff();
    static void timerCallback(lv_timer_t *timer);
    lv_obj_t *root_ = nullptr;
    lv_obj_t *overview_ = nullptr;
    lv_obj_t *details_ = nullptr;
    lv_obj_t *status_ = nullptr;
    lv_obj_t *window_name_ = nullptr;
    lv_obj_t *percent_ = nullptr;
    lv_obj_t *countdown_ = nullptr;
    lv_obj_t *secondary_ = nullptr;
    lv_obj_t *secondary_bar_ = nullptr;
    lv_obj_t *ring_ = nullptr;
    lv_obj_t *detail_text_ = nullptr;
    lv_obj_t *footer_ = nullptr;
    lv_obj_t *volume_down_ = nullptr;
    lv_obj_t *volume_up_ = nullptr;
    lv_obj_t *volume_text_ = nullptr;
    lv_obj_t *power_button_ = nullptr;
    lv_obj_t *power_dialog_ = nullptr;
    lv_obj_t *power_message_ = nullptr;
    lv_obj_t *power_confirm_ = nullptr;
    lv_timer_t *timer_ = nullptr;
    int64_t control_notice_until_ = 0;
    int selected_ = 0;
    bool showing_details_ = false;
};
}
