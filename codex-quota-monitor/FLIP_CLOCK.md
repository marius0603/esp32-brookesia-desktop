# 翻页时钟

`local.flipclock` 0.1.1，独立安装于 ESP-Brookesia s3.3，无需重刷固件。
从桌面打开“翻页时钟”，只显示居中的大号 `HH:MM`：北京时间、24 小时制，无秒数、日期或标题。
数字使用 128 像素字号绘制，卡片从 70×114 放大为 92×152；用户确认正常、没有裁切。

数字变化时，旧数字上半页向中线收起，新数字下半页从中线展开；仅变化的数字翻页。
动画目标时长 360 ms，40 ms 请求一次更新，实际帧数随调度变化。空闲每 250 ms 检查分钟，
同一分钟不更新图形。后台停止动画，恢复时直接显示正确时间；大幅校时直接跳到新时间。

使用设备系统时间与已有 SNTP 服务校时，离线继续走时；断电重启后如尚未获得有效时间，
显示四条短横线，联网校时后恢复。没有模拟或从电脑推送时钟数据。

数字图片由 `tools/generate_assets.py` 代码绘制，字体仅用于生成图片，不打包字体文件。
采用设备已有的 PNG 解码器，关闭 Toolkit 的额外位图转换，避免同时存放 PNG、原始位图和独立描述文件。
原六位版本因存储不足安装失败后已清理临时目录，未移除其他应用。

## 源码与构建

源码：`D:/chatgpt_data/brookesia-apps/flip-clock`。

```powershell
.venv\Scripts\python.exe ..\brookesia-apps\flip-clock\tools\generate_assets.py
.venv\Scripts\python.exe tools/build_brookesia_app.py ..\brookesia-apps\flip-clock
.\stop.ps1
# 等待后台退出，再使用串口
.venv\Scripts\python.exe tools/install_runtime_app.py ..\brookesia-apps\flip-clock\dist\local.flipclock.debug.0.1.1.bpk
.venv\Scripts\python.exe tools/verify_flip_clock.py
.\start.ps1
```

JavaScript 回归检查包括：北京时间换算、午夜四位进位、只更新变化数字、上下半页完成、后台停止、
恢复显示、校时跳变和同一 JavaScript 上下文重复加载。实体屏幕已确认原版翻页正常、大字版只显示时分。
安装记录：`runtime/flip-clock-install-0.1.1.log`；设备检查：`runtime/flip-clock-verification.json`。

最终设备检查通过：连续重开两次、设备北京时间一致、分钟翻页完成（本次记录 8 帧）。

## s3.28 前台恢复修复

应用仍为0.1.1。设备曾出现时钟仍是Running、但没有前台应用的状态，再次点击图标时启动函数直接成功返回，画面留在桌面。s3.28对失去前台的运行时应用先停止旧实例再启动，并在桌面图标入口处理这一状态。检查脚本已支持`--port COM3`，等待桌面启动完成后验证连续重开、跨应用返回及完整分钟翻页，详见[桌面翻页说明](PHONE_LAUNCHER.md)。

2026-10-28修复版实机检查通过：连续重开两次、切到轻学习再关闭后恢复时钟前台、北京时间一致，完整分钟翻页8帧。桌面图标点击的用户确认另记于桌面说明。

用户随后现场确认“时钟正常”。
