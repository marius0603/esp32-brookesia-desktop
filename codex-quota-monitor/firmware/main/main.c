#include <assert.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "driver/gpio.h"
#include "driver/usb_serial_jtag.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "esp_check.h"
#include "quota_state.h"
#include "quota_hardware.h"

static SemaphoreHandle_t snapshot_lock;
static SemaphoreHandle_t transmit_lock;
static quota_snapshot_t snapshot;
static int64_t last_refresh_ms = -15000;

void quota_copy_snapshot(quota_snapshot_t *out)
{
    xSemaphoreTake(snapshot_lock, portMAX_DELAY);
    *out = snapshot;
    xSemaphoreGive(snapshot_lock);
}

static void usb_send(const char *message)
{
    if (xSemaphoreTake(transmit_lock, pdMS_TO_TICKS(25)) == pdTRUE) {
        usb_serial_jtag_write_bytes(message, strlen(message), pdMS_TO_TICKS(25));
        xSemaphoreGive(transmit_lock);
    }
}

void quota_request_refresh(void)
{
    int64_t now = esp_timer_get_time() / 1000;
    if (now - last_refresh_ms < 15000) return;
    last_refresh_ms = now;
    usb_send("{\"type\":\"refresh\",\"v\":1}\n");
}

static void usb_task(void *unused)
{
    char line[QUOTA_MAX_FRAME + 1];
    size_t length = 0;
    bool overflow = false;
    int64_t last_hello = -5000;
    uint8_t buffer[256];
    while (true) {
        int64_t now = esp_timer_get_time() / 1000;
        if (now - last_hello >= 5000) {
            usb_send("{\"type\":\"hello\",\"device\":\"codex-quota-monitor\",\"v\":1}\n");
            last_hello = now;
        }
        int count = usb_serial_jtag_read_bytes(buffer, sizeof(buffer), pdMS_TO_TICKS(100));
        for (int i = 0; i < count; ++i) {
            char ch = (char)buffer[i];
            if (ch == '\n') {
                if (!overflow && length) {
                    line[length] = 0;
                    quota_snapshot_t next;
                    if (quota_parse(line, length + 1, esp_timer_get_time() / 1000, &next)) {
                        xSemaphoreTake(snapshot_lock, portMAX_DELAY);
                        snapshot = next;
                        xSemaphoreGive(snapshot_lock);
                        char acknowledgement[256];
                        int volume = -1;
                        quota_get_volume(&volume);
                        snprintf(acknowledgement, sizeof(acknowledgement),
                                 "{\"type\":\"ack\",\"v\":1,\"sampled_at\":%" PRId64 ",\"windows\":%d,\"firmware\":\"0.3.0\",\"volume\":%d,\"audio_ready\":%s,\"pmu_ready\":%s,\"uptime_ms\":%" PRId64 "}\n",
                                 next.sampled_at, next.count, volume, quota_audio_ready() ? "true" : "false",
                                 quota_power_ready() ? "true" : "false", esp_timer_get_time() / 1000);
                        usb_send(acknowledgement);
                    }
                }
                length = 0;
                overflow = false;
            } else if (!overflow) {
                if (length < QUOTA_MAX_FRAME - 1 && ch != 0) line[length++] = ch;
                else overflow = true;
            }
        }
    }
}

static void button_task(void *unused)
{
    bool last_raw = false, stable = false, long_sent = false;
    int64_t changed_at = 0, pressed_at = 0;
    while (true) {
        int64_t now = esp_timer_get_time() / 1000;
        bool raw = gpio_get_level(GPIO_NUM_18) == 0;
        if (raw != last_raw) { last_raw = raw; changed_at = now; }
        if (raw != stable && now - changed_at >= 40) {
            stable = raw;
            if (stable) { pressed_at = now; long_sent = false; }
            else if (!long_sent) quota_key_event(false);
        }
        if (stable && !long_sent && now - pressed_at >= 1000) {
            quota_key_event(true);
            long_sent = true;
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}

void app_main(void)
{
    esp_err_t error = nvs_flash_init();
    // Never erase NVS automatically on a board that might contain existing settings.
    ESP_ERROR_CHECK(error);
    snapshot_lock = xSemaphoreCreateMutex();
    transmit_lock = xSemaphoreCreateMutex();
    assert(snapshot_lock && transmit_lock);
    usb_serial_jtag_driver_config_t usb = {.tx_buffer_size = 4096, .rx_buffer_size = 4096};
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb));
    gpio_config_t key = {.pin_bit_mask = 1ULL << GPIO_NUM_18, .mode = GPIO_MODE_INPUT, .pull_up_en = GPIO_PULLUP_ENABLE};
    ESP_ERROR_CHECK(gpio_config(&key));
    quota_ui_start();
    BaseType_t created = xTaskCreate(usb_task, "quota_usb", 6144, NULL, 5, NULL);
    assert(created == pdPASS);
    created = xTaskCreate(button_task, "quota_key", 3072, NULL, 4, NULL);
    assert(created == pdPASS);
}
