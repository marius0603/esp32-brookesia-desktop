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
} quota_window_t;

typedef struct {
    bool received;
    bool has_sample;
    char status[24];
    char plan[24];
    char bucket[48];
    int count;
    quota_window_t windows[QUOTA_MAX_WINDOWS];
    int64_t sent_at;
    int64_t sampled_at;
    int64_t received_ms;
    int stale_after;
    int warning;
    int critical;
} quota_snapshot_t;

// On invalid input the previous good snapshot is left untouched.
bool quota_parse(const char *line, size_t length, int64_t received_ms, quota_snapshot_t *out);
int64_t quota_estimated_now(const quota_snapshot_t *snapshot, int64_t now_ms);
const char *quota_status(const quota_snapshot_t *snapshot, int64_t now_ms);

void quota_copy_snapshot(quota_snapshot_t *out);
void quota_request_refresh(void);
void quota_ui_start(void);
void quota_key_event(bool long_press);
