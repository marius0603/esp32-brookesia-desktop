# 桌面 CPU / RAM 占比（s3.60）

系统桌面左上角同一行显示CPU、RAM，音量和电量紧跟RAM右侧；右侧原有
Wi-Fi和时间留在原处。所有新增状态使用透明背景，手绘主题为奶油色文字/图标，
赛博主题为浅青色，随主题切换。进入应用或息屏时隐藏，回到桌面/唤醒后恢复。
标签不接收点击，不改变九宫格和图标尺寸。

## 统计口径

- CPU：读取FreeRTOS每核空闲任务累计运行时间，用相邻约1秒的差分估算忙碌率；
  双核平均后归一化到0～100%，一个核满载、另一个核空闲为50%。首个有效窗口
  前显示`--`。U32计数器回绕按无符号差分处理，异常长间隔重新建立基线。
- RAM：`MALLOC_CAP_8BIT`可分配堆的已用/总量，包含内部DRAM与PSRAM，字节只计
  一次；不代表Flash或SD占用，也不包含堆外静态区。接口另保留内部/PSRAM明细，
  总百分比不能替代内部连续块/DMA余量诊断。
- 显示取整数百分比，维护接口保留两位小数。CPU是基于任务运行时间的估算，
  不是硬件周期级分析。电量继续复用原30秒缓存，音量继续同步原共享目标。

## 实现

`resource_monitor.cpp`复用现有方向/电源后台任务，约每秒采样，不增加任务栈，
不创建周期性分配，不扫描所有任务，也不写Flash。GUI只读取短临界区保护的
缓存；CPU/RAM变化才改文字。音量、电量单独缓存变化，按CPU/RAM实际宽度定位
在右侧并留20像素间隔；CPU与RAM、音量与电量之间各留四个空格，
加大四项状态的区分度，并检查不遮挡原生Wi-Fi/时间。

`DeviceModes.GetResourceUsage`返回CPU总量/每核、RAM及内部/PSRAM总量与空闲量、
采样计数和时间戳。`GetWeatherLayers`额外报告状态标签的位置、文字颜色及背景
透明度，用于实机核对；查询不改变音量、家长设置或播放内容。

## 构建与更新

```powershell
python tools/prepare_workspace.py
python codex-quota-monitor/tools/verify_resource_monitor.py --port COM5 --capture-baseline
python codex-quota-monitor/tools/brookesia_idf6.py build
# 先执行backup_current_firmware.py，完整备份只存runtime私有目录
python codex-quota-monitor/tools/flash_app_only.py --port COM5
python codex-quota-monitor/tools/verify_resource_monitor.py --port COM5
```

固件开发使用ESP-IDF Python。自定义构建路径可设置`BROOKESIA_PROJECT`、`IDF_PATH`、
`IDF_TOOLS_PATH`；烧录脚本相应使用`--project`与`--idf`。更新前核对设备、完整
备份、版本和分区表，只写应用区，并比较写入前后所有应用分区外Flash区域的
MD5；不烧录NVS、LittleFS、模型或SD资源。已发布程序为
`packages/firmware/brookesia-s3.60.bin`，哈希在`packages/SHA256.json`。

## 验证

`tests/resource_monitor_static.cpp`用目标编译器静态断言验证空闲/满载、单核忙碌
的双核归一化、U32回绕、零间隔和RAM边界/舍入。固件已编译并通过程序区读回及
保护区比较。实机测试脚本检查统计公式/采样推进、左上角单行布局、透明底与
主题色、和原生Wi-Fi/时间不重叠、应用内隐藏与返回恢复，并核对14应用、
30故事、20儿歌、原音量及显示/勿扰/深睡偏好。

最终加宽间距版读回：CPU/RAM从x=8开始，音量/电量组到x=305结束，
原Wi-Fi从x=360、时间从x=421开始，标签背景透明度为0；应用内隐藏与返回恢复
均通过。用户已查看前一版并要求加宽间距，本版实屏间距观感待反馈。
验证基线通过`--capture-baseline`在更新前保存，和日志一样仅留本地runtime目录。

实时日志和完整Flash备份不提交；测试中的CPU/RAM值随当时负载与缓存变化，
不写成固定的“正常占比”。
