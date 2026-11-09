#pragma once
#include <array>
#include <cstdint>

namespace resource_monitor {
struct Snapshot {
    uint64_t sampled_us=0;
    uint32_t samples=0;
    int cpu_basis_points=-1, ram_basis_points=-1;
    unsigned cores=0;
    std::array<int,2> core_basis_points{{-1,-1}};
    uint32_t ram_total=0,ram_free=0,internal_total=0,internal_free=0,psram_total=0,psram_free=0;
};
// Called on the existing internal-stack orientation worker, not the GUI thread.
void poll();
Snapshot snapshot();
}
