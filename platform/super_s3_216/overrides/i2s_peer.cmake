# Restore a released direction without destroying the live full-duplex peer.
set(peer_source "${CMAKE_BINARY_DIR}/s3_audio_overrides/periph_i2s.c")
file(READ "${peer_source}" content)
set(needle "    if (i2s_chan_handles[config->port].chan_out == NULL &&")
string(FIND "${content}" "${needle}" found)
if(found EQUAL -1)
    message(FATAL_ERROR "I2S peer override no longer matches")
endif()
string(REPLACE "${needle}" "    periph_i2s_chan_t previous = i2s_chan_handles[config->port];\n${needle}" content "${content}")
set(needle "    }\n    if (err != ESP_OK) {\n        ESP_LOGE(TAG, \"I2S[%d] new channel failed")
set(replacement "    } else if (config->mode != I2S_COMM_MODE_PDM) {\n        if (!i2s_chan_handles[config->port].chan_out) {\n            err = i2s_new_channel(&chan_cfg, &i2s_chan_handles[config->port].chan_out, NULL);\n        }\n        if (err == ESP_OK && !i2s_chan_handles[config->port].chan_in) {\n            err = i2s_new_channel(&chan_cfg, NULL, &i2s_chan_handles[config->port].chan_in);\n        }\n    }\n    if (err != ESP_OK) {\n        ESP_LOGE(TAG, \"I2S[%d] new channel failed")
string(FIND "${content}" "${needle}" found)
if(found EQUAL -1)
    message(FATAL_ERROR "I2S missing-direction allocation no longer matches")
endif()
string(REPLACE "${needle}" "${replacement}" content "${content}")
set(start "    if (err != ESP_OK) {\n        if (i2s_chan_handles[config->port].chan_in) {")
string(FIND "${content}" "${start}" begin)
string(FIND "${content}" "    if (config->direction == I2S_DIR_TX) {\n        *periph_handle" end)
if(begin EQUAL -1 OR end EQUAL -1)
    message(FATAL_ERROR "I2S error cleanup no longer matches")
endif()
string(SUBSTRING "${content}" 0 ${begin} prefix)
string(SUBSTRING "${content}" ${end} -1 suffix)
set(cleanup [=[    if (err != ESP_OK) {
        periph_i2s_chan_t *current = &i2s_chan_handles[config->port];
        if (current->chan_in && (!previous.chan_in || !previous.in_en)) {
            i2s_channel_disable(current->chan_in);
            if (i2s_del_channel(current->chan_in) == ESP_OK) {
                previous.chan_in = NULL;
                previous.in_en = false;
            }
        }
        if (current->chan_out && (!previous.chan_out || !previous.out_en)) {
            i2s_channel_disable(current->chan_out);
            if (i2s_del_channel(current->chan_out) == ESP_OK) {
                previous.chan_out = NULL;
                previous.out_en = false;
            }
        }
        *current = previous;
        ESP_LOGE(TAG, "I2S[%d] initialize failed: %d", config->port, err);
        return -1;
    }
]=])
file(WRITE "${peer_source}" "${prefix}${cleanup}${suffix}")
