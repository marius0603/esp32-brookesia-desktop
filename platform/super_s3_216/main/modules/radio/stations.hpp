#pragma once
namespace radio_catalog {
struct Station {const char *id,*url,*format;};
inline constexpr Station stations[]={
 {"suzhou-qtfm","https://lhttp.qtfm.cn/live/20211692/64k.mp3","mp3"},
 {"suzhou-qtfm-legacy","https://lhttp.qtfm.cn/live/2807/64k.mp3","mp3"},
 {"junior-0","https://listen-funkids.sharp-stream.com/funkidsjunior.aac?platform=website","aac"},
 {"story-quest-0","https://stream.rcs.revma.com/d3xb3hq3tm0uv","aac"},
 {"cnr-classic","https://ngcdn001.cnr.cn/live/dszs/index.m3u8","hls_ts"},
 {"naps-0","https://stream.rcs.revma.com/3rpf8hr3tm0uv","aac"},
 {"sleep-sounds-0","https://stream.rcs.revma.com/5skkr2gtuy8uv","aac"},
 {"cnr-news","https://ngcdn001.cnr.cn/live/zgzs/index.m3u8","hls_ts"},
 {"cnr-economy","https://ngcdn002.cnr.cn/live/jjzs/index.m3u8","hls_ts"},
};
}
