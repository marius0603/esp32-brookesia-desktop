/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * Auto-generated device configuration file
 * DO NOT MODIFY THIS FILE MANUALLY
 *
 * See LICENSE file for details.
 */

#include <stdlib.h>
#include "esp_board_device.h"
#include "dev_audio_codec.h"
#include "dev_custom.h"
#include "dev_display_lcd.h"
#include "dev_fs_fat.h"
#include "dev_lcd_touch.h"
#include "driver/sdmmc_host.h"
#include "sdmmc_cmd.h"
#include "gen_board_device_custom.h"

// Device configuration structures
const static dev_custom_axp2101_power_manager_config_t esp_bmgr_axp2101_power_manager_cfg = {
    .name = "axp2101_power_manager",
    .type = "custom",
    .chip = "axp2101",
    .frequency = 400000,
    .i2c_addr = 52,
    .peripheral_count = 1,
    .peripheral_name = "i2c_master",
};

const static dev_audio_codec_config_t esp_bmgr_audio_dac_cfg = {
    .name = "audio_dac",
    .chip = "es8311",
    .type = "audio_codec",
    .data_if_type = 0,
    .adc_enabled = false,
    .adc_max_channel = 0,
    .adc_channel_mask = 0x3,
    .adc_channel_labels = "",
    .adc_init_gain = 0,
    .dac_enabled = true,
    .dac_max_channel = 1,
    .dac_channel_mask = 0x1,
    .dac_init_gain = 0,
    .pa_cfg = {
        .name = "gpio_pa_control",
        .port = 46,
        .active_level = 1,
        .gain = 6.0,
    },
    .i2c_cfg = {
        .name = "i2c_master",
        .port = 0,
        .address = 48,
        .frequency = 400000,
    },
    .i2s_cfg = {
        .name = "i2s_audio_out",
        .port = 0,
        .clk_src = 0,
        .tx_aux_out_io = -1,
        .tx_aux_out_line = 0,
        .tx_aux_out_invert = false,
    },
    .adc_cfg = {
        .periph_name = NULL,
        .sample_rate_hz = 0,
        .max_store_buf_size = 0,
        .conv_frame_size = 0,
        .conv_mode = 0,
        .format = 0,
        .pattern_num = 0,
        .cfg_mode = 0,
        .cfg = {
            .single_unit = {
                .unit_id = 0,
                .atten = 0,
                .bit_width = 0,
                .channel_id = {},
            },
        },
    },
    .metadata = NULL,
    .metadata_size = 0,
    .mclk_enabled = true,
    .aec_enabled = false,
    .eq_enabled = false,
    .alc_enabled = false,
};

const static dev_audio_codec_config_t esp_bmgr_audio_adc_cfg = {
    .name = "audio_adc",
    .chip = "es7210",
    .type = "audio_codec",
    .data_if_type = 0,
    .adc_enabled = true,
    .adc_max_channel = 2,
    .adc_channel_mask = 0x7,
    .adc_channel_labels = "NA,RE,FR,FL",
    .adc_init_gain = 0,
    .dac_enabled = false,
    .dac_max_channel = 0,
    .dac_channel_mask = 0x0,
    .dac_init_gain = 0,
    .pa_cfg = {
        .name = NULL,
        .port = -1,
        .active_level = 0,
        .gain = 0.0,
    },
    .i2c_cfg = {
        .name = "i2c_master",
        .port = 0,
        .address = 128,
        .frequency = 400000,
    },
    .i2s_cfg = {
        .name = "i2s_audio_in",
        .port = 0,
        .clk_src = 0,
        .tx_aux_out_io = -1,
        .tx_aux_out_line = 0,
        .tx_aux_out_invert = false,
    },
    .adc_cfg = {
        .periph_name = NULL,
        .sample_rate_hz = 0,
        .max_store_buf_size = 0,
        .conv_frame_size = 0,
        .conv_mode = 0,
        .format = 0,
        .pattern_num = 0,
        .cfg_mode = 0,
        .cfg = {
            .single_unit = {
                .unit_id = 0,
                .atten = 0,
                .bit_width = 0,
                .channel_id = {},
            },
        },
    },
    .metadata = NULL,
    .metadata_size = 0,
    .mclk_enabled = false,
    .aec_enabled = false,
    .eq_enabled = false,
    .alc_enabled = false,
};

const static dev_display_lcd_config_t esp_bmgr_display_lcd_cfg = {
    .name = "display_lcd",
    .chip = "co5300",
    .sub_type = "spi",
    .lcd_width = 480,
    .lcd_height = 480,
    .swap_xy = false,
    .mirror_x = false,
    .mirror_y = false,
    .need_reset = false,
    .invert_color = false,
    .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB,
    .data_endian = LCD_RGB_DATA_ENDIAN_BIG,
    .bits_per_pixel = 16,
    .sub_cfg = {
        .spi = {
            .spi_name = "spi_display",
            .panel_config = {
                .reset_gpio_num = 39,
                .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB,
                .data_endian = LCD_RGB_DATA_ENDIAN_BIG,
                .bits_per_pixel = 16,
                .flags = {
                    .reset_active_high = false,
                },
                .vendor_config = NULL,
            },
            .io_spi_config = {
                .cs_gpio_num = 12,
                .dc_gpio_num = -1,
                .spi_mode = 0,
                .pclk_hz = 40000000,
                .trans_queue_depth = 1,
                .lcd_cmd_bits = 32,
                .lcd_param_bits = 8,
                .cs_ena_pretrans = 0,
                .cs_ena_posttrans = 0,
                .flags = {
                    .dc_high_on_cmd = false,
                    .dc_low_on_data = false,
                    .dc_low_on_param = false,
                    .octal_mode = false,
                    .quad_mode = true,
                    .sio_mode = false,
                    .lsb_first = false,
                    .cs_high_active = false,
                },
            },
        },
    },
};

const static dev_lcd_touch_config_t esp_bmgr_lcd_touch_cfg = {
    .name = "lcd_touch",
    .chip = "cst9217",
    .type = "lcd_touch",
    .sub_type = "i2c",
    .touch_config = {
        .x_max = 480,
        .y_max = 480,
        .rst_gpio_num = 40,
        .int_gpio_num = 11,
        .levels = {
            .reset = 0,
            .interrupt = 0,
        },
        .flags = {
            .swap_xy = false,
            .mirror_x = false,
            .mirror_y = false,
        },
        .process_coordinates = NULL,
        .interrupt_callback = NULL,
        .user_data = NULL,
        .driver_data = NULL,
    },
    .sub_cfg = {
        .i2c = {
            .i2c_name = "i2c_master",
            .i2c_addr_count = 1,
            .i2c_addr = {0xb4, 0x00, 0x00, 0x00},
            .io_i2c_config = {
                .dev_addr = 0,
                .control_phase_bytes = 1,
                .dc_bit_offset = 0,
                .lcd_cmd_bits = 8,
                .lcd_param_bits = 0,
                .scl_speed_hz = 400000,
                .flags = {
                    .dc_low_on_data = false,
                    .disable_control_phase = true,
                },
            },
        },
    },
};

const static dev_fs_fat_config_t esp_bmgr_fs_sdcard_cfg = {
    .name = "fs_sdcard",
    .mount_point = "/sdcard",
    .frequency = SDMMC_FREQ_HIGHSPEED,
    .vfs_config = {
        .format_if_mount_failed = false,
        .max_files = 5,
        .allocation_unit_size = 16384,
    },
    .sub_type = "sdmmc",
    .sub_cfg = {
        .sdmmc = {
            .slot = SDMMC_HOST_SLOT_1,
            .bus_width = 1,
            .slot_flags = SDMMC_SLOT_FLAG_INTERNAL_PULLUP,
            .pins = {
                .clk = 2,
                .cmd = 1,
                .d0 = 3,
                .d1 = -1,
                .d2 = -1,
                .d3 = -1,
                .d4 = -1,
                .d5 = -1,
                .d6 = -1,
                .d7 = -1,
                .cd = -1,
                .wp = -1,
            },
            .ldo_chan_id = -1,
        },
    },
};

// Device descriptor array
static const char* esp_bmgr_audio_dac_deps[] = {
    "axp2101_power_manager",
};
static const char* esp_bmgr_audio_adc_deps[] = {
    "axp2101_power_manager",
};
static const char* esp_bmgr_display_lcd_deps[] = {
    "axp2101_power_manager",
};
static const char* esp_bmgr_lcd_touch_deps[] = {
    "axp2101_power_manager",
};

const esp_board_device_desc_t g_esp_board_devices[] = {
    {
        .next = &g_esp_board_devices[1],
        .name = "axp2101_power_manager",
        .chip = "axp2101",
        .type = "custom",
        .sub_type = NULL,
        .cfg = &esp_bmgr_axp2101_power_manager_cfg,
        .cfg_size = sizeof(esp_bmgr_axp2101_power_manager_cfg),
        .init_skip = false,
        .depends_on = NULL,
        .depends_on_num = 0,
    },
    {
        .next = &g_esp_board_devices[2],
        .name = "audio_dac",
        .chip = "es8311",
        .type = "audio_codec",
        .sub_type = NULL,
        .cfg = &esp_bmgr_audio_dac_cfg,
        .cfg_size = sizeof(esp_bmgr_audio_dac_cfg),
        .init_skip = false,
        .depends_on = esp_bmgr_audio_dac_deps,
        .depends_on_num = 1,
    },
    {
        .next = &g_esp_board_devices[3],
        .name = "audio_adc",
        .chip = "es7210",
        .type = "audio_codec",
        .sub_type = NULL,
        .cfg = &esp_bmgr_audio_adc_cfg,
        .cfg_size = sizeof(esp_bmgr_audio_adc_cfg),
        .init_skip = false,
        .depends_on = esp_bmgr_audio_adc_deps,
        .depends_on_num = 1,
    },
    {
        .next = &g_esp_board_devices[4],
        .name = "display_lcd",
        .chip = "co5300",
        .type = "display_lcd",
        .sub_type = "spi",
        .cfg = &esp_bmgr_display_lcd_cfg,
        .cfg_size = sizeof(esp_bmgr_display_lcd_cfg),
        .init_skip = false,
        .depends_on = esp_bmgr_display_lcd_deps,
        .depends_on_num = 1,
    },
    {
        .next = &g_esp_board_devices[5],
        .name = "lcd_touch",
        .chip = "cst9217",
        .type = "lcd_touch",
        .sub_type = "i2c",
        .cfg = &esp_bmgr_lcd_touch_cfg,
        .cfg_size = sizeof(esp_bmgr_lcd_touch_cfg),
        .init_skip = false,
        .depends_on = esp_bmgr_lcd_touch_deps,
        .depends_on_num = 1,
    },
    {
        .next = NULL,
        .name = "fs_sdcard",
        .chip = NULL,
        .type = "fs_fat",
        .sub_type = "sdmmc",
        .cfg = &esp_bmgr_fs_sdcard_cfg,
        .cfg_size = sizeof(esp_bmgr_fs_sdcard_cfg),
        .init_skip = false,
        .depends_on = NULL,
        .depends_on_num = 0,
    },
};
