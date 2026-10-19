#include "quota_hardware.h"
#include "bsp/esp-bsp.h"
#include "driver/i2c_master.h"
#include "esp_codec_dev.h"
#include "esp_log.h"

static const char *TAG = "quota_hardware";
static esp_codec_dev_handle_t speaker;
static i2c_master_dev_handle_t pmu;
static bool power_ready;

void quota_hardware_init(int volume)
{
    if (bsp_i2c_init() != ESP_OK) return;
    i2c_device_config_t config = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7, .device_address = 0x34, .scl_speed_hz = 100000,
    };
    if (i2c_master_bus_add_device(bsp_i2c_get_handle(), &config, &pmu) == ESP_OK) {
        uint8_t reg = 0x03, id = 0;
        power_ready = i2c_master_transmit_receive(pmu, &reg, 1, &id, 1, 100) == ESP_OK && id == 0x4a;
    }
    speaker = bsp_audio_codec_speaker_init();
    if (speaker) {
        esp_codec_dev_sample_info_t sample = {.sample_rate = 22050, .channel = 1, .bits_per_sample = 16};
        if (esp_codec_dev_open(speaker, &sample) != ESP_CODEC_DEV_OK ||
            esp_codec_dev_set_out_vol(speaker, volume) != ESP_CODEC_DEV_OK) {
            esp_codec_dev_close(speaker);
            esp_codec_dev_delete(speaker);
            speaker = NULL;
        }
    }
    ESP_LOGI(TAG, "ES8311=%s AXP2101=%s", speaker ? "ready" : "unavailable", power_ready ? "ready" : "unavailable");
}
bool quota_audio_ready(void) { return speaker != NULL; }
bool quota_power_ready(void) { return power_ready; }
bool quota_get_volume(int *volume)
{
    return speaker && volume && esp_codec_dev_get_out_vol(speaker, volume) == ESP_CODEC_DEV_OK;
}
bool quota_set_volume(int volume)
{
    if (volume < 0 || volume > 100) return false;
    return speaker && esp_codec_dev_set_out_vol(speaker, volume) == ESP_CODEC_DEV_OK;
}
esp_err_t quota_power_off(void)
{
    if (!power_ready) return ESP_ERR_INVALID_STATE;
    /* Same read/modify/write as the official XPowers AXP2101 shutdown():
       COMMON_CONFIG (0x10), bit 0. Preserve every other bit and all rail settings. */
    uint8_t reg = 0x10, data[2] = {0x10, 0};
    esp_err_t err = i2c_master_transmit_receive(pmu, &reg, 1, &data[1], 1, 100);
    if (err != ESP_OK) return err;
    data[1] |= 1;
    if (speaker) esp_codec_dev_set_out_mute(speaker, true);
    err = i2c_master_transmit(pmu, data, sizeof(data), 100);
    if (err != ESP_OK && speaker) esp_codec_dev_set_out_mute(speaker, false);
    return err;
}
