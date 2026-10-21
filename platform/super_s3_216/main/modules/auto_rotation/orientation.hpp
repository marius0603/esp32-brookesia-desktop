#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace board_orientation {
// Reject flat, diagonal and strongly accelerating poses rather than guessing.
constexpr float abs_g(float value) { return value < 0 ? -value : value; }
constexpr int classify(float x, float y, float z) {
    const float magnitude = x*x + y*y + z*z;
    const float dominant = std::max(abs_g(x), abs_g(y));
    const float minor = std::min(abs_g(x), abs_g(y));
    if (magnitude < .55F || magnitude > 1.65F || dominant < .60F ||
            abs_g(z) > .80F || dominant < minor * 1.40F) return -1;
    if (abs_g(y) >= abs_g(x)) return y > 0 ? 0 : 180;
    return x > 0 ? 270 : 90;
}
// The IMU orientation is viewed from the rear of this board. Reverse its
// handedness after calibration; the normal pose and 180 degrees stay fixed.
constexpr int screen_angle(int pose, int calibration_offset) {
    return (360 - (pose + calibration_offset) % 360) % 360;
}
constexpr void inverse_touch(int16_t &x, int16_t &y, int degrees) {
    const int16_t px = std::clamp<int16_t>(x, 0, 479);
    const int16_t py = std::clamp<int16_t>(y, 0, 479);
    switch (degrees) {
    case 90: x = py; y = 479-px; break;
    case 180: x = 479-px; y = 479-py; break;
    case 270: x = 479-py; y = px; break;
    default: x = px; y = py; break;
    }
}
}
