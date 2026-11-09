#pragma once
#include <array>
#include <cstdint>
#include <limits>
#include <type_traits>

namespace resource_math {
// Basis points retain precision for diagnostics; the desktop rounds to percent.
constexpr int heap_usage(uint64_t total, uint64_t free) {
    return total == 0 ? -1 : int((total - (free > total ? total : free)) * 10000 / total);
}
constexpr int rounded_percent(int basis_points) {
    return basis_points < 0 ? -1 : (basis_points + 50) / 100;
}
template<class Counter, unsigned N> class CpuWindow {
    static_assert(N > 0 && std::is_unsigned_v<Counter>);
    bool primed_ = false;
    uint64_t at_ = 0;
    std::array<Counter,N> previous_{};
public:
    struct Sample { bool valid=false; int total=-1; std::array<int,N> cores{}; };
    constexpr Sample sample(uint64_t now, std::array<Counter,N> idle) {
        Sample result{};
        if(primed_ && now > at_ && now-at_ <= std::numeric_limits<Counter>::max()) {
            const auto elapsed=now-at_;uint64_t idle_total=0;
            for(unsigned i=0;i<N;++i) {
                // Unsigned subtraction also handles the configured U32 rollover.
                const uint64_t delta=Counter(idle[i]-previous_[i]);
                const auto bounded=delta>elapsed?elapsed:delta;
                idle_total+=bounded;result.cores[i]=10000-int(bounded*10000/elapsed);
            }
            result.total=10000-int(idle_total*10000/(elapsed*N));result.valid=true;
        }
        previous_=idle;at_=now;primed_=true;return result;
    }
};
}
