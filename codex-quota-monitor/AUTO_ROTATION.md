# 重力感应与自动旋转

适用设备：ESP32-S3-Touch-AMOLED-2.16；固件 0.8.3-s3.8 起。

设置 → 显示 → 自动旋转。首次使用默认开启；关闭后锁定当前方向。
开关和校准结果保存于 NVS，重启后保留；关闭时还会恢复锁定的方向。

使用板载 QMI8658 加速度计，31.25Hz 采样、每 100ms 读取一次；陀螺仪关闭。
支持 0°/90°/180°/270°，低通滤波后方向稳定 500ms 才切换，两次切换至少间隔 1 秒。
平放、接近对角线、明显加速或手指仍按住屏幕时保持原方向。
CO5300 使用硬件旋转，LVGL 保持 480×480，无新增全屏缓冲区。
触摸在 HAL 层反向换算一次，供应用和系统边缘手势共同使用。

原生服务 `AutoRotation`：

| 方法 | 参数与作用 |
| --- | --- |
| GetState | 读取 enabled、available、degrees、加速度、采样次数、错误与栈余量 |
| SetEnabled | `{ "Enabled": true/false }`，保存开关状态 |
| SetRotation | 自动旋转关闭时设置 `{ "Degrees": 0/90/180/270 }` |
| CalibrateUpright | 手持设备竖直并让期望的上边朝上，把该姿态校准为 0° |

传感器初始化失败时自动旋转不可用，保留原方向，设置中的开关置灰。
设置保存与 I2C 读取在独立的 6KiB 内部栈任务运行；写入 NVS 失败时保留待保存状态并间隔重试。

已有设备只刷应用分区，不会自动替换原有 LittleFS 内的设置页面。
停止电脑端额度采集，烧录 s3.8 后执行：

```powershell
# 位于 codex-quota-monitor，COM5 替换为实际端口
.venv\Scripts\python.exe tools/deploy_auto_rotation.py ..\platform\super_s3_216\overrides\settings-display.json --port COM5
```

脚本先将旧页面备份到 SD 卡 `/sdcard/rotation-backups/<时间>/display.json`，再原子替换设置页；
备份路径同时记录在本机 `runtime/auto-rotation-deployment.json`。恢复旧页面：

```powershell
.venv\Scripts\python.exe tools/deploy_auto_rotation.py --restore-from /sdcard/rotation-backups/<时间>/display.json --port COM5
```

全新编译的资源分区已包含新页面。触摸与设置的上游改动保存在 `patches/brookesia-s3.patch`，
服务源码保存在 `platform/super_s3_216/main/modules/auto_rotation`。
`tests/orientation_static.cpp` 可用 C++23 编译器进行编译期检查，覆盖方向分类、平放/晃动拒绝、
四方向的触摸坐标与屏幕映射往返、边界裁剪；实际重力方向及触摸仍需在设备上检查。
