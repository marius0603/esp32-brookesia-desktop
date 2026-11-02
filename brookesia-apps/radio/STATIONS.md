# 网络电台频道核验

核验日期：2026-11-02。保留最初的儿童故事/儿歌、舒缓音乐/自然声音、资讯方向；按通用网络电台设计，不按上海、青岛等地区划分。中文频道优先排列，补充三路英语内容和一路自然环境声。列表中的名称对应真实频道，不再使用“童话电台”“童谣小屋”等虚构台名。

| 分类 | 原型显示名 | 实际频道与内容依据 | 语言与节目边界 | 短测音频格式 |
| --- | --- | --- | --- | --- |
| 儿童 | 苏州儿童广播 | [蜻蜓FM频道2807](https://m.qtfm.cn/channels/2807/)，亲子957 | 中文；亲子综合台，包含新闻、歌曲等，按节目表播出，并非全天故事 | MP3，48kHz，双声道，64kbps |
| 儿童 | Fun Kids Junior | [官方介绍](https://www.funkidslive.com/news/whats-fun-kids-junior-and-how-do-i-listen/)，面向低龄听众 | 英语；儿歌和陪伴，夜间故事/摇篮曲按英国时间安排 | HE-AAC，44.1kHz，双声道，64kbps |
| 儿童 | Story Quest | [Fun Kids Story Quest Radio官方介绍](https://www.funkidslive.com/stations/what-is-fun-kids-story-quest-radio-and-how-do-i-listen/)，连续原创故事 | 英语；不是中文故事，也不保证全部适合1至3岁 | HE-AAC，44.1kHz，双声道，约47kbps |
| 音乐 | 经典音乐广播 | [央广官方介绍](https://ent.cnr.cn/ylzt/goldenradio/)、[2026年官方报道](https://news.cnr.cn/native/gd/20260914/t20260914_527813513.shtml) | 中文导播与音乐；不是全天钢琴或纯轻音乐 | HLS/AAC-LC，48kHz，双声道，192kbps |
| 音乐 | Fun Kids Naps | [官方介绍](https://www.funkidslive.com/stations/fun-kids-naps/what-is-fun-kids-naps/)，摇篮曲与睡眠音乐 | 英语歌曲；对应原先睡眠音乐方向 | MP3，44.1kHz，双声道，128kbps |
| 音乐 | Sleep Sounds | [Fun Kids Sleep Sounds官方介绍](https://www.funkidslive.com/stations/what-is-fun-kids-sleep-sounds-and-how-do-i-listen/)，海浪、风、雨/炉火、鸟鸣、溪流、森林声音 | 自然环境声；对应原先自然之声方向，不是中文朗读 | HE-AAC，44.1kHz，双声道，约47kbps |
| 资讯 | 中国之声 | [央广官方报道](https://news.cnr.cn/dj/20260216/t20260216_527529018.shtml) | 中文新闻资讯，普通听众频道 | HLS/AAC-LC，48kHz，双声道，192kbps |
| 资讯 | 经济之声 | [央广官方报道](https://news.cnr.cn/dj/20260216/t20260216_527529018.shtml) | 中文财经资讯，普通听众频道 | HLS/AAC-LC，48kHz，双声道，192kbps |

## 音源与验证范围

稳定入口及逐台结果保存于 [stations.json](stations.json)。Fun Kids入口直接取自各台官方播放器公开配置；苏州台身份和直播ID来自蜻蜓FM频道页，公开MP3入口经实际读取验证；央广入口由公开目录线索定位，再按官方台名与音频响应核对。只保存稳定入口，不保存CDN跳转中短期生成的参数，也不提交音频采样。

- 八个入选音源均HTTP 200。连续流各读取128KiB；HLS读取播放列表及一个约250KiB片段，FFmpeg解码前2秒成功。此检查验证有可解码音频，不能替代长时监听、逐节目内容检查或独立听辨台号。
- 测试走电脑配置的代理网络，因此不能据此承诺开发板直接联网、所有运营商或境外源的国内稳定性。当前界面仍是静音交互原型，音源未接入设备。
- HE-AAC与HLS在设备上的解码支持、重定向、缓冲、断线恢复和内存占用须在播放器开发阶段验证；不能把电脑解码成功当作ESP32已兼容。
- 儿童广播可能穿插其他节目或宣传；儿童分类是内容分组，不是已逐项审核的低龄内容白名单。中文全天故事/纯儿歌直播尚未核实到可直接采用的来源，不用点播专辑冒充直播台。

## 未采用的候选与旧入口

- 蜻蜓旧链接中的`20211692`不是此次可用的苏州台频道入口；采用当前频道页确认的`2807`。
- 央广部分旧目录主机返回403；未绕过限制，改用正常公开响应且可解码的入口。音乐之声、文艺之声虽也通过短测，本次优先保留更贴近原设计的舒缓/自然声音，没有另建文艺分类。
- ABC Kids listen的[官方访问说明](https://help.abc.net.au/hc/en-us/articles/360001184395-How-can-I-access-ABC-Kids-listen)标明仅限澳大利亚，未列入设备候选。

后续默认进入中文儿童台；若希望“打开就一定是中文睡前故事”，应使用现有听书书库，或另做经授权的中文点播入口，而不是给综合广播改成“睡前故事”的台名。
