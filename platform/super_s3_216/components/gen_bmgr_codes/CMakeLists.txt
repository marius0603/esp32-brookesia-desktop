# Board information output
message(STATUS "Selected Board: esp32_s3_touch_amoled_2_16")
get_filename_component(S3_216_BOARD_PATH "${CMAKE_CURRENT_LIST_DIR}/../../../../../hal/brookesia_hal_boards/boards/waveshare/esp32_s3_touch_amoled_2_16" ABSOLUTE)
message(STATUS "Board Path: ${S3_216_BOARD_PATH}")

idf_component_register(
    SRC_DIRS "." "${S3_216_BOARD_PATH}"
    INCLUDE_DIRS "." "${S3_216_BOARD_PATH}"
    REQUIRES esp_board_manager
)

# This is equivalent to adding WHOLE_ARCHIVE option to the idf_component_register call above:
idf_component_set_property(${COMPONENT_NAME} WHOLE_ARCHIVE TRUE)
