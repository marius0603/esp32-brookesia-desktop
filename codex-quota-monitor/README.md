# Codex 额度仪表盘

当前额度 App **0.2.5**、系统固件s3.63（ESP-IDF 6.0.2）：设备额度页前台每60秒发请求，仅Codex桌面已运行时电脑才查询，15秒无有效回应显示已过期。电脑不再主动定时查询。先运行`launch-codex.ps1 -InstallShortcut`，以后通过桌面**Codex (device sync)**打开Codex，监听自动跟随启动/退出，无需单独手动运行同步程序，也不配置开机自启动。原来的Codex入口不会联动。使用及实机验证见 [PACMAN_QUOTA.md](PACMAN_QUOTA.md)，全部应用当前进度见[仓库说明](../README.md)。

天气 App 0.2.2 已独立安装，默认上海，由开发板联网获取天气，显示温度、湿度、天气状况和 24 小时预报，背景随天气变化；界面与部署记录见 [WEATHER.md](WEATHER.md)。

Windows电脑端监听设备请求后按需查询，不会主动打开Codex桌面。原厂系统及独立额度固件0.3.0的完整Flash备份仅在本机私有保存，后者使用ESP-IDF 5.5.5。`brookesia/components/codex_quota_app`是旧出厂系统集成参考，不用于当前0.8运行时App。以下独立固件界面和编译内容仅作历史说明。

`firmware/` 是回退用的独立额度固件工程，0.1.0 固件包为旧原型。烧录入口会核对完整备份和设备身份。

回退版本 0.3.0 底部提供音量减/加和触摸关机按钮。新版额度 App 当前专注额度显示，音量通过“设置”调节，原触摸关机按钮尚未迁移。

适用于微雪 ESP32-S3-Touch-AMOLED-2.16，使用 Windows 电脑采集当前登录的 Codex 账号额度，再通过 USB 发送到小屏。包含真实额度采集、独立桌面预览和 ESP-IDF 固件工程。

## 电脑端运行

项目目录：D:\chatgpt_data\codex-quota-monitor

本机已安装好电脑端依赖。日常使用Codex联动快捷方式即可；`start.cmd/start.ps1`保留为Codex已打开时手动启动监听的入口，`stop.cmd/stop.ps1`停止监听。关闭预览窗口不停止监听，但实际退出Codex桌面会停止监听。

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

按当前用户设置不安装Windows登录自启动；已有旧启动项可用`install-startup.ps1 -Remove`移除。新联动入口通过`launch-codex.ps1 -InstallShortcut`创建。

config.json可指定USB串口、提醒阈值和Codex路径，修改后重启监听。当前Brookesia模式约每2秒读取设备请求，每个新请求查询一次并回复，不周期推送；设备前台每60秒请求、15秒无有效回应即过期。`poll_seconds/stale_seconds`保留用于旧独立固件和电脑预览，不控制新版设备的60/15秒规则。电脑与设备之间仅发送额度和请求ID；需在Codex中使用ChatGPT账号登录。

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
