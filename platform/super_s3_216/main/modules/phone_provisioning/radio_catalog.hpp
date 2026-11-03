#pragma once
// Same public stations as brookesia-apps/radio/src/app/catalog.json. No arbitrary URLs over BLE.
namespace phone_remote {
struct RadioStation {const char *id,*name,*group,*sub;};
inline constexpr RadioStation radio_stations[]={
 {"suzhou-qtfm","苏州儿童广播","儿童","中文 · 亲子广播，按节目表播出"},
 {"junior-0","Fun Kids Junior","儿童","英语 · 低龄儿歌与陪伴"},
 {"story-quest-0","Story Quest","儿童","英语 · Fun Kids 原创故事"},
 {"cnr-classic","经典音乐广播","音乐","中文 · 央广经典音乐"},
 {"naps-0","Fun Kids Naps","音乐","英语 · 摇篮曲与睡眠音乐"},
 {"sleep-sounds-0","Sleep Sounds","音乐","自然声音 · 海浪、雨声与溪流"},
 {"cnr-news","中国之声","资讯","中文 · 新闻资讯"},
 {"cnr-economy","经济之声","资讯","中文 · 财经资讯"},
};
}
