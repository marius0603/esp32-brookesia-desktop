# 儿歌 0.1.3

设备端独立中文儿歌播放器，要求固件 **s3.48+**。App、20首儿歌、10首摇篮曲、播放偏好和断点都在SD卡；没有SD卡时基础桌面、设置和家长验证仍可用，儿歌不登记到桌面。

打开先显示“快乐儿歌 / 摇篮曲”两个独立专区，分别为20首和10首；选择专区不自动播放。各区独立分页、上下首和断点，设备App的顺序/随机/单曲循环均只在当前区选曲。原单书签自动迁移，返回顶部“专区”可切换；切到另一区时停止原歌曲。

奶油色大按钮和小马音符图标；顶部音量，播放/暂停、上一首/下一首，四行分页选歌，顺序/随机/单曲循环，以及15/30/45分钟睡眠定时。打开不自动播放，正常1倍速；最后两分钟沿用听书服务的淡出/变暗/晚安。左右实体键调整系统音量。回到桌面或切换App会按系统生命周期结束播放并保存儿歌断点。

儿童模式复用“听书/儿歌”授权位、每日时长、休息时间和音量上限，原PIN和设置不变。儿歌与故事分别扫描 `/sdcard/audiobooks/songs` 与其余听书目录；`Audiobook.List`和手机原有书架仍只列故事，`ListSongs`只列儿歌。安卓0.4.0提供独立儿歌页，通过原接口读取全部歌曲并控制上下首、暂停/继续/停止、音量、播放模式和定时。离线“讲故事”选故事，已有“下一篇”仍在歌曲总目录内选下一项，尚未增加按专区的离线命令。安卓0.4.0保持原儿歌页，曲库会包含新增的10首，但本次未新增手机分类界面。

复用已经验证的原生MP3/WAV解码、64KiB PSRAM PCM缓冲和音频互斥，不增加第二套音频缓存或常驻解码任务。当前App只有打开时运行JS；没有上传麦克风或音频内容。歌曲的顺序/随机/单曲循环偏好独立于听书模式，由原生服务与手机/设备页面共享；首次读取原JS偏好，之后保存至SD的独立play-mode.json，不改写书签。原生音频硬件、睡眠计时器和音量仍是同一套共享服务。

## 曲库和音量

首批20首：小星星、两只老虎、小兔子乖乖、小白兔白又白、小青蛙、小毛驴、数鸭子、找朋友、小燕子、上学歌、小螺号、采蘑菇的小姑娘、蜗牛与黄鹂鸟、泥娃娃、虫儿飞、小红帽、新年好、生日快乐、小老鼠上灯台、小汽车。

来源为[悟空教育公开儿歌页面](https://www.wukongsch.com/blog/zh/best-kids-chinese-classic-songs-collection-post-36383/?amp=1)中直接提供的音频链接。录音仅下载至用户设备/私有工作目录，Git不分发录音；页面可访问不等于获得录音再分发许可。链接、原始/成品SHA256、时长、格式和响度记录在 `samples/songs/library-20261104.json`。

与原故事库统一目标 **−14 LUFS**，输出44.1kHz、96kbps、单声道MP3。实测成品 **−14.27～−13.70 LUFS**，最高真峰值 **−1.60 dBTP**；共约36.3分钟、24.91MiB。转换保留完整音频和时长，检查严重双声道抵消，并测量实际MP3成品。相同音量设置下切歌响度更接近；这不是喇叭声压计校准，音量上限继续由家长模式控制。

## 摇篮曲专区（2026-11-09）

十首舒缓纯音乐：勃拉姆斯摇篮曲、困困小笛、摇摇小木马、魔法铃声、小熊睡着了、甜甜摇篮曲、星星晚安、夜晚好朋友、第一个美梦、童年的梦。显示名为中文译名，录音由Alexander Blu创作/制作，来自[Orange Free Sounds摇篮曲目录](https://orangefreesounds.com/tag/lullaby/page/4/)及[勃拉姆斯摇篮曲页面](https://orangefreesounds.com/brahms-lullaby/)。

文件独立放在`/sdcard/audiobooks/songs/lullabies`，原20首不移动、不重新编码；故事列表仍排除整个儿歌曲库。十首约29.5分钟、20.26MiB，目标同为−14 LUFS，实际−14.21～−13.75 LUFS，最高真峰值−2.93 dBTP。全部完整解码并核对转换前后时长及SHA256；不同喇叭和距离的声压仍由实际音量决定。

来源、每首CC BY 4.0或CC BY-NC 4.0许可、中文译名、原始/成品哈希和测量在`samples/songs/lullabies-20261109.json`。非商业个人设备使用，下载录音不进入Git；设备“音乐来源”和SD同目录`CREDITS.txt`保留作者、来源、许可链接和单声道/响度处理说明。

```powershell
python codex-quota-monitor/tools/prepare_song_library.py --manifest samples/songs/lullabies-20261109.json --ffmpeg <pinned-ffmpeg.exe> --output <private-lullaby-dir>
python codex-quota-monitor/tools/package_nursery_songs.py
python codex-quota-monitor/tools/deploy_lullabies.py --port COM5 --audio-dir <private-lullaby-dir>
# 重启设备以重新登记0.1.3，然后：
python codex-quota-monitor/tools/verify_lullabies.py --port COM5
```

本次只更新SD应用与新增录音，沿用s3.61，无需烧录固件。部署逐文件传输核对SHA，应用整树复制到SD暂存并校验app/res和原data/cache/files后切换目录，旧树完整保留于`/sdcard/resource-backups`，避免整包安装分配峰值。

## 重建与部署

在仓库根目录运行，Python需fontTools，Node需已有构建环境：

```powershell
python brookesia-apps/nursery-songs/tools/generate_resources.py
# 使用 sharp 将 src/res/images/launcher_icon.svg 栅格化到同目录的96x96 PNG。
python codex-quota-monitor/tools/package_nursery_songs.py
python codex-quota-monitor/tools/prepare_song_library.py --manifest samples/songs/library-20261104.json --ffmpeg <ffmpeg.exe> --output <private-audio-dir>
# 先按仓库通用流程构建/烧录s3.48应用分区；不要覆盖NVS、LittleFS或SD。
python codex-quota-monitor/tools/deploy_nursery_songs.py --port COM5 --audio-dir <private-audio-dir>
# 重启加载补充的“鹂”字形后：
python codex-quota-monitor/tools/verify_nursery_songs.py --port COM5
```

`prepare_song_library.py`默认严格核对已提交的原始/成品哈希。仅首次审阅新曲单时使用`--record`更新测量，不应将未知变化当作通过。编码器版本和SHA已固定。上传逐文件核对设备SHA及SD尺寸；部署报告只放忽略的runtime目录，已核验文件可断点重跑，未知重名文件拒绝覆盖。

可用`python brookesia-apps/nursery-songs/tools/generate_title_font.py --font <NotoSansSC-VF.ttf>`按固定来源哈希重建标题字体。共享标题补充字体增加“鹂”，保留原“筝蝌”，成品4664字节；来源及OFL记录在`samples/songs/font-source-20261104.json`和`licenses/notosanssc-OFL.txt`。基础中文字体作回退。图标源SVG和屏幕JSON均随源码提交。

## 首曲与系统主题（2026-11-10）

显式选择专区后的第一次播放从所选曲目开头开始，避免继承旧播放状态或末尾断点；直接重开App仍保留原断点。只有原生正在播放时才跟随其曲目，停止的旧路径不覆盖新选择。

儿歌0.1.3、听书0.3.7和电台0.1.3统一随系统深浅模式切换：Q版使用奶油浅底/棕字，赛博使用深蓝底/浅字；正文、按钮、边框和选中状态一起切换。启动、返回App与前台轮询均同步，未增加常驻任务或音频缓冲。界面生成后运行`python tools/apply_audio_themes.py`补充绑定，再打包。

系统深浅模式读取`SystemCore.GetEnvironment.theme_id`；`DeviceModes.desktop_theme_index`只代表壁纸样式，不能用于判断深浅。
