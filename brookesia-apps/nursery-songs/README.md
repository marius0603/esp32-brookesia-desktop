# 儿歌 0.1.0

设备端独立中文儿歌播放器，要求固件 **s3.47+**。App、20首音频、播放偏好和断点都在SD卡；没有SD卡时基础桌面、设置和家长验证仍可用，儿歌不登记到桌面。

奶油色大按钮和小马音符图标；顶部音量，播放/暂停、上一首/下一首，四行分页选歌，顺序/随机/单曲循环，以及15/30/45分钟睡眠定时。打开不自动播放，正常1倍速；最后两分钟沿用听书服务的淡出/变暗/晚安。左右实体键调整系统音量。回到桌面或切换App会按系统生命周期结束播放并保存儿歌断点。

儿童模式复用“听书/儿歌”授权位、每日时长、休息时间和音量上限，原PIN和设置不变。儿歌与故事分别扫描 `/sdcard/audiobooks/songs` 与其余听书目录；`Audiobook.List`和手机原有书架仍只列故事，`ListSongs`只列儿歌。当前手机App尚无独立儿歌页。离线“讲故事”选故事，已有“下一篇”在当前曲库内选下一项。

复用已经验证的原生MP3/WAV解码、64KiB PSRAM PCM缓冲和音频互斥，不增加第二套音频缓存或常驻解码任务。当前App只有打开时运行JS；没有上传麦克风或音频内容。歌曲的顺序/随机/单曲循环偏好独立于听书模式。原生音频硬件、睡眠计时器和音量仍是同一套共享服务。

## 曲库和音量

首批20首：小星星、两只老虎、小兔子乖乖、小白兔白又白、小青蛙、小毛驴、数鸭子、找朋友、小燕子、上学歌、小螺号、采蘑菇的小姑娘、蜗牛与黄鹂鸟、泥娃娃、虫儿飞、小红帽、新年好、生日快乐、小老鼠上灯台、小汽车。

来源为[悟空教育公开儿歌页面](https://www.wukongsch.com/blog/zh/best-kids-chinese-classic-songs-collection-post-36383/?amp=1)中直接提供的音频链接。录音仅下载至用户设备/私有工作目录，Git不分发录音；页面可访问不等于获得录音再分发许可。链接、原始/成品SHA256、时长、格式和响度记录在 `samples/songs/library-20261104.json`。

与原故事库统一目标 **−14 LUFS**，输出44.1kHz、96kbps、单声道MP3。实测成品 **−14.27～−13.70 LUFS**，最高真峰值 **−1.60 dBTP**；共约36.3分钟、24.91MiB。转换保留完整音频和时长，检查严重双声道抵消，并测量实际MP3成品。相同音量设置下切歌响度更接近；这不是喇叭声压计校准，音量上限继续由家长模式控制。

## 重建与部署

在仓库根目录运行，Python需fontTools，Node需已有构建环境：

```powershell
python brookesia-apps/nursery-songs/tools/generate_resources.py
# 使用 sharp 将 src/res/images/launcher_icon.svg 栅格化到同目录的96x96 PNG。
python codex-quota-monitor/tools/package_nursery_songs.py
python codex-quota-monitor/tools/prepare_song_library.py --manifest samples/songs/library-20261104.json --ffmpeg <ffmpeg.exe> --output <private-audio-dir>
# 先按仓库通用流程构建/烧录s3.47应用分区；不要覆盖NVS、LittleFS或SD。
python codex-quota-monitor/tools/deploy_nursery_songs.py --port COM5 --audio-dir <private-audio-dir>
# 重启加载补充的“鹂”字形后：
python codex-quota-monitor/tools/verify_nursery_songs.py --port COM5
```

`prepare_song_library.py`默认严格核对已提交的原始/成品哈希。仅首次审阅新曲单时使用`--record`更新测量，不应将未知变化当作通过。编码器版本和SHA已固定。上传逐文件核对设备SHA及SD尺寸；部署报告只放忽略的runtime目录，已核验文件可断点重跑，未知重名文件拒绝覆盖。

可用`python brookesia-apps/nursery-songs/tools/generate_title_font.py --font <NotoSansSC-VF.ttf>`按固定来源哈希重建标题字体。共享标题补充字体增加“鹂”，保留原“筝蝌”，成品4664字节；来源及OFL记录在`samples/songs/font-source-20261104.json`和`licenses/notosanssc-OFL.txt`。基础中文字体作回退。图标源SVG和屏幕JSON均随源码提交。
