#pragma once
#include <atomic>

// Raw codec users must claim the shared I2S/PA path before starting a worker.
namespace local_audio {
enum Owner { Free = 0, Audiobook = 1, Assistant = 2 };
inline std::atomic<int> owner{Free};
inline std::atomic<bool> sleeping{false};
inline bool claim(Owner value) {
    if(sleeping.load())return false;
    int expected = Free;
    if(!owner.compare_exchange_strong(expected, value))return false;
    if(sleeping.load()){expected=value;owner.compare_exchange_strong(expected,Free);return false;}
    return true;
}
inline void release(Owner value) {
    int expected = value;
    owner.compare_exchange_strong(expected, Free);
}
}
