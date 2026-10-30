/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#include "private/utils.hpp"
#include "esp_heap_caps.h"
#include "boost/chrono.hpp"
#include "boost/thread.hpp"
#include "brookesia/lib_utils/thread_config.hpp"
#include "brookesia/gui_lvgl.hpp"
#include "brookesia/system_super.hpp"
#include "modules/general_services.hpp"
#include "modules/display.hpp"
#include "modules/child_mode/child_mode.hpp"
#include "modules/device_modes/deep_sleep.hpp"
#include "modules/phone_provisioning/navigation.hpp"
#include "modules/audio_ownership.hpp"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

extern "C" bool brookesia_board_single_app_mode(){return true;}
extern "C" const char *brookesia_board_before_app_start(){
    // Disconnect requests are asynchronous. The assistant releases ownership
    // only after its network callbacks have stopped and audio buffers are freed.
    // Keep the next page from allocating over those still-live resources.
    for(int i=0;local_audio::owner.load()==local_audio::Assistant && i<2000;++i)
        vTaskDelay(pdMS_TO_TICKS(10));
    return local_audio::owner.load()==local_audio::Assistant?"语音连接正在关闭，请稍后重试":nullptr;
}

using namespace esp_brookesia;

extern "C" void app_main(void)
{
    board_deep_sleep_boot();
    BROOKESIA_LOGI("\n\n=== System Example ===\n");

    auto setup_task = []() {
        /* Initialize general services */
        BROOKESIA_CHECK_FALSE_EXIT(
            GeneralServices::get_instance().init(), "Failed to initialize general services"
        );

        /* Start display UI */
        auto &display = Display::get_instance();
        auto display_start_ret = display.start({});
        BROOKESIA_CHECK_FALSE_EXIT(display_start_ret, "Failed to start display");
        /* Start audio services */
        BROOKESIA_CHECK_FALSE_EXIT(
            GeneralServices::get_instance().start_audio_services(), "Failed to start audio services"
        );

        /* Create system instance */
        static std::unique_ptr<system::super::System> system_instance;
        system_instance = std::make_unique<system::super::System>();

        /* Configure system */
        system::super::System::Config config;
        config.core_config.gui_backend = std::make_unique<gui::lvgl::Backend>();
        config.core_config.environment = {
            .width_px = static_cast<int32_t>(display.width()),
            .height_px = static_cast<int32_t>(display.height()),
            .density = 1.0F,
            .font_scale = 1.0F,
            .language = "zh_CN",
            .theme_id = "dark",
        };
        // config.core_config.enable_gui_view_debug = true;

        /* Initialize and start system */
        BROOKESIA_LOGI("Memory before desktop: internal=%1% PSRAM=%2%",
                       heap_caps_get_free_size(MALLOC_CAP_INTERNAL), heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
        auto init_result = system_instance->init(std::move(config));
        BROOKESIA_CHECK_FALSE_EXIT(init_result, "System init failed: %1%", init_result.error());
        child_mode_attach_system(system_instance.get());
        phone_remote::attach_system(system_instance.get());
        auto start_result = system_instance->start();
        BROOKESIA_CHECK_FALSE_EXIT(start_result, "System start failed: %1%", start_result.error());

        boost::this_thread::sleep_for(boost::chrono::seconds(10));

        BROOKESIA_LOGI("Memory after desktop: internal=%1% PSRAM=%2%",
                       heap_caps_get_free_size(MALLOC_CAP_INTERNAL), heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
        BROOKESIA_LOGI("=== System Example Completed ===");
    };
    {
        /* Setup task in a high stack size thread to avoid stack overflow */
        BROOKESIA_THREAD_CONFIG_GUARD({
            .stack_size = 40 * 1024,
            .stack_in_ext = true,
        });
        boost::thread(setup_task).detach();
    }
}
