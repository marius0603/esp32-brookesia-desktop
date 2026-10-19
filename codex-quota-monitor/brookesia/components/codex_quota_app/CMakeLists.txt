idf_component_register(
    SRCS "codex_quota_app.cpp" "quota_feed.cpp" "quota_protocol.c" "quota_controls.cpp" "codex_quota_font.c"
    INCLUDE_DIRS "include"
    PRIV_INCLUDE_DIRS "."
    REQUIRES brookesia_core esp_timer
    WHOLE_ARCHIVE
)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wno-missing-field-initializers)
