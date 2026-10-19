# 在现有微雪 Brookesia 系统中增加 Codex 应用

此目录目标是在保留 AIChats、Settings、MusicPlayer 等原有应用的系统工程中注册 Codex 应用。此路线尚缺完整出厂工程。用户后来明确授权备份后替换系统，目前板上部署独立固件 0.3.0；这不表示本目录的出厂集成已完成。原系统恢复见项目根目录 RESTORE_FACTORY.md。

## 已准备的组件

components/codex_quota_app 可复制到出厂工程的 components/ 目录中：

- CodexQuota 继承 Brookesia Phone App，通过与官方示例相同的注册机制进入桌面应用列表。
- run 创建应用界面，pause/resume 暂停和恢复定时器，back 交回系统关闭流程，close 交由 Brookesia 回收屏幕和定时器。
- 使用系统分配的可视区域，显示状态栏和导航栏。点击额度数字切换窗口，详情按钮查看两个窗口，R 请求刷新。
- 组件不初始化屏幕、触摸、USB、Wi-Fi、电源、GPIO 按键或全局亮度，不接管 app_main。
- 通过线程安全的数据接口接收电脑端发来的 JSON，兼容已有额度协议。
- 保留旧数据并标识过期，未知额度显示 --，倒计时归零后等待同步。
- 底部提供音量减、真实音量百分比、音量加和电源按钮。每次调整 5%，限制在 0..100%；关机需确认，可取消或通过返回键关闭弹窗。
- 电源和音量通过宿主接口工作；未接入时音量显示 --，相关按钮禁用，不以虚拟数值冒充系统音量。完全关机后使用板上 PWR 实体键开机，屏幕不能在断电时接收触摸。

## 接入现有系统工程

1. 将组件目录复制到完整出厂工程 components/ 下。
2. 沿用出厂工程的 Brookesia 实例、应用注册表、显示初始化、USB/Wi-Fi 服务及现有应用。
3. 确保 components/codex_quota_app 被纳入构建（例如让 main 的 REQUIRES 包含 codex_quota_app）。
4. 在现有传输服务中分发完整 JSON 行到 codex_quota_feed_json(json, length)。函数返回 true 表示解析成功；不要由应用再次安装已被系统使用的 USB 驱动。
5. 现有传输服务每 5 秒发送 codex_quota_protocol_hello() 返回的身份帧，并在系统初始化阶段注册刷新回调。

~~~cpp
#include "codex_quota_feed.h"

// 在宿主现有传输服务中接收到一行后：
bool accepted = codex_quota_feed_json(line, length);

// 宿主提供实际的发送函数；应用组件不持有串口：
codex_quota_set_refresh_callback([](void *context) {
    // 使用现有传输服务发送：{"type":"refresh","v":1}\n
}, transport_context);
~~~

这里的传输接入点须依据真实出厂工程确定，示例片段不能直接安装到已烧录的二进制中。接入成功后再将电脑端 config.json 的 serial_port 从 off 改回 auto，或指定真实端口。

## 电源和音量接入

include/codex_quota_controls.h 定义了宿主控制接口。在应用启动前、GUI 任务内或持有系统 GUI 锁时注册 codex_quota_device_controls_t：

- get_volume(context, percent)：读取系统扬声器输出音量，转换为 0..100%，成功返回 true。必须与出厂 Settings、MusicPlayer 等共用实际音量状态。
- set_volume(context, percent)：调用出厂音频服务调整音量，成功返回 true。读写失败时不更新虚假的本地音量。
- power_off(context)：请求出厂电源服务关机，接受请求返回 true。宿主负责停止播放、保存配置和电源时序；应用不直接写 AXP2101 寄存器。

通过 codex_quota_set_device_controls(&controls) 注册；传入 nullptr 可解除。注册和解除需与 GUI 操作串行，回调必须及时返回，不在 GUI 任务阻塞等待关机。需要排队时由宿主服务负责，并保持回调及 context 的生命周期有效。

音量按钮到达 0%/100% 时分别禁用减/加，周期读取实际值以反映其他应用的调整。电源按钮打开确认弹窗，仅确认后调用关机接口，失败可重试。此版本不把息屏伪装成关机，也不提供无法兑现的触摸冷启动按钮。

硬件依据：[微雪板载 PWR 电源键与 PMU 说明](https://docs.waveshare.net/ESP32-S3-Touch-AMOLED-2.16/)。实际音量、USB/电池供电下的关机与重新开机，需要在完整出厂工程集成后上板验证。

## 编译验证

compile-check/ 仅用于验证组件能与官方公开 Brookesia 核心编译和链接；它不是完整出厂系统，也不是可部署的替代固件。

~~~powershell
.\.venv\Scripts\python.exe tools/build_firmware.py --project brookesia/compile-check
~~~

不提供这个验证工程的烧录入口。

## 当前缺少的资料

官方当前仓库明确说明完整出厂固件的源码和构建说明尚未包含在仓库中。公开的 03_esp-brookesia 仅含核心及 SquareLine 示例，不能保证重现板上全部原有应用。已检查原始 examples/ESP-IDF-v5.5/03_esp-brookesia 的历史目录，同样未发现完整的出厂应用集合。

需要对应出厂版本的完整 ESP-IDF 工程，至少包含 main、AIChats/Settings/MusicPlayer 等应用源码、分区表、sdkconfig、依赖锁文件和资源生成方式。获得后才能具体合入传输服务、确认应用注册兼容性、核对持久化分区并生成保留原有应用的更新固件。

这里的 Brookesia 应用注册是源码中的对象注册，不等于已安装系统具备 APK 式的动态程序安装能力。当前没有找到出厂固件提供独立程序加载器的证据。

参考：

- [微雪出厂固件说明](https://docs.waveshare.net/ESP32-S3-Touch-AMOLED-2.16/Instructions-For-Use/)
- [官方源码与出厂镜像边界](https://github.com/waveshareteam/ESP32-S3-Touch-AMOLED-2.16/blob/main/docs/firmware.md)
