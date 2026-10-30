# 小马蓝牙遥控 0.1.0

安卓手机直接通过BLE控制ESP32-S3设备，不需要同一Wi-Fi，也不需要电脑中转。手机需要在设备的蓝牙覆盖范围内。本轮优先实现蓝牙，跨网络遥控暂缓。

## 安装与连接

设备端需要配套固件 **0.8.3-s3.36** 和s3.34独立蓝牙设置资源；安卓端安装 [xiaoma-remote-0.1.0.apk](../packages/android/xiaoma-remote-0.1.0.apk)，支持Android 8及以上。

1. 设备进入 **设置 → 蓝牙 → 开启蓝牙遥控**。先停止正在进行的播放或录音，再开启入口；开启后可从手机播放故事。
2. 屏幕会显示 `CTRL_XXXXXX` 和8位临时配对码。原来的“开始配网”仍用于乐鑫ESP BLE Prov，设备名为 `PROV_XXXXXX`。
3. 手机打开“小马遥控”，允许“附近设备”权限，点击“扫描设备”；旧版Android还需要允许定位并打开系统定位开关。
4. 输入设备显示的配对码，点击扫描出的设备。连接成功后可调整音量和亮度，分页查看应用、故事并点击打开或播放。

支持暂停、继续、停止听书、息屏、唤醒和锁屏。亮度可调10%至100%，音量0至100%仍经过设备原有音量上限和勿扰逻辑。锁屏后仅能读取状态，需在设备上快速连按两次音量＋解锁。儿童模式下不能从手机直接打开应用，听书仍受原家长授权限制。

每次开启生成新配对码，窗口最多30分钟，成功连接不会延长窗口；再次点击设备上的“结束连接”即可关闭。配网与遥控共用蓝牙硬件，每次只开启一种模式。当前为前台遥控应用，没有后台常驻服务，也不保存配对码。此应用无需互联网、麦克风或云端账号。

## 设备更新

关闭电脑额度采集器，使用USB数据线连接设备，先做本次私有完整备份，再只更新应用分区：

```powershell
python codex-quota-monitor/tools/backup_current_firmware.py --port COM3 --label before-ble-remote
python codex-quota-monitor/tools/update_brookesia_app_only.py --port COM3 --build <s3.36构建目录> --backup <本次校验备份目录>
python phone-remote/tools/deploy_bluetooth_settings.py --port COM3
# 安装后重启设备，以清除Settings预载界面缓存
```

入口资源通过合并方式安装，先备份原Wi-Fi页面，保留其余页面。更新器保留NVS、LittleFS、应用、SD故事和主题；不要写入完整构建目录中的出厂Flash参数。完成验证后恢复额度采集器。

s3.34的部署器另外备份首页、屏幕注册和导航等五份设置文档。必须在资源安装后重启，停止再打开设置不会清除预载界面。回退旧固件时也需还原本次对应的设置文档备份，保证菜单与固件导航能力一致。

从s3.34升级到s3.35只需更新应用分区，沿用现有设置资源和安卓0.1.0安装包。s3.35将“桌面”请求接入系统首页流程；已经运行的原生设置页重新打开时重新挂载到前台，避免启动请求返回成功却不显示页面。

s3.36针对连续打开多个应用后的失败，切换时先关闭上一应用页面，退出脚本应用时释放运行环境；原生设置等应用保留界面缓存，加快再次进入。在线助手的断开请求是异步的；开始下一应用前等待音频所有权释放，确保网络回调停止、大录音缓冲已回收，最多等待20秒，超时则提示稍后重试。后台服务按各应用原有关闭逻辑处理；听书页面关闭仍会停止听书。遥控指令由独立协调循环执行，避免打开应用时的嵌套服务调用占满共享线程。屏幕SPI最大传输块设为4092字节、队列深度设为1，避免两笔较大的内部DMA临时缓冲与蓝牙争抢内存。保留整屏PSRAM绘制及现有壁纸。同步系统任务即使抛出异常也会完成等待结果，返回原始错误，避免调度器捕获异常后调用方永久等待。需同时安装电子宠物0.1.3，按当前动作缓存两到三张帧，避免一次预载八张帧的内存峰值。应用商店的存储、网络及界面异步回调转由应用定时任务统一处理，关闭时丢弃旧回调并取消迟到的HTTP请求，避免后台回调访问已经释放的页面上下文。USB状态另提供当前生命周期阶段，便于区分卡在加载、关闭或挂载。安卓端仍用0.1.0，独立蓝牙菜单资源沿用s3.34。

已有s3.34/35设备升级时只更新应用分区，并运行 `python codex-quota-monitor/tools/deploy_virtual_pet.py --port COM3` 安装宠物0.1.3；已有SD动画帧与自定义作息继续使用。

## 构建手机安装包

电脑需要Python。工具下载到源码仓库外，首次约330MB；下载地址与SHA256固定在 `tools/downloads.json`，工具和签名私钥不入Git。

```powershell
python phone-remote/tools/bootstrap_android.py --cache D:/codex/android-remote-build
python phone-remote/tools/build_android.py --tools D:/codex/android-remote-build/tools.json --work D:/codex/android-remote-build/app
python phone-remote/tests/verify_android_protocol.py --tools D:/codex/android-remote-build/tools.json --idf <ESP-IDF目录> --work D:/codex/android-remote-build/protocol-tests
```

安装包使用本地开发签名；继续发布更新时需保留同一外部构建目录内的签名文件。更换签名需要先卸载手机上的旧版本。Bouncy Castle 1.80用于X25519运算，许可随源码及APK的 `assets/licenses` 提供。

## 协议与验证

复用ESP-IDF protocomm Security 1：X25519、临时PoP和连续AES-CTR字节流。遥控模式只注册 `prov-session`、`proto-ver`、`remote-control`；不开放Wi-Fi配置端点。遥控特征UUID为 `1775ff55-6b43-439b-877c-060f2d9bed07`。同一会话串行交换JSON请求和回复，不并行发送，以免破坏加密流顺序。

设备只接受预定义指令：`status`、`volume`、`brightness`、`apps`、`open`、`stories`、`play`、`pause`、`resume`、`stop`、`sleep`、`wake`、`lock`。列表每页三项、页码从零开始；不提供任意服务调用、文件访问、录音或家长设置接口。

设备端s3.34已安装，应用分区读回校验和设置页安装核对通过。APK实际使用的Java协议代码已与独立Python实现核对官方protobuf字段、密钥协商、配对证明及连续双向加解密，也通过电脑蓝牙与实机完成连接、音量/亮度调整、列表及打开应用检查；测试设置随后恢复。安卓APK已构建并通过签名校验，手机安装和界面操作需现场确认。

实机另已通过锁屏后拒绝唤醒和调音量检查，以及原配网模式的错误配对码拒绝、加密扫描及短密码拒绝回归。原故事、书签、播放模式、音量和桌面主题核对保留。

`tests/check_settings_navigation.py --upstream <上游源码目录>` 检查事件订阅与导航判定两份名单一致，并核对蓝牙页面的跳转目标、根资源与屏幕流注册。

s3.34独立蓝牙菜单已由用户确认可以进入，并显示设备名和配对码。

s3.35已通过保持BLE连接的两轮“时钟→设置→桌面”、重复打开设置、电子宠物退出后再次打开检查；测试核对实际前台应用，设备直接启动宠物也成功。对应测试增加 `--navigation-only` 运行选项。手机端的本轮复测尚待现场确认。

s3.36已通过实机Wi-Fi与BLE同时开启的三轮全应用切换（每轮11个，共33次），逐次核对实际前台、单前台状态及无异常重启；三轮回桌面PSRAM剩余分别为2,532,092、2,528,184、2,524,792字节。音量、亮度、列表及非法命令拒绝检查通过。宠物0.1.3在Wi-Fi与BLE开启时通过全部八帧、喂食/陪伴/睡觉预览、时钟同步和退出重开检查，正式BPK已恢复。测试保留10篇故事、听书偏好、作息和经典Q版主题；用户新连接的Wi-Fi继续使用。`--sweep --require-wifi` 可复现联网压力测试；手机界面操作仍需用户现场复核。

参考：[ESP-IDF protocomm](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/provisioning/protocomm.html)、[Android BLE](https://developer.android.com/develop/connectivity/bluetooth/ble/ble-overview)。
