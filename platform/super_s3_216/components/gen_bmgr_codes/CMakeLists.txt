# Board information output
message(STATUS "Selected Board: esp32_s3_touch_amoled_2_16")
message(STATUS "Board Path: D:/chatgpt_data/esp-brookesia-v08/hal/brookesia_hal_boards/boards/waveshare/esp32_s3_touch_amoled_2_16")

idf_component_register(
    SRC_DIRS "." "../../../../../hal/brookesia_hal_boards/boards/waveshare/esp32_s3_touch_amoled_2_16"
    INCLUDE_DIRS "." "../../../../../hal/brookesia_hal_boards/boards/waveshare/esp32_s3_touch_amoled_2_16"
    REQUIRES esp_board_manager
)

# This is equivalent to adding WHOLE_ARCHIVE option to the idf_component_register call above:
idf_component_set_property(${COMPONENT_NAME} WHOLE_ARCHIVE TRUE)
