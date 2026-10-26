# ESP-SR 2.4.5 SD loader: safe missing files and repeated init/deinit.
s3_audio_source_override(espressif__esp-sr "src/model_path.c"
    "fclose(fp);" "if (fp) fclose(fp);")
idf_component_get_property(sr_lib espressif__esp-sr COMPONENT_LIB)
set(sr_sd_source "${CMAKE_BINARY_DIR}/s3_audio_overrides/model_path.c")
file(READ "${sr_sd_source}" content)
string(REPLACE "        free(models);\n    }\n    models = NULL;\n}\n\nsrmodel_list_t *esp_srmodel_init"
    "        free(models->model_name);\n        free(models->model_info);\n        free(models);\n    }\n    static_srmodels = NULL;\n    srmodel_init_refcount = 0;\n}\n\nsrmodel_list_t *esp_srmodel_init" content "${content}")
string(REPLACE "#ifdef ESP_PLATFORM\n    return srmodel_mmap_deinit(models);"
    "#if defined(ESP_PLATFORM) && !defined(CONFIG_MODEL_IN_SDCARD)\n    return srmodel_mmap_deinit(models);" content "${content}")
file(WRITE "${sr_sd_source}" "${content}")
