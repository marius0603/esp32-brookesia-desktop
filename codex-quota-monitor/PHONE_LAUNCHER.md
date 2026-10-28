# 手机式桌面 · s3.29

桌面改为横向分页：每页两行、按屏幕宽度自动计算列数，480×480屏幕为3列共6个应用。当前10个应用分为两页，底部实心圆点表示当前页。左右拖动可跟手移动，普通拖动24dp即可切换一页，350ms内的短促轻扫只需12dp，否则回到原页；首尾不循环，边缘拖动有阻尼。保留现有Q版图标、应用名称、点击打开、状态栏及应用内手势。

翻页只在桌面前台生效。拖动超过8dp且横向位移明显大于纵向时开始移动，并抑制滑动后的点击300ms，避免翻页时打开图标。应用列表刷新时将当前页限制在有效范围，隐藏的儿童模式应用不会占据页内位置。

同时修复应用仍被标记为运行中、却已经失去前台的情况。原启动函数直接返回成功，桌面启动动画结束后仍留在桌面，看起来像时钟闪退；现在对这样的运行时应用先停止旧实例再正常启动，恢复真实前台和界面。桌面图标入口也在启动动画之前处理这种状态，正常前台应用保持原行为。

## 安装和回退

先停止额度同步，并用`tools/backup_current_firmware.py`创建和校验本机私有完整备份。安装顺序为桌面资源、应用分区、重启，不覆盖NVS、LittleFS或SD分区：

```powershell
# 在codex-quota-monitor目录执行，端口按实际设备修改。
.venv/Scripts/python.exe tools/deploy_phone_launcher.py --port COM3
# 解压 packages/firmware/brookesia-0.8.3-s3.29-app-only.zip 后：
.venv/Scripts/python.exe tools/update_brookesia_app_only.py --port COM3 --build <解压目录> --backup <私有完整备份目录>
.venv/Scripts/python.exe tools/verify_flip_clock.py --port COM3
```

独立桌面资源在`packages/resources/phone-launcher-s3.28.json`，也包含在固件包的`launcher/app_launcher.json`中。安装器将旧文档、音量与故事列表备份到私有`runtime/phone-launcher-时间戳`；压缩JSON后写入，再读取核对。回退s3.27时也需要恢复该目录中的旧`app_launcher.json`，然后重新启动。不要只回退应用分区而保留新版桌面文档。

源码重建顺序为固定上游、`patches/brookesia-s3.patch`、`patches/phone-launcher.patch`及平台文件，`tools/prepare_workspace.py`已包含顺序。新补丁覆盖桌面分页及运行时前台恢复。设备启动后必须等待桌面处于Running，再运行应用检查，避免在系统仍注册资源时启动应用。

## 验证

时钟脚本检查两次关闭重开，再启动轻学习、关闭轻学习、重新打开仍为Running的时钟，要求时钟恢复前台，并检查实际北京时间和一次完整分钟翻页。桌面左右拖动、圆点、第二页点击和时钟实际显示需结合设备手动确认。日志和完整备份均不进入Git。

2026-10-28：s3.28应用分区写入及读回校验通过，桌面冷启动成功。时钟连续重开2次、失去前台后恢复、实际北京时间及8帧完整分钟翻页均通过；设备仍有10个可见应用、10本故事，音量75与更新前一致。用户确认“时钟正常”，同时反馈翻页需要滑动很长距离，因此s3.29将普通翻页门槛从48dp降为24dp、开始跟手门槛从16dp降为8dp，并增加350ms内12dp短扫判定。s3.29写入及读回校验通过，时钟重开、跨应用返回和8帧分钟翻页再次通过，故事及音量保持不变。用户实测确认“短距离轻扫可以翻页，手感正常”。
