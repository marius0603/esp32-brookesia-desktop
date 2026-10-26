#pragma once
#include <cstdint>

namespace screen_lock {
// Count completed short presses, never autorepeat events from a held key.
class DoublePress {
public:
    static constexpr uint32_t max_press_ms = 350;
    static constexpr uint32_t interval_ms = 650;
    void reset() { down_ = pending_ = false; }
    void press(uint32_t now) {
        if (down_) return;
        down_ = true;
        pressed_at_ = now;
    }
    bool release(uint32_t now) {
        if (!down_) return false;
        down_ = false;
        if (now - pressed_at_ > max_press_ms) {
            pending_ = false;
            return false;
        }
        if (pending_ && now - released_at_ <= interval_ms) {
            pending_ = false;
            return true;
        }
        pending_ = true;
        released_at_ = now;
        return false;
    }
    void expire(uint32_t now) {
        if (pending_ && now - released_at_ > interval_ms) pending_ = false;
    }
    unsigned pending() const { return pending_ ? 1U : 0U; }
private:
    bool down_ = false, pending_ = false;
    uint32_t pressed_at_ = 0, released_at_ = 0;
};
}
