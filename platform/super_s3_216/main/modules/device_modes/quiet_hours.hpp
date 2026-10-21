#pragma once
namespace quiet_hours {
// Half-open local-time interval; equal start/end explicitly means all day.
constexpr bool contains(int minute,int start,int end){
    if(minute<0 || minute>=1440 || start<0 || start>=1440 || end<0 || end>=1440)return false;
    return start==end || (start<end ? minute>=start && minute<end : minute>=start || minute<end);
}
static_assert(contains(1320,1320,420));
static_assert(contains(0,1320,420));
static_assert(contains(419,1320,420));
static_assert(!contains(420,1320,420));
static_assert(!contains(1319,1320,420));
static_assert(contains(600,540,660) && !contains(660,540,660));
static_assert(contains(700,0,0) && !contains(-1,0,0));
}
