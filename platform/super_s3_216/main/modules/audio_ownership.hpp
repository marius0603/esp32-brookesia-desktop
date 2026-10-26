#pragma once
#include <atomic>

// Raw codec users must claim the shared I2S/PA path before starting a worker.
namespace local_audio {
enum Owner { Free = 0, Audiobook = 1, Assistant = 2 };
inline std::atomic<int> owner{Free};
inline std::atomic<bool> sleeping{false};
inline std::atomic<bool> offline_duck{false};
inline std::atomic<bool> audiobook_busy{false}, assistant_busy{false};
inline std::atomic<bool> story_timer_busy{false};
inline bool busy(){return audiobook_busy.load() || assistant_busy.load() || story_timer_busy.load();}
inline bool claim(Owner value) {
    if(sleeping.load())return false;
    int expected = Free;
    if(!owner.compare_exchange_strong(expected, value))return false;
    if(sleeping.load()){expected=value;owner.compare_exchange_strong(expected,Free);return false;}
    return true;
}
inline void release(Owner value) {
    int expected = value;
    if(owner.compare_exchange_strong(expected, Free)) {
        if(value==Audiobook)audiobook_busy=false;
        if(value==Assistant)assistant_busy=false;
    }
}
}
