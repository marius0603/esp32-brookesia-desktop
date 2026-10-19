#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#define QUOTA_MAX_FRAME 2048
#define QUOTA_MAX_WINDOWS 2
typedef struct {
    int minutes;
    float used;
    int64_t reset_at;
} codex_quota_window_t;
typedef struct {
    bool received;
    bool has_sample;
    char status[24];
    char plan[24];
    char bucket[48];
    int count;
    codex_quota_window_t windows[QUOTA_MAX_WINDOWS];
    int64_t sent_at;
    int64_t sampled_at;
    int64_t received_ms;
    int stale_after;
    int warning;
    int critical;
} codex_quota_snapshot_t;
#ifdef __cplusplus
extern "C" {
#endif
bool codex_quota_parse(const char *line, size_t length, int64_t received_ms, codex_quota_snapshot_t *out);
int64_t codex_quota_estimated_now(const codex_quota_snapshot_t *snapshot, int64_t now_ms);
const char *codex_quota_status(const codex_quota_snapshot_t *snapshot, int64_t now_ms);
void codex_quota_copy_snapshot(codex_quota_snapshot_t *out);
#ifdef __cplusplus
}
#endif
