# GCC 15 checks the promoted 4-bit compression-method field as int, while
# LV_PRIu32 expects uint32_t. Compile a local variant, keeping vendor sources intact.
s3_audio_source_override(lvgl__lvgl "src/libs/bin_decoder/lv_bin_decoder.c"
    [[LV_LOG_WARN("Unknown compression method: %" LV_PRIu32, compressed->method);]]
    [[LV_LOG_WARN("Unknown compression method: %" LV_PRIu32, (uint32_t)compressed->method);]])
