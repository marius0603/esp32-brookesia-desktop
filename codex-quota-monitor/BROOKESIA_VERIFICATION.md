# 部署验证：2026-10-18

当前设备：COM5，Waveshare ESP32-S3-Touch-AMOLED-2.16。
ESP-IDF 6.0.2；System Super 0.8.3 / Core 0.8.4；构建版本 **0.8.3-s3.2**。
这是官方 0.8 开发分支的本地 S3 适配，固定提交见 BROOKESIA.md。

## 用户实屏确认

用户先确认 s3.1 能显示桌面和图标，随后报告触摸约 90° 错位、严重卡顿。
s3.2 更新后，用户明确确认：**“位置对应，点击正常”**，**“已基本流畅”**。

## 修复与验证

- 触摸轴交换与镜像全部关闭，与 Board Manager 最终显示方向统一。
- CST9217 如实声明为单点，LVGL 只创建一个触摸输入设备；修正读取返回值为 esp_err_t。
- LVGL、GUI 后端、FreeType 使用 -O2，其余继续 -Os；指令/数据缓存分别为 32/64 KiB。
- 固件仅写入程序区 0x60000；写入前逐字节核对设备分区表，写入后 esptool 哈希校验通过。
- NVS、LittleFS、分区表、bootloader 未重写；已有额度 App 保留并重新注册。
- 桌面启动完成；可用 PSRAM 5,022,168 字节，内部 RAM 88,423 字节，未观察到 panic/OOM。
- 文件、设置、额度 App 均通过 USB 启动检查，状态 Running，last_error 为空；启动调用耗时约 0.8–1.1 秒。
- 真实额度文件写入、读回一致；额度 App 发出控件更新确认，验证结束已返回桌面。
- 绘图周期统计分组平均约 15.8–70.3 ms，测试中最大 197.2 ms；包含界面切换，不能当成持续帧率。
- 电脑端 17 项测试通过；后台同步已恢复。

证据：runtime/brookesia-s3.2-boot.log、brookesia-s3.2-flash.log、
brookesia-flash-result.json、brookesia-s3.2-ui-verification.json、
brookesia-s3.2-ui.log、brookesia-s3.2-python-tests.log。

## 运行时 App 更新

额度 0.2.1、天气 0.2.2 已独立安装，无需重刷系统。曾在两个应用重开时复现
QuickJS 的 gui / SHANGHAI 重复声明错误；用立即执行函数隔离局部变量，保留
globalThis.brookesia_app 入口。额度还兼容框架已移除定时器后调用 on_stop 的顺序。

两个 App 各连续重开 6 次，共 12 次全部通过；额度数值与真实样本一致，动画持续更新。
用户确认吃豆人“显示正常，动画正常”。天气保留字号 30/32、去除标题、24 小时预报和天气背景。
电脑端 21 项测试、天气 JavaScript 8 项测试及额度 JavaScript 回归通过。
USB 客户端过滤已知绘图统计行，严格限制请求截止时间，仅对明确的会话未初始化拒绝重建会话并重试。
证据：runtime/runtime-reopen-verification.json、quota-pacman-python-tests.log、weather-install-0.2.2-retry.log、quota-pacman-install-0.2.1.log。

天气已验证实际 Wi-Fi 联网、HTTPS 获取、断线缓存与重连刷新；天气页面用户确认显示正常、滑动流畅。

## 备份与限制

微雪出厂系统、独立额度固件 0.3.0 的两份完整 16 MiB Flash 备份均已验证并保留。
升级前 s3.1 的程序镜像另存于 artifacts/brookesia-s3.1-before-touch-fix。

在线应用商店及实际音频播放未测试，AI/视频未集成。
音量 API 已在 s3.1 验证读写并恢复原值；不能据此认定实际发声已验证。
新版额度 App 尚未迁移原 0.3.0 触摸关机按钮；音量通过系统设置调节。
现有日志仍可见启动时一次触摸无效响应及个别屏幕边缘 Y=480 警告；
本轮用户实测未报告相应操作异常，未将其误记为已修复。
当前为轻量应用开发配置，不能据此宣称已恢复微雪出厂全部 App。

额度布局更新 0.2.2：去除页面标题及同步时间，重置倒计时字号 30；独立安装成功，
再次重开两次、真实样本与动画检查通过。证据：runtime/quota-layout-verification-0.2.2.json。

## s3.3 听书扩展

2026-10-18：仅更新应用分区，esptool 哈希校验通过；保留额度、天气、Wi-Fi 配置。
听书 App 0.1.1 已安装，重开测试和低幅度 440 Hz 测试音通过；用户确认界面正常、喇叭有声音。
书籍未下载，SD 卡读取与持续解码尚待装卡测试。详见 AUDIOBOOK.md。
