# 听书应用

听书 App：`local.audiobook` 0.1.1。底层服务 `Audiobook` 0.1.0 集成在
ESP-Brookesia 本地适配固件 0.8.3-s3.3，独立工作于播放任务；额度、天气继续使用原有 App 包。

按用户要求，暂停下载《凡人修仙传》，等待 microSD 卡。当前没有下载任何书籍音频。
“测试喇叭”生成两秒、低幅度的 440 Hz 正弦波，不使用网络音频或书籍。

## 装卡后使用

使用可读的 FAT32 microSD 卡，在电脑上创建 `audiobooks` 文件夹。例如：

```
audiobooks/
  书名/
    0001.mp3
    0002.mp3
```

关机装卡后启动开发板，打开“听书”，点击“扫描章节”。支持 MP3、WAV，单声道或双声道、
8–48 kHz；输出为 16 位 PCM。文件按路径字典序排列，建议章节编号补零。
扫描至子目录两层，当前最多显示 512 个文件。无卡时显示提示，不格式化存储卡。
SD 卡读写、真实长音频解码和持续播放需装卡后实测。

提供播放／暂停、上一章／下一章、前后 30 秒、音量调节、章节扫描和测试喇叭。
自动播放下一章；显示当前播放时间，只有文件头提供总时长时才显示总时长。
MP3 未提供总帧数时不扫描整部文件计算时长，避免阻塞首次播放。

书签保存在 `/littlefs/audiobook-bookmark.json`：记录最近章节及播放秒数，播放时每 15 秒保存，
暂停、切换和退出时保存；恢复是章节及秒数级，断电可能损失最后 15 秒进度。
切到后台继续当前章节；退出应用停止播放。SD 读取与解码由独立内部栈任务运行。

## 源码和构建

- App：`D:/chatgpt_data/brookesia-apps/audiobook`。
- 音频服务：`D:/chatgpt_data/esp-brookesia-v08/examples/system/super_s3_216/main/modules/audiobook`。
- 解码器：[dr_libs](https://github.com/mackron/dr_libs)，固定提交和文件校验值见服务目录 `upstream.json`；许可见 `LICENSE`。

```powershell
.venv\Scripts\python.exe tools/build_brookesia_app.py ..\brookesia-apps\audiobook
# 先停止电脑采集器，等待串口释放
.venv\Scripts\python.exe tools/install_runtime_app.py ..\brookesia-apps\audiobook\dist\local.audiobook.debug.0.1.1.bpk
```

此 BPK 需要包含 Audiobook 服务的 s3.3 固件；在只有音量控制的 s3.2 上不能实际播放。
升级只写应用分区，保留现有应用、LittleFS、NVS 和 Wi-Fi 配置。
s3.2 升级前镜像位于 `artifacts/brookesia-s3.2-before-audiobook`。

## 内容来源

已找到[喜马拉雅制作的《凡人修仙传》多播版](https://www.himalaya.com/courses/3710632)，
页面注明前 30 集免费试听，其余需要购买。尚未下载，也未验证平台文件能否直接用于开发板。

## 实机验证（2026-10-18）

固件已仅写入应用分区并通过 esptool 哈希校验，额度 0.2.2 和天气 0.2.2 保留。
听书重复打开两次通过；无卡目录为空，缺失文件正确拒绝。测试音完整输出 64,000 字节 PCM，
状态 Ended，无错误；用户确认“界面正常，喇叭有声音”。音量测试后恢复原值。
0.1.1 将音量减号从字体缺失的 U+2212 改为 ASCII 连字符，更新后启动正常。
证据：runtime/audiobook-verification.json、audiobook-layout-0.1.1.json、audiobook-flash.log。
SD 文件读取、MP3/WAV 持续播放和实机断点续播等待装卡后验证。
