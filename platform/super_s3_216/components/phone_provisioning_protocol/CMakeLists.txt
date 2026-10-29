idf_component_register(SRCS src/network_config.c src/network_scan.c
    proto-c/network_config.pb-c.c proto-c/network_scan.pb-c.c proto-c/network_constants.pb-c.c
    INCLUDE_DIRS include proto-c REQUIRES esp_wifi esp_netif protobuf-c protocomm)
target_compile_definitions(${COMPONENT_LIB} PUBLIC
    CONFIG_NETWORK_PROV_NETWORK_TYPE_WIFI=1 CONFIG_NETWORK_PROV_SCAN_MAX_ENTRIES=16)
