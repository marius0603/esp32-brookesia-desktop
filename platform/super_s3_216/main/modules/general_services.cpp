/*
 * SPDX-FileCopyrightText: 2025-2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: CC0-1.0
 */
#include "sdkconfig.h"
#include "brookesia/hal_interface.hpp"
#include "brookesia/hal_adaptor.hpp"
#include "brookesia/service_helper/media/audio.hpp"
#include "brookesia/service_manager/service/manager.hpp"
#include "private/utils.hpp"
#include "general_services.hpp"
#include "audiobook/audiobook.hpp"
#include "offline_voice/offline_voice.hpp"
#include "voice_assistant/voice_assistant.hpp"
#include "voice_assistant/local_voice.hpp"
#include "auto_rotation/auto_rotation.hpp"
#include "device_modes/device_modes.hpp"
#include "child_mode/child_mode.hpp"
#include "sd_resources/sd_resources.hpp"
#include "learning_audio/learning_audio.hpp"
#include "phone_provisioning/phone_provisioning.hpp"

using namespace esp_brookesia;

using AudioPlaybackHelper = esp_brookesia::service::helper::AudioPlayback;

constexpr const char *AUDIO_WAKEUP_WORD_MODEL_PARTITION_LABEL = "model";
constexpr const char *AUDIO_WAKEUP_WORD_MN_LANGUAGE = "cn";
constexpr uint32_t AUDIO_WAKEUP_START_TIMEOUT_MS = 30000;
constexpr uint32_t AUDIO_WAKEUP_END_TIMEOUT_MS = 10000;

bool GeneralServices::init()
{
    auto &service_manager = service::ServiceManager::get_instance();
    BROOKESIA_CHECK_FALSE_RETURN(service_manager.init(), false, "Failed to initialize service manager");
    BROOKESIA_CHECK_FALSE_RETURN(service_manager.add_service(make_audiobook_service()), false, "Failed to register audiobook service");
    BROOKESIA_CHECK_FALSE_RETURN(service_manager.add_service(make_voice_assistant_service()), false, "Failed to register voice assistant service");
    BROOKESIA_CHECK_FALSE_RETURN(service_manager.add_service(make_local_voice_service()), false, "Failed to register local voice service");
    BROOKESIA_CHECK_FALSE_RETURN(service_manager.add_service(make_device_modes_service()), false, "Failed to register device modes");
    BROOKESIA_CHECK_FALSE_RETURN(service_manager.add_service(make_auto_rotation_service()), false, "Failed to register auto rotation service");
    BROOKESIA_CHECK_FALSE_RETURN(service_manager.add_service(make_child_mode_service()), false, "Failed to register child mode service");
    BROOKESIA_CHECK_FALSE_RETURN(service_manager.add_service(make_sd_resources_service()), false, "Failed to register SD resource service");
    BROOKESIA_CHECK_FALSE_RETURN(service_manager.add_service(make_learning_audio_service()), false, "Failed to register learning audio service");
    BROOKESIA_CHECK_FALSE_RETURN(service_manager.add_service(make_phone_provisioning_service()), false, "Failed to register phone provisioning");

    BROOKESIA_CHECK_FALSE_RETURN(service_manager.add_service(make_offline_voice_service()), false, "Failed to register offline voice");

    BROOKESIA_CHECK_FALSE_RETURN(init_audio(), false, "Failed to initialize audio");
    BROOKESIA_CHECK_FALSE_RETURN(service_manager.start(), false, "Failed to start service manager");

    BROOKESIA_LOGI("Service manager started successfully");

    return true;
}

bool GeneralServices::init_audio()
{
#if CONFIG_BROOKESIA_HAL_ADAPTOR_AUDIO_ENABLE_AUDIO_PROCESSOR_IMPL
    hal::AudioProcessorConfig processor_config {
        .playback = {
            .player_task = {
                .core_id = 0,
                .priority = 5,
                .stack_size = 4 * 1024,
#if CONFIG_SPIRAM_XIP_FROM_PSRAM
                .stack_in_ext = true,
#else
                .stack_in_ext = false,
#endif
            },
        },
        .encoder = {},
        .decoder = {},
        .afe = {
            .vad = hal::AudioProcessorAFE_VAD_Config{},
            .wakenet = hal::AudioProcessorAFE_WakeNetConfig{
                .model_partition_label = AUDIO_WAKEUP_WORD_MODEL_PARTITION_LABEL,
                .mn_language = AUDIO_WAKEUP_WORD_MN_LANGUAGE,
                .start_timeout_ms = AUDIO_WAKEUP_START_TIMEOUT_MS,
                .end_timeout_ms = AUDIO_WAKEUP_END_TIMEOUT_MS,
            },
        },
    };
    BROOKESIA_CHECK_FALSE_RETURN(
        hal::AudioDevice::get_instance().set_processor_config(std::move(processor_config)),
        false,
        "Failed to configure audio processor"
    );
    BROOKESIA_LOGI(
        "Audio processor AFE configured: model_partition(%1%), mn_language(%2%), wake_start_timeout_ms(%3%), "
        "wake_end_timeout_ms(%4%); agent AudioEncoder defaults keep enable_afe=true",
        AUDIO_WAKEUP_WORD_MODEL_PARTITION_LABEL,
        AUDIO_WAKEUP_WORD_MN_LANGUAGE,
        AUDIO_WAKEUP_START_TIMEOUT_MS,
        AUDIO_WAKEUP_END_TIMEOUT_MS
    );
#endif

    return true;
}

bool GeneralServices::start_audio_services()
{
    static auto child_binding = service::ServiceManager::get_instance().bind("ChildMode");
    BROOKESIA_CHECK_FALSE_RETURN(child_binding.is_valid(), false, "Failed to bind child policy service");
    // Called after the LVGL display source has started. Keep orientation sensing
    // alive even when no app is using audio or the Settings app is closed.
    static auto modes_binding = service::ServiceManager::get_instance().bind("DeviceModes");
    BROOKESIA_CHECK_FALSE_RETURN(modes_binding.is_valid(), false, "Failed to bind device modes");
    static auto rotation_binding = service::ServiceManager::get_instance().bind("AutoRotation");
    BROOKESIA_CHECK_FALSE_RETURN(rotation_binding.is_valid(), false, "Failed to bind auto rotation service");
    static auto phone_binding = service::ServiceManager::get_instance().bind("PhoneProvisioning");
    BROOKESIA_CHECK_FALSE_RETURN(phone_binding.is_valid(), false, "Failed to bind phone provisioning");

    if (!AudioPlaybackHelper::is_available()) {
        BROOKESIA_LOGW("Audio playback service is not available");
        return true;
    }

    auto &service_manager = service::ServiceManager::get_instance();
    static auto playback_binding = service_manager.bind(AudioPlaybackHelper::get_name().data());
    BROOKESIA_CHECK_FALSE_RETURN(playback_binding.is_valid(), false, "Failed to bind audio playback service");
    static auto offline_binding = service_manager.bind("OfflineVoice");
    BROOKESIA_CHECK_FALSE_RETURN(offline_binding.is_valid(), false, "Failed to bind offline voice");
    // Keep the service object alive while an app's asynchronous Disconnect finishes.
    static auto assistant_binding = service_manager.bind("VoiceAssistant");
    BROOKESIA_CHECK_FALSE_RETURN(assistant_binding.is_valid(), false, "Failed to bind voice assistant service");
    static auto local_voice_binding = service_manager.bind("LocalVoice");
    BROOKESIA_CHECK_FALSE_RETURN(local_voice_binding.is_valid(), false, "Failed to bind local voice service");

    return true;
}
