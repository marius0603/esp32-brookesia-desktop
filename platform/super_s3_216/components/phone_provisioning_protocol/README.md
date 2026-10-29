# Provisioning protocol codecs

This deliberately small source component contains the Wi-Fi config/scan codecs,
public callback headers and generated protobuf-C files from Espressif's
`idf-extra-components/network_provisioning`. The upstream revision and original
file hashes are recorded in `UPSTREAM.json`; Apache-2.0 terms are in `LICENSE`.
These are required protocol sources, not a downloaded build/dependency cache.

Only config/scan codecs are compiled. The upstream provisioning manager, network
driver ownership, SoftAP transport and Thread implementation are not included.
The board supplies callbacks that use its existing Brookesia Wi-Fi service, while
ESP-IDF's protocomm BLE transport and Security 1 implement the authenticated,
encrypted session. This retains compatibility with the official Android app.

One local correction in `src/network_config.c` allocates/copies the binary BSSID
as six bytes instead of using `strndup`, which can truncate a BSSID containing a
zero byte. The original hash remains recorded for provenance; this adaptation is
listed explicitly in the metadata.
