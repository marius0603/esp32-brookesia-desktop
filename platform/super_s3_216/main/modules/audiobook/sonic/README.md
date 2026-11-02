# Sonic speech time stretching

Upstream: https://github.com/waywardgeek/sonic
Pinned commit: b93885dcb70aae50c6f76b0fe4e0868f029a077e
Files: sonic.c, sonic.h, LICENSE (Apache-2.0).

Local adaptation: on ESP_PLATFORM, calloc/realloc/free use PSRAM heap capabilities. Other processing code is unchanged. The audiobook decoder resamples to 16kHz mono before passing samples to Sonic; speed varies while pitch/rate remain at 1. Stereo duplication and the bounded speaker queue follow time stretching. No cloud request is involved.
