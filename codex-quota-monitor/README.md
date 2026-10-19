# Codex 额度仪表盘

当前部署：ESP-Brookesia 0.8 本地适配版 0.8.3-s3.3（ESP-IDF 6.0.2），额度 App 0.2.2 已通过 USB 独立安装，使用吃豆人和豆子显示真实剩余额度，用户确认显示和动画正常。额度、天气的重复打开错误已修复，各连续重开 6 次全部通过。电脑端使用 `device_protocol=brookesia`、`serial_port=COM5`。s3.2 已修正触摸约 90° 错位并优化绘图与缓存；用户实测确认点击位置正常、已基本流畅。部署、开发和回退见 [BROOKESIA.md](BROOKESIA.md)，验证记录见 [BROOKESIA_VERIFICATION.md](BROOKESIA_VERIFICATION.md)，额度动画说明见 [PACMAN_QUOTA.md](PACMAN_QUOTA.md)。

天气 App 0.2.2 已独立安装，默认上海，由开发板联网获取天气，显示温度、湿度、天气状况和 24 小时预报，背景随天气变化；界面与部署记录见 [WEATHER.md](WEATHER.md)。

Windows 电脑端持续采集并推送额度。原厂系统及独立额度固件 0.3.0 的两份完整 16 MiB Flash 备份均保留，后者使用 ESP-IDF 5.5.5。`brookesia/components/codex_quota_app` 是旧出厂系统集成方案的参考组件，不用于当前 0.8 运行时 App。

`firmware/` 是回退用的独立额度固件工程，0.1.0 固件包为旧原型。烧录入口会核对完整备份和设备身份。

回退版本 0.3.0 底部提供音量减/加和触摸关机按钮。新版额度 App 当前专注额度显示，音量通过“设置”调节，原触摸关机按钮尚未迁移。

适用于微雪 ESP32-S3-Touch-AMOLED-2.16，使用 Windows 电脑采集当前登录的 Codex 账号额度，再通过 USB 发送到小屏。包含真实额度采集、独立桌面预览和 ESP-IDF 固件工程。

## 电脑端运行

项目目录：D:\chatgpt_data\codex-quota-monitor

本机已安装好电脑端依赖。双击 start.cmd 可启动后台并打开实时预览，双击 stop.cmd 停止后台。关闭独立预览窗口不会停止后台采集。

首次安装依赖并验证当前账号：

~~~powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
~~~

启动后台及预览窗口：

~~~powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1 -Preview
~~~

单独打开预览：

~~~powershell
powershell -ExecutionPolicy Bypass -File .\preview.ps1
~~~

预览窗口点击切换两个额度窗口。直接运行以下命令可在预览中用 R 请求刷新，关闭窗口即停止采集：

~~~powershell
.\.venv\Scripts\python.exe -m quota_monitor --preview
~~~

停止后台：

~~~powershell
powershell -ExecutionPolicy Bypass -File .\stop.ps1
~~~

需要登录 Windows 后自动启动时，执行 install-startup.ps1；使用 -Remove 删除该项目创建的启动项。

config.json 可设置采集间隔、过期阈值、指定 USB 串口、提醒阈值和 Codex 路径。修改后重启后台。默认每 60 秒查询一次，每 2 秒推送到设备；电脑与设备之间仅发送额度数据。首次运行必须已在 Codex 中使用 ChatGPT 账号登录。API Key 登录不提供这里监控的订阅额度。

运行数据位于 runtime/latest.json，滚动日志位于 runtime/monitor.log。采集通过官方 Codex app-server 的 account/rateLimits/read 完成，不发起模型对话。程序不会读取或复制 auth.json 的内容。

## 固件界面

- 概览页：主额度剩余百分比、进度环、重置倒计时、副额度、同步时间。
- 左右滑动切换概览、详情、设置。点击概览切换主额度；点击详情请求刷新；点击设置切换亮度。
- GPIO18：短按刷新，长按息屏/唤醒；息屏时短按先唤醒。
- 亮度与主额度选择保存在 NVS；60 秒闲置自动调暗，5 分钟闲置自动息屏。
- 默认余量低于或等于 20% 为橙色，10% 为红色；失去有效数据后仪表变灰并给出状态。
- USB 拔出后保留旧数值并显示电脑未连接。倒计时到期显示等待同步。
- 同步时间按北京时间显示；屏幕使用本机字体生成的精简中文字库。

固件基于 ESP-IDF v5.5.5、微雪 BSP 2.0.1、LVGL 9.3。板载屏幕及触摸通过官方 BSP 初始化，无需自行重新分配引脚。

## 编译与上板

本机工具链已经安装在 tools/ 内。重新准备工具链时可运行：

~~~powershell
.\.venv\Scripts\python.exe .\tools\bootstrap_toolchain.py
~~~

该脚本下载包含子模块的 ESP-IDF 官方完整归档，以及 ESP32-S3 工具链。构建工具会跳过 SDK Git 版本检测中的全目录 dirty 扫描，以避免 Windows 下首次解压后长时间扫描；这只修改版本探测脚本，不修改 SDK 驱动或编译器代码。

当前独立固件可离线编译。烧录命令只适用于已明确允许替换出厂系统、且有校验通过的整机备份的场景；它会替换原桌面，不能用于宣称保留出厂应用的集成：

~~~powershell
powershell -ExecutionPolicy Bypass -File .\tools\build-firmware.ps1 -Port COM9 -Flash
~~~

COM9 应替换为实际开发板端口。烧录前停止采集服务，避免串口被占用；烧录将替换开发板现有应用固件。当前阶段不烧录、不擦除开发板。

上板时需验证：USB 枚举、实际屏幕方向与边缘裁切、触摸滑动、GPIO18 按键、亮度与息屏唤醒、PMU 供电、拔插重连，以及和 Codex 界面的额度对照。软件测试和成功交叉编译不能替代这些硬件验证。

## 结构与测试

quota_monitor/ 是 Windows 程序，firmware/ 是固件，tests/ 是自动化测试，PROTOCOL.md 定义 USB 数据格式。

~~~powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
~~~

工具链、下载缓存、第三方示例、运行状态及虚拟环境未纳入源文件。中文字体如需修改文案，安装 tools/font-converter 的依赖后运行 tools/generate_font.py 重新生成；生成器默认使用本机 Windows 黑体，适用于本机开发。

参考资料：

- [Codex App Server](https://learn.chatgpt.com/docs/app-server)
- [微雪 ESP-IDF 开发](https://docs.waveshare.net/ESP32-S3-Touch-AMOLED-2.16/ESP-IDF/)
- [ESP-IDF v5.5.5](https://github.com/espressif/esp-idf/releases/tag/v5.5.5)

软件验证详情见 VERIFICATION.md。artifacts/ 中提供 0.3.0 源码包及固件包；旧 0.1.0 包仅作历史原型。下载缓存、完整工具链和私有整机备份不打入源码包。

听书 App 0.1.1 已安装；s3.3 加入本地 MP3/WAV 解码与扬声器输出，用户已确认测试音发声。书籍下载按用户要求暂停，等待 SD 卡。使用和限制见 [AUDIOBOOK.md](AUDIOBOOK.md)。

翻页时钟 0.1.1 已安装，只显示大号北京时间时分，分钟变化时翻页；用户确认显示正常。使用与源码见 [FLIP_CLOCK.md](FLIP_CLOCK.md)。
