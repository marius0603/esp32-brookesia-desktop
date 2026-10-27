# ESP32-S3 翻页桌面与应用

微雪 **ESP32-S3-Touch-AMOLED-2.16** 的接续开发仓库。包含当前设备使用的 Brookesia 本地适配、全部自研应用和电脑端工具，可在另一台 Windows 电脑继续开发。

| 内容 | 版本与当前行为 |
| --- | --- |
| 桌面固件 | ESP-IDF 6.0.2，ESP-Brookesia 本地适配 0.8.3-s3.24；新增电脑语音助手公网 WSS 通道；保留听书触摸锁屏、双击音量＋解锁、离线 WakeNet + MultiNet 命令、Q 版主题、持久化音量、自动息屏、定时勿扰、儿童模式及重力旋转 |
| Codex 额度 | 0.2.2，真实剩余额度、吃豆人动画、大号重置倒计时 |
| 天气 | 0.2.6，默认上海、开发板直接联网、各天气动态背景、云形图片、24 小时预报 |
| 听书 | 0.3.0，恢复并随包保留 Q 版图标、中文故事标题；移除前后 30 秒按钮，睡眠定时改为选择框；增加锁屏键，连按两次音量＋解锁；SD MP3/WAV、章节与书签，最后 2 分钟声音/亮度渐弱，到时离线“晚安”并停播 |
| 翻页时钟 | 0.1.1，只显示大号北京时间 HH:MM，分钟变化时翻页 |
| 智能助手 | 0.2.0，电脑 Qwen3-ASR → DS 云端 → Qwen3-TTS → 设备播放，可切换小智；公网加密音频、手动录音发送、字幕、打断及本地回放，保留实体音量与勿扰规则 |
| 离线语音 | 0.1.0 试验版，先说“你好小智”，本机处理八类命令；存在漏识别，童声准确率尚未验证；SD 模型与中文剩余时间提示，不上传命令录音 |
| 儿童模式 | 0.1.0，家长 PIN、应用白名单、音量上限、每日时长和可选夜间休息；默认不开放语音助手 |

本仓库不含 Codex 登录凭据、Wi-Fi 密码、设备完整 Flash 备份、运行额度数据或下载的书籍。
自动息屏和定时勿扰见 [DEVICE_MODES.md](codex-quota-monitor/DEVICE_MODES.md)。
壁纸微移的行为与已有设备更新步骤见 [WALLPAPER_SHIFT.md](codex-quota-monitor/WALLPAPER_SHIFT.md)。
重力感应开关、校准与已有设备安装步骤见 [AUTO_ROTATION.md](codex-quota-monitor/AUTO_ROTATION.md)。
儿童模式设置与验证见 [CHILD_MODE.md](codex-quota-monitor/CHILD_MODE.md)，主题资源迁移见 [SD_RESOURCES.md](codex-quota-monitor/SD_RESOURCES.md)。
听书定时、中文样例及离线语音合成见 [AUDIOBOOK.md](codex-quota-monitor/AUDIOBOOK.md)。当前 Q 版图标和壁纸见 [主题说明](themes/cartoon-q-v1/README.md)。
助手实体音量键及界面同步修复见 [ASSISTANT_VOLUME.md](codex-quota-monitor/ASSISTANT_VOLUME.md)。
电脑模型、跨网络连接、设备安装与验证见 [电脑语音助手](pc-voice-bridge/README.md)。当前公网入口为临时隧道，重建后需更新设备地址；长期使用需固定入口。
离线命令词、模型部署与童声验证范围见 [OFFLINE_VOICE.md](codex-quota-monitor/OFFLINE_VOICE.md)。
当前系统属于官方开发分支的本地 S3 适配，未恢复微雪出厂 AIChats 等完整应用。

## 在另一台 Windows 电脑开始

准备 Git、Python 3.12（64 位）、Node.js LTS；固件编译建议使用较短路径，例如 `C:\dev\esp32-desktop`。
克隆仓库时使用你自己的 GitHub 登录。进入仓库后运行：

```powershell
git clone https://github.com/marius0603/esp32-brookesia-desktop.git
cd esp32-brookesia-desktop
python tools/prepare_workspace.py
cd codex-quota-monitor
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
npm --prefix tools/brookesia-toolkit install
```

准备脚本会下载 `versions.json` 固定的 Brookesia 提交，应用 `patches/brookesia-s3.patch`，再装入 `platform/super_s3_216` 工程。
整个上游代码无需重复保存在此仓库；首次准备需要网络。脚本拒绝覆盖已有不同内容的源码。
目录关系必须保留：`codex-quota-monitor`、`brookesia-apps` 与生成的 `esp-brookesia-v08` 同级。

## 修改应用，独立安装

在 `brookesia-apps/<应用>/src` 修改 JavaScript、界面 JSON 或图片。资源已提供，无需重新生成字库。
在 `codex-quota-monitor` 目录执行，例如更新时钟：

```powershell
.venv\Scripts\python.exe tools/build_brookesia_app.py ..\brookesia-apps\flip-clock
.\stop.ps1
# 等待采集器退出，释放串口；COM5 替换成新电脑检测到的端口
.venv\Scripts\python.exe tools/install_runtime_app.py ..\brookesia-apps\flip-clock\dist\local.flipclock.debug.0.1.1.bpk --port COM5
.\start.ps1
```

其他应用目录是 `codex-quota`、`weather`、`audiobook`、`voice-assistant`、`child-mode`；打包文件名以各自 `src/manifest.json` 的版本为准。
安装 App 无需重刷系统。听书需要 s3.3 固件提供的 Audiobook 服务；时钟依赖已有 PNG 解码与 SNTP。
智能助手 0.2.0 需要 s3.24 原生服务。默认电脑模式，点击模式按钮可切换小智；小智首次使用仍需在平台添加设备。点击说话后才采集语音，再次点击发送，最长30秒。
电脑端 Node.js 从 PATH 查找，也可通过 `QUOTA_NODE` 指定。

## 恢复电脑端额度同步

在新电脑安装并登录 Codex，编辑 `codex-quota-monitor/config.json`：将 `serial_port` 设置为开发板实际端口，
`device_protocol` 保持 `brookesia`。配置文件初始为 `auto`；手动指定可避免连接其他串口设备。

```powershell
# 位于 codex-quota-monitor
.venv\Scripts\python.exe -m quota_monitor --once
.\start.ps1
```

不要在两台电脑同时占用同一串口。天气与时钟直接使用设备网络和系统时间，不依赖电脑提供数据。

## 编译桌面固件

应用修改只需上面的工具。改音频服务、驱动或桌面 C++ 时才需要完整工具链：

```powershell
# 位于 codex-quota-monitor；会下载较大的官方 SDK 和交叉编译工具
.venv\Scripts\python.exe tools/bootstrap_idf6.py
.venv\Scripts\python.exe tools/brookesia_idf6.py gen-bmgr-config -b esp32_s3_touch_amoled_2_16
.venv\Scripts\python.exe tools/brookesia_idf6.py -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;components/gen_bmgr_codes/board_manager.defaults;sdkconfig.s3_216' -D BROOKESIA_CXX_JOBS=4 -D BROOKESIA_FAST_COMPILE=ON build
```

准备时恢复了 `sdkconfig.reproducible` 中的完整构建配置。`platform` 是本仓库维护的源码；
生成的 `esp-brookesia-v08` 目录被 Git 忽略。在生成目录修改 C++ 后，要将改动同步回 `platform` 或更新上游补丁再提交。
主工程包括 GUI、缓存和触摸优化；第三方依赖与硬件驱动的本地改动保存在补丁中。

## 固件文件与备份

`packages/apps` 保存可安装 BPK，当前听书为 [0.3.0](packages/apps/local.audiobook.debug.0.3.0.bpk)，智能助手为 [0.2.0](packages/apps/local.voiceassistant.debug.0.2.0.bpk)；`packages/firmware` 包含 [s3.24 应用分区更新包](packages/firmware/brookesia-0.8.3-s3.24-app-only.zip) 及历史版本。更新包附带只用于核对的分区表，使用 [听书更新步骤](codex-quota-monitor/AUDIOBOOK.md) 安装；校验值见 `packages/SHA256.json`。
它们不包含用户 NVS、Wi-Fi 数据或设备系统资源分区，不能当成任意新设备的完整恢复镜像。

原电脑的恢复工具会检查完整备份和设备身份，新电脑没有备份时会拒绝直接烧录。这是已有防误刷机制。
已验证的私有整机备份仍在原电脑 `codex-quota-monitor/runtime/backups`，需要自行离线保管；不要提交 GitHub。
新电脑可直接开发及安装应用，不需要这些备份。

## 测试与开发记录

```powershell
# 位于 codex-quota-monitor
.venv\Scripts\python.exe -m unittest discover -s tests
node ..\brookesia-apps\codex-quota\tests\main.test.cjs
node ..\brookesia-apps\weather\tests\main.test.cjs
node ..\brookesia-apps\audiobook\tests\main.test.cjs
node ..\brookesia-apps\flip-clock\tests\main.test.cjs
node ..\brookesia-apps\voice-assistant\tests\main.test.cjs
node ..\tests\child_ui_flow.cjs
```

本次更新的功能、修复和验证结果见 [CHANGELOG.md](CHANGELOG.md)。

详细记录：
[桌面与驱动](codex-quota-monitor/BROOKESIA.md)、
[设备验证](codex-quota-monitor/BROOKESIA_VERIFICATION.md)、
[额度动画](codex-quota-monitor/PACMAN_QUOTA.md)、
[天气](codex-quota-monitor/WEATHER.md)、
[听书](codex-quota-monitor/AUDIOBOOK.md)、
[翻页时钟](codex-quota-monitor/FLIP_CLOCK.md)、
[智能助手](codex-quota-monitor/VOICE_ASSISTANT.md)。
历史记录中的绝对路径、串口、MAC 和日志指向原电脑，迁移时按实际位置使用；运行日志不随仓库上传。

## 桌面图标与背景

[奶油手绘主题](themes/cream-handdrawn-v1/README.md) 包含 8 个应用图标、480×480 壁纸和可回滚的 USB 部署工具。无需重新烧录固件；重新安装应用后可单独重应用主题。

上游及第三方许可见 `UPSTREAM_LICENSE`、`licenses` 和各组件原始许可文件。
