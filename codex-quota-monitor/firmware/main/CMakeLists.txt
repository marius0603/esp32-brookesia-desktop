idf_component_register(
    SRCS "main.c" "quota_state.c" "quota_ui.c" "quota_hardware.c" "quota_font.c"
    INCLUDE_DIRS "."
    REQUIRES json driver esp_timer nvs_flash esp_driver_usb_serial_jtag
)
