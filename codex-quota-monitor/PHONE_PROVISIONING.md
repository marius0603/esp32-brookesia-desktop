# 安卓手机蓝牙配网

配套固件为 **0.8.3-s3.32**，适用于 ESP32-S3-Touch-AMOLED-2.16。设备使用 BLE 配网，手机直接把网络信息通过加密连接交给设备，不需要电脑中转或注册云端账号。原有设备端 Wi-Fi 列表、密码输入和已保存网络继续保留。

## 手机上使用

1. 在安卓手机安装乐鑫官方 [ESP BLE Prov 2.2.3](https://github.com/espressif/esp-idf-provisioning-android/releases/download/Provisioning_App_Release_2.2.3/ESP_Prov_BLE_2_2_3.apk)。[官方发布页](https://github.com/espressif/esp-idf-provisioning-android/releases/tag/Provisioning_App_Release_2.2.3) 同时提供源码和安装包；选择 BLE 版本。
2. 设备进入 **设置 → Wi-Fi → 手机配网 → 开始配网**，屏幕出现设备名 `PROV_XXXXXX` 和8位配对码。
3. 打开手机应用，允许“附近的设备/蓝牙”等所需权限；较旧安卓版本按提示允许定位并开启系统定位。选择添加设备，再选 **I don't have a QR code / 没有二维码**，选择 BLE 设备及屏幕上的设备名。
4. 在 Proof of Possession / 配对码 页面输入屏幕显示的8位码，保留字母大小写。若手机要求选择安全版本，选择 Security 1 / Secure。
5. 从手机列表选择 **2.4GHz Wi-Fi** 并输入密码，等待手机和设备显示配网完成。设备会保存成功连接的网络，重启后自动连接。

入口手动开启后开放五分钟，结束配网或超时后会停止蓝牙；再次开启生成新的随机配对码。Wi-Fi原来关闭时，开始配网会打开并保存原有Wi-Fi开关。成功后保留短时间让手机读取结果，然后自动关闭入口。输错密码可在本次窗口内重新提交，也可结束后重新开始。配网会切换网络，正在播放或录音时请先停止；开启入口后可返回其他页面。

此版在设备上显示配对码，暂不显示配网二维码。电脑端可验证协议，但日常配网只需要手机和设备。

## 实现和验证范围

- 使用 ESP-IDF 6.0.2 的 **NimBLE + protocomm Security 1**，Curve25519交换密钥、PoP验证和AES-CTR加密；未启用明文 Security 0。协议对接乐鑫官方 Android 应用，支持 `proto-ver`、`prov-session`、`prov-scan`、`prov-config`。
- 复用已有 Wifi 服务进行扫描、设置目标、连接及成功后的NVS保存，不创建第二套Wi-Fi驱动或清空原已保存网络。尚未收到手机“应用配置”之前，不改变目标网络；取消或超时后的失败连接会尝试恢复原目标。
- 等待本次连接产生新的获取IP事件后才判定成功，避免给原SSID重新配网时误把旧连接当成功。密码只在内存及原有Wi-Fi存储中处理，不加入仓库或公开报告；临时配对码只在开启的窗口内提供，普通状态接口不返回它。
- 蓝牙按需启动，关闭后销毁协议和蓝牙栈；NimBLE缓冲优先使用PSRAM。启用官方 `BT_CTRL_RUN_IN_FLASH_ONLY`，让控制器代码使用Flash，释放内部内存；配网协调任务的8KiB栈使用PSRAM并在后台休眠复用，涉及Flash的蓝牙初始化、销毁及网络恢复交给已有内部RAM服务调度器。开启前检查连续内存，不足时提示关闭其他应用，避免进入ROM断言。原Settings Wi-Fi页面以JSON合并方式增加入口，旧文档先备份，其他页面和桌面资源保留。
- 内置的协议编解码源自固定上游版本，出处、许可及二进制BSSID修正见 [协议组件](../platform/super_s3_216/components/phone_provisioning_protocol/README.md)。

## 构建和已有设备更新

工程准备顺序为四个补丁：S3适配、分页桌面、主题切换、手机配网。完整源码保存在本仓库的 `platform/super_s3_216`，工具链和下载缓存不入库。

```powershell
python tools/prepare_workspace.py
# 按仓库说明设置ESP-IDF后构建 examples/system/super_s3_216
python codex-quota-monitor/tools/backup_current_firmware.py --port COM3 --label before-phone-provisioning
python codex-quota-monitor/tools/update_brookesia_app_only.py --port COM3 --build <build目录> --backup <本次已校验私有备份目录>
python codex-quota-monitor/tools/deploy_phone_provisioning.py --port COM3
```

关闭串口额度采集器后进行更新，完成后恢复。更新器只写应用分区，核对设备MAC、分区表、备份及写回哈希。设置入口需要单独部署，因为应用分区更新不会覆盖现有LittleFS。安装器在SD和电脑私有runtime目录备份原Wi-Fi页面，并读取设备内解析后的紧凑JSON来避免旧版长文本串口回复丢字节。

固件包为 `packages/firmware/brookesia-0.8.3-s3.32-app-only.zip`，设置入口在 `packages/resources/phone-provisioning-wifi-s3.32.json`；校验值见 `packages/SHA256.json`。不包含设备Wi-Fi信息、临时配对码、运行日志或完整Flash备份。

## 可选电脑端检查

电脑需要可用的蓝牙适配器，以及本地ESP-IDF的protocomm Python协议定义。

```powershell
python -m pip install -r codex-quota-monitor/requirements-ble-test.txt
python codex-quota-monitor/tools/verify_phone_provisioning_ble.py --port COM3 --idf <ESP-IDF目录>
# 追加 --apply-existing 会经真实BLE加密协议重新配置并连接当前已保存网络
python codex-quota-monitor/tools/verify_phone_provisioning_lifecycle.py --port COM3 --cycles 5
# 可通过 --baseline <部署前私有快照.json> 对照部署前数据；省略时对照本轮测试前数据
```

检查覆盖错误配对码拒绝、正确加密会话、Wi-Fi扫描、短密码拒绝和可选的完整配网。配对码及网络信息只在进程中使用，报告仅记录检查结果。纯C++规则检查在 `tests/phone_provisioning_rules.cpp`，包括SSID、密码和超时边界。

本次实机已通过连续五次开关、配对码轮换与清除、设置启动和已有内容保留检查；电脑端真实BLE已完成错误码拒绝、加密扫描、短密码拒绝及当前网络重新配网。Android 2.2.3页面流程已对照官方源码，用户在Wi-Fi页面确认“出现配对码，手机配网成功”。重启后自动连接已配置网络、配网窗口保持关闭，故事、音量与书签保留；用户主动切换为经典Q版并确认保留。

## 回退

先结束手机配网。需要恢复旧界面时，将本次SD备份的 `wifi.json` 复制回 `/littlefs/apps/brookesia.general.settings/res/screens/wifi.json`；旧固件可通过已验证的s3.31程序包按同一应用分区更新流程恢复，仍保留当前网络、故事、主题与SD内容。不要通过写入完整出厂镜像来回退此功能。
