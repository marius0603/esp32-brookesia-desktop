# 天气 App

当前版本：local.weather 0.2.2，运行于已部署的 ESP-Brookesia 0.8 本地适配系统 s3.2。
源码：D:/chatgpt_data/brookesia-apps/weather。

界面只显示当前温度、湿度、天气状况，以及可横向滑动的 24 个逐小时预报卡片。
湿度字号 30、天气状况字号 32；不显示“未来24小时”标题、体感、风速、三日预报或操作按钮。
默认查询上海（31.2304, 121.4737）。联网后由开发板直接通过校验证书的 HTTPS 获取数据，
不依赖电脑提供天气。应用打开后每 10 分钟刷新；联网状态变化会触发检查与重取。
后台暂停动画，返回应用时恢复；离线保留缓存并在天气文字前标明“缓存”。

## 背景

天气码与昼夜标志控制晴天/晴夜、多云、雨、雷雨、雾、雪的背景。
雨和雷雨采用玻璃水珠纹理，以及四个缓慢滑落的水珠图层，每秒最多更新八次；
不循环重绘整个页面或重复解码整张图片。切到后台后停止动画定时器。
纹理、图标由 tools/generate_weather_assets.py 和源资源中的代码绘制流程生成。
所有 24 小时卡片同时使用真实天气码、温度和当地小时；首个卡片为当前观测时刻之后
最近的整点。网络出口定位仅在 weather-settings.json 的 mode 为 auto 时启用，
结果保留“网络出口推测”来源，失败回退上海；默认 shanghai 模式不请求定位服务。

## 构建与安装

在 codex-quota-monitor 目录执行：

```powershell
.venv\Scripts\python.exe tools/build_brookesia_app.py ..\brookesia-apps\weather
.\stop.ps1
# 等待后台采集器退出，再操作串口
.venv\Scripts\python.exe tools/install_runtime_app.py ..\brookesia-apps\weather\dist\local.weather.debug.0.2.2.bpk
.venv\Scripts\python.exe tools/verify_weather.py
.\start.ps1
```

系统现有安装器对覆盖安装的删除步骤设有 5 秒等待；大资源更新可能报 Wait timeout
after 5000 ms，删除工作仍会完成。遇到该错误，应等几秒并重新建立 USB hello 会话后
重试安装，不能直接复用已结束的上传会话。此流程不擦除系统或 Wi-Fi 凭据。

## 验证

0.2.0 实机检查已通过：24 小时天气、雨天动画更新、Wi-Fi 断开保留缓存、重连自动取回
新数据。用户确认“显示正常，滑动流畅”。绘图日志记录平均约 11.1 ms，最大约 15.7 ms，
该结果是当时场景的绘图周期，不能当成所有场景的持续帧率。

JavaScript 八项测试覆盖缺失值、天气码、异步联网、刷新间隔、失败退避、断线重连、
缓存恢复、定位标记、24 小时数据选择、雨滴更新及后台暂停。
0.2.1 调整上述字号并删除标题；0.2.2 隔离脚本作用域，修复重复打开时的变量声明冲突。
设备安装和验证证据见 runtime/weather-*。

## 数据来源

[Open-Meteo 天气 API](https://open-meteo.com/en/docs)，天气状态为模型天气，非板载传感器读数。
[IPWhois 定位文档](https://ipwhois.io/documentation)仅用于可选网络出口定位。
页面保留 Open-Meteo 署名。

## 重复打开修复

原脚本在顶层声明 let/const，Brookesia 复用 QuickJS 上下文后，再次载入可能报
SyntaxError: redeclaration of SHANGHAI。0.2.2 使用立即执行函数隔离应用局部变量，
保留 globalThis.brookesia_app 生命周期入口；同一 VM 重复求值的回归测试通过。
额度 App 的同类 gui 重复声明错误同时修复。两个 App 各连续重开 6 次，共 12 次全部通过。
最终设备重开检查见 runtime/runtime-reopen-verification.json。
