#pragma once
#include <stdbool.h>
#include "esp_err.h"
void quota_hardware_init(int volume);
bool quota_audio_ready(void);
bool quota_power_ready(void);
bool quota_get_volume(int *volume);
bool quota_set_volume(int volume);
esp_err_t quota_power_off(void);
