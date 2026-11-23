#include "clock_utc.hpp"

#include <array>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <ctime>
#include <optional>
#include <sys/time.h>

#include "driver/i2c_master.h"
#include "esp_board_manager.h"
#include "esp_log.h"
#include "esp_timer.h"

namespace board_clock {
namespace {
using namespace std::chrono;

constexpr char TAG[] = "BoardClock";
constexpr uint8_t Control1 = 0x00;
constexpr uint8_t RamByte = 0x03;
constexpr uint8_t Seconds = 0x04;
constexpr uint8_t UtcMarker = 0xa7;
constexpr uint8_t StopOr12Hour = 0x22;
constexpr uint8_t OscillatorStopped = 0x80;
constexpr int64_t RetryUs = 15'000'000;
constexpr int64_t CheckUs = 60'000'000;
constexpr auto Earliest = sys_days{year{2025}/January/1};
constexpr auto Latest = sys_days{year{2100}/January/1};

i2c_master_dev_handle_t rtc = nullptr;
std::atomic<bool> restored{false};
std::atomic<bool> current{false};
int64_t next_check = 0;

bool attach()
{
    if (rtc) return true;
    void *bus = nullptr;
    if (esp_board_manager_get_periph_handle("i2c_master", &bus) != ESP_OK || !bus) return false;
    i2c_device_config_t config{};
    config.dev_addr_length = I2C_ADDR_BIT_LEN_7;
    config.device_address = 0x51;
    config.scl_speed_hz = 100000;
    return i2c_master_bus_add_device(static_cast<i2c_master_bus_handle_t>(bus), &config, &rtc) == ESP_OK;
}

template <std::size_t N>
bool read(uint8_t reg, std::array<uint8_t, N> &bytes)
{
    return i2c_master_transmit_receive(rtc, &reg, 1, bytes.data(), bytes.size(), 20) == ESP_OK;
}

bool write(uint8_t reg, uint8_t value)
{
    const std::array bytes{reg, value};
    return i2c_master_transmit(rtc, bytes.data(), bytes.size(), 20) == ESP_OK;
}

int decimal(uint8_t bcd)
{
    const int ones = bcd & 15;
    const int tens = bcd >> 4;
    return ones < 10 && tens < 10 ? tens * 10 + ones : -1;
}

uint8_t bcd(unsigned value)
{
    return static_cast<uint8_t>((value / 10 << 4) | (value % 10));
}

std::optional<sys_seconds> read_utc()
{
    std::array<uint8_t, 11> registers{};
    if (!read(Control1, registers) || registers[RamByte] != UtcMarker ||
            (registers[Control1] & StopOr12Hour) || (registers[Seconds] & OscillatorStopped)) {
        return std::nullopt;
    }
    const int second = decimal(registers[4] & 0x7f);
    const int minute = decimal(registers[5] & 0x7f);
    const int hour = decimal(registers[6] & 0x3f);
    const int yr = decimal(registers[10]);
    const auto date = year{2000 + yr}/month{static_cast<unsigned>(decimal(registers[9] & 0x1f))}/
                      day{static_cast<unsigned>(decimal(registers[7] & 0x3f))};
    if (yr < 0 || !date.ok() || second < 0 || second > 59 || minute < 0 || minute > 59 || hour < 0 || hour > 23) {
        return std::nullopt;
    }
    const auto value = sys_days{date} + hours{hour} + minutes{minute} + seconds{second};
    if (value < Earliest || value >= Latest) return std::nullopt;
    return value;
}

bool write_utc(sys_seconds value)
{
    const auto days = floor<std::chrono::days>(value);
    const year_month_day date{days};
    const hh_mm_ss time{value - days};
    const std::array<uint8_t, 8> bytes{
        Seconds, bcd(time.seconds().count()), bcd(time.minutes().count()), bcd(time.hours().count()),
        bcd(unsigned(date.day())), bcd(weekday{days}.c_encoding()), bcd(unsigned(date.month())),
        bcd(int(date.year()) - 2000)
    };
    std::array<uint8_t, 1> control{};
    if (!read(Control1, control) || !write(RamByte, 0)) return false;
    if ((control[0] & StopOr12Hour) && !write(Control1, control[0] & ~StopOr12Hour)) return false;
    return i2c_master_transmit(rtc, bytes.data(), bytes.size(), 20) == ESP_OK && write(RamByte, UtcMarker);
}

sys_seconds system_utc()
{
    return sys_seconds{seconds{std::time(nullptr)}};
}
}

void initialize()
{
    // SNTP later loads the user's saved timezone. Use the normal board default
    // while the first desktop is starting.
    setenv("TZ", "CST-8", 0);
    tzset();
    if (!attach() || system_utc() >= Earliest) return;
    if (const auto saved = read_utc()) {
        const timeval utc{.tv_sec = static_cast<time_t>(saved->time_since_epoch().count()), .tv_usec = 0};
        if (settimeofday(&utc, nullptr) == 0) {
            restored = true;
            current = true;
            ESP_LOGI(TAG, "Restored UTC from onboard RTC");
        }
    }
}

void poll()
{
    const int64_t ticks = esp_timer_get_time();
    if (ticks < next_check) return;
    next_check = ticks + RetryUs;
    const auto now = system_utc();
    if (now < Earliest || now >= Latest || !attach()) return;
    const auto stored = read_utc();
    if (stored && abs(*stored - now) <= seconds{3}) {
        current = true;
        next_check = ticks + CheckUs;
        return;
    }
    current = false;
    if (write_utc(now)) {
        const auto verified = read_utc();
        if (verified && abs(*verified - now) <= seconds{2}) {
            current = true;
            next_check = ticks + CheckUs;
            ESP_LOGI(TAG, "Stored valid UTC in onboard RTC");
        }
    }
}

bool restored_from_rtc() { return restored.load(); }
bool rtc_current() { return current.load(); }
}
