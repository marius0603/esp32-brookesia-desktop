#include "quota_state.h"
#include "cJSON.h"
#include <math.h>
#include <string.h>
#include <stdio.h>

static bool number(const cJSON *item, double low, double high)
{
    return cJSON_IsNumber(item) && isfinite(item->valuedouble) && item->valuedouble >= low && item->valuedouble <= high;
}

static bool integer(const cJSON *item, double low, double high)
{
    return number(item, low, high) && floor(item->valuedouble) == item->valuedouble;
}

static void copy_string(char *dest, size_t capacity, const cJSON *item, const char *fallback)
{
    snprintf(dest, capacity, "%s", cJSON_IsString(item) ? item->valuestring : fallback);
}

bool quota_parse(const char *line, size_t length, int64_t received_ms, quota_snapshot_t *out)
{
    if (!line || !out || length == 0 || length > QUOTA_MAX_FRAME) return false;
    cJSON *root = cJSON_ParseWithLength(line, length);
    if (!cJSON_IsObject(root)) { cJSON_Delete(root); return false; }
    bool valid = false;
    quota_snapshot_t next = {.received = true, .received_ms = received_ms, .stale_after = 180, .warning = 20, .critical = 10};
    const cJSON *type = cJSON_GetObjectItemCaseSensitive(root, "type");
    const cJSON *version = cJSON_GetObjectItemCaseSensitive(root, "v");
    const cJSON *sent = cJSON_GetObjectItemCaseSensitive(root, "sent_at");
    const cJSON *sample = cJSON_GetObjectItemCaseSensitive(root, "sampled_at");
    const cJSON *windows = cJSON_GetObjectItemCaseSensitive(root, "windows");
    if (!cJSON_IsString(type) || strcmp(type->valuestring, "quota") || !integer(version, 1, 1) ||
        !integer(sent, 1, 9007199254740991.0) || !cJSON_IsArray(windows) || cJSON_GetArraySize(windows) > QUOTA_MAX_WINDOWS) goto done;
    next.sent_at = (int64_t)sent->valuedouble;
    next.has_sample = integer(sample, 1, 9007199254740991.0);
    if (next.has_sample) next.sampled_at = (int64_t)sample->valuedouble;
    copy_string(next.status, sizeof(next.status), cJSON_GetObjectItemCaseSensitive(root, "status"), "error");
    if (strcmp(next.status, "ok") && strcmp(next.status, "starting") && strcmp(next.status, "error") && strcmp(next.status, "auth_required")) goto done;
    copy_string(next.plan, sizeof(next.plan), cJSON_GetObjectItemCaseSensitive(root, "plan"), "");
    copy_string(next.bucket, sizeof(next.bucket), cJSON_GetObjectItemCaseSensitive(root, "bucket"), "codex");
    const cJSON *stale = cJSON_GetObjectItemCaseSensitive(root, "stale_after");
    const cJSON *warning = cJSON_GetObjectItemCaseSensitive(root, "warning");
    const cJSON *critical = cJSON_GetObjectItemCaseSensitive(root, "critical");
    if (integer(stale, 30, 86400)) next.stale_after = stale->valueint;
    if (integer(warning, 1, 100) && integer(critical, 0, warning->valueint - 1)) {
        next.warning = warning->valueint;
        next.critical = critical->valueint;
    }
    const cJSON *item;
    cJSON_ArrayForEach(item, windows) {
        const cJSON *used = cJSON_GetObjectItemCaseSensitive(item, "used");
        const cJSON *minutes = cJSON_GetObjectItemCaseSensitive(item, "minutes");
        const cJSON *reset = cJSON_GetObjectItemCaseSensitive(item, "reset_at");
        if (!number(used, 0, 100) || !integer(minutes, 1, 52560000)) goto done;
        quota_window_t *window = &next.windows[next.count++];
        window->used = (float)used->valuedouble;
        window->minutes = minutes->valueint;
        if (integer(reset, 1, 9007199254740991.0)) window->reset_at = (int64_t)reset->valuedouble;
    }
    if (!strcmp(next.status, "ok") && (!next.has_sample || next.count == 0)) goto done;
    if (next.count && !next.has_sample) goto done;
    *out = next;
    valid = true;
done:
    cJSON_Delete(root);
    return valid;
}

int64_t quota_estimated_now(const quota_snapshot_t *snapshot, int64_t now_ms)
{
    int64_t elapsed = now_ms - snapshot->received_ms;
    return snapshot->sent_at + (elapsed > 0 ? elapsed / 1000 : 0);
}

const char *quota_status(const quota_snapshot_t *snapshot, int64_t now_ms)
{
    if (!snapshot->received || now_ms - snapshot->received_ms > 8000) return "offline";
    if (snapshot->has_sample && quota_estimated_now(snapshot, now_ms) - snapshot->sampled_at > snapshot->stale_after) return "stale";
    return snapshot->status;
}
