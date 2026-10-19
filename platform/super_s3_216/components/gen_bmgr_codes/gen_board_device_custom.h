/*
 * SPDX-FileCopyrightText: 2025 Espressif Systems (Shanghai) CO., LTD
 * SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT
 *
 * Auto-generated custom device structure definitions
 * DO NOT MODIFY THIS FILE MANUALLY
 *
 * See LICENSE file for details.
 */

#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "dev_custom.h"

// Custom device structure definitions
// These structures are dynamically generated based on YAML configuration

// Structure definition for axp2101_power_manager
typedef struct {
    const char *name;           /*!< Custom device name */
    const char *type;           /*!< Device type: "custom" */
    const char *chip;           /*!< Chip name */
    int32_t      frequency;
    int8_t       i2c_addr;
    uint8_t     peripheral_count;
    const char *peripheral_name;
} dev_custom_axp2101_power_manager_config_t;

