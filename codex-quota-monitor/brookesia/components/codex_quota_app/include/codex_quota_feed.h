#pragma once
#include <stdbool.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Call from the host firmware's existing transport after receiving one complete JSON line. */
bool codex_quota_feed_json(const char *json, size_t length);
const char *codex_quota_protocol_hello(void);
typedef void (*codex_quota_refresh_callback_t)(void *context);
void codex_quota_set_refresh_callback(codex_quota_refresh_callback_t callback, void *context);
bool codex_quota_request_refresh(void);
#ifdef __cplusplus
}
#endif
