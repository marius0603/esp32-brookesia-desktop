# ESP-Brookesia 0.8 / Waveshare 2.16 适配记录

此目录同时保留原独立额度固件与新版 Brookesia 的电脑端工具。部署状态以
`runtime/brookesia-flash-result.json` 和实机验证记录为准；源码准备、编译通过均不代表烧录成功。

## 固定版本

- ESP-Brookesia 源码：`../esp-brookesia-v08`，提交 `68ac00e7aa9012cd8cbf0cbf6bee155801db0e8c`。
- 桌面工程：`examples/system/super_s3_216`，版本 `0.8.3-s3.3`。
- ESP-IDF 6.0.2；System Super 0.8.3、System Core 0.8.4、JavaScript Runtime 0.8.3。
- 独立 App：`../brookesia-apps/codex-quota`，`local.codex.quota` 0.2.2；`../brookesia-apps/weather`，`local.weather` 0.2.2。
- Toolkit 1.0.1；电脑端 USB 工具 0.1.1，来自同一固定提交。

官方支持此板的 HAL；完整 System Super 示例未将此 ESP32-S3 板列入其验证板卡，本工程是本地适配。
保留设置、文件、应用商店和 JavaScript 运行时；未加入摄像头、NES、Coze、XiaoZhi 和音频处理器。
保留板载 codec 播放、录音 HAL 接口，未集成声学识别模型或语音代理。
AudioPlayback 启动兼容 codec 控制模式，保留音量和静音；此模式不提供媒体 URL 解码播放。

## 构建

在本项目根目录执行：

```powershell
.venv\Scripts\python.exe tools/brookesia_idf6.py gen-bmgr-config -b esp32_s3_touch_amoled_2_16
.venv\Scripts\python.exe tools/brookesia_idf6.py -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;components/gen_bmgr_codes/board_manager.defaults;sdkconfig.s3_216' -D BROOKESIA_CXX_JOBS=4 -D BROOKESIA_FAST_COMPILE=ON build
.venv\Scripts\python.exe tools/build_quota_bpk.py
```

SDK 6 工具使用 `D:\chatgpt_data\i6` 目录联接，避免 Windows 工具链解压路径过长。
仓库 `.patch` 文件须使用 LF 换行，否则 Git 的 `apply` 会将 CRLF 空白上下文行报为损坏补丁。
初次生成配置后应核对：codec recorder=y、audio processor=n；关闭 recorder 会使 processor 配置项从
SDK 配置 JSON 中消失，而上游依赖清单仍会引用该项。

本地配置关闭 SD 卡挂载失败时自动格式化，开启 TLS 证书验证、USB Serial/JTAG 服务及中文字体资源。
使用 `CONFIG_COMPILER_OPTIMIZATION_SIZE=y` 缩小代码，关闭 PSRAM XiP、指令及只读数据复制，
让 8 MB PSRAM 用于 GUI、字体和 App。Storage 使用框架的 Secondary Scheduler（内部 RAM 栈），
字体使用 FreeType MEMFS 端口，避免由外部栈直接执行 Flash 操作。图像缓存设为 1 MB。
USB 上传临时文件会直接写入 LittleFS，因此在关闭 XiP 时，现有 Main Scheduler 的
三个 15 KiB 栈均使用内部 RAM（`BROOKESIA_SERVICE_MANAGER_WORKER_STACK_IN_EXT=n`）。
Storage 的 Secondary Scheduler 保持开启；USB 不新增专用调度器。原 PSRAM 栈会在
开始安装 BPK 时触发 Flash 栈检查断言，曾试验的 USB 私有调度器存在启动阻塞，未采用。
首次使用性能优化的构建占用过多 PSRAM，且原音频启动流程会在缺少处理器时退出；
体积优化后仍开启 XiP 时，桌面加载发生 OOM，日志为 `runtime/brookesia-size-xip-boot.log`。
相关首次实机日志保存在 `runtime/brookesia-reset-boot.log`，本地适配补丁为
`tools/brookesia-s3-adaptation.patch`。还原固定提交时需应用此补丁。
初次烧录使用新的 NVS，避免原程序数据与新版服务配置混用。原完整 Flash 备份保留原数据。

## 额度 App 与传输

电脑端每 60 秒读取已登录 Codex 的额度缓存；每 15 秒通过 Brookesia USB Storage 服务
更新 `/littlefs/quota.json`。App 每 2 秒读取文件，显示两种额度与重置倒计时。
45 秒没有传输心跳或样本超过 180 秒时标记过期，不额外发起模型请求。

启用电脑端传输需要 `config.json` 设置 `device_protocol` 为 `brookesia`、`serial_port` 为实际端口。
操作 USB 工具前运行 `stop.ps1` 并等待采集器退出，完成后用 `start.ps1` 恢复；避免两个进程占用串口。

```powershell
.venv\Scripts\python.exe tools/brookesia_device.py --port COM5
.venv\Scripts\python.exe tools/brookesia_device.py --port COM5 --service SystemCore --function ListApps
.venv\Scripts\python.exe tools/install_runtime_app.py ..\brookesia-apps\codex-quota\dist\local.codex.quota.debug.0.2.2.bpk
```

App 包可以单独安装，不需要随每次 App 更新重刷系统。Toolkit 的服务检测会覆盖显式依赖，
`build_quota_bpk.py` 在打包前恢复源 manifest 的 Storage 服务声明并检查 ZIP 完整性。

## 回退

两份经过完整 Flash MD5 和本地 SHA256 核对的 16 MiB 备份分别由
`runtime/verified-backup-path.txt`（微雪出厂系统）和
`runtime/verified-standalone-backup-path.txt`（独立额度固件 0.3.0）定位。
备份可能含设备私人数据，不应放入公开源码包。

停止电脑端采集器后，使用原 IDF 5.5 Python：

```powershell
tools\idf-tools\python_env\idf5.5_py3.12_env\Scripts\python.exe tools/restore_factory.py --port COM5 --source standalone-0.3.0
# 或 --source factory 恢复微雪出厂系统
```

恢复独立额度固件后，将 `device_protocol` 改回 `legacy`，再启动采集器。

## 官方资料

- [源码](https://github.com/espressif/esp-brookesia)
- [Waveshare 板卡 HAL](https://docs.espressif.com/projects/esp-brookesia/en/latest/hal/boards/waveshare.html)
- [App 工具链](https://docs.espressif.com/projects/esp-brookesia/en/latest/system/toolkit.html)
- [USB 控制协议](https://docs.espressif.com/projects/esp-brookesia/en/latest/system/usb_cli.html)

## 触摸与性能修正（s3.2）

用户已确认 s3.1 桌面与图标显示，但报告触摸相差约 90°、操作严重卡顿。
Board Manager 在厂商初始化后执行默认的 panel mirror/swap（全关闭），覆盖
厂商 MADCTL=0xA0，而旧触摸 swap_xy=true/mirror_y=true 保留，导致坐标方向不一致。
s3.2 将触摸 swap_xy、mirror_x、mirror_y 全部关闭，与最终显示方向一致。
同时修正 HAL 中 esp_lcd_touch_get_data 返回值类型，保留完整 esp_err_t 错误码。
将 CST9217 的触摸能力如实声明为单点，LVGL 从五个虚拟输入设备减为一个。

仅对 LVGL、GUI 后端和 FreeType 使用 -O2，其余继续 -Os；指令缓存从 16 KiB
增至 32 KiB，数据缓存从 32 KiB 增至 64 KiB，LVGL 最大休眠从 100 ms 缩至
20 ms。增加 S3_PERF 实际绘图周期的平均/最大耗时日志；这些值包含分块绘图和
传输等待，不能当成持续刷新帧率，也不能替代用户实机流畅度确认。

本次通过 --app-only 更新程序，在写入前读回设备分区表并与构建逐字节核对，
不重写 LittleFS、NVS、分区表与 bootloader，保留已安装额度 App 和设置。

```powershell
tools\idf-tools\python_env\idf5.5_py3.12_env\Scripts\python.exe tools/flash_brookesia.py --port COM5 --app-only
```

## 本地听书（s3.3）

s3.3 在 main/modules/audiobook 注册独立 Audiobook 服务，使用 dr_libs 流式解码本地 MP3/WAV，
通过板载 CodecPlayer 输出 PCM，不启用语音识别或音频处理器。听书 0.1.1 独立安装，
额度与天气保留；只写应用分区，保留 LittleFS、NVS、分区表和 bootloader。
用户确认界面正常且喇叭有声音。SD 读取及长音频验证等待装卡，详情见 AUDIOBOOK.md。
