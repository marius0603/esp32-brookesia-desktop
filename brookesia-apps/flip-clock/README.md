# 时钟 0.2.1

保留大号HH:MM翻页及金属指针表盘，猫咪款替换为用户确认的细腻橘猫图集。
屏幕中部左右滑动循环三款表盘，至少48像素的水平移动且以水平为主才生效；
上下操作留给系统。选择保存在clock-face.json，重开后恢复。

![白天猫咪表盘示意](watchface-cat-day-preview.png)
![夜晚猫咪表盘示意](watchface-cat-night-preview.png)

预览使用示意时间和天气；设备显示北京时间、日期星期、Wi-Fi、电量和真实天气。
猫咪款日期在左、天气温度在右，并列于时间上方。两款数字表盘只显示时分，
指针款有红色秒针，1Hz更新。

## 图集与昼夜

图集使用内置imagegen绘制，源文件、提示词、SHA256与构建说明在assets/。
八帧双爪敲击，180ms更新一次340×150区域，每四个循环眨眼一次。
使用原生RGB565/RLE单个Image切换，不播放整屏视频、不同时手动预载十六帧；
切离猫咪款、后台或息屏后停止画面更新。后台不做逐帧Flash写入，诊断仅在
选择表盘、首轮成功及昼夜变化时保存。

天气优先复用天气App城市与缓存，默认上海。时钟每约10分钟直接HTTPS获取
温度、天气、is_day及未来三天sunrise/sunset/daylight_duration，按返回城市时区与
当天日出日落判断昼夜。正好日出进入白天、正好日落进入夜晚，跨午夜重新选日期；
极昼极夜使用日照时长。缺少当天太阳数据时暂用API的is_day或初始白天，并在
诊断中标明fallback来源，不使用固定的早六晚六规则。离线保留缓存；30分钟以上
天气标为过期。只读天气App的配置，不改其缓存。电池复用系统30秒缓存。

[Open-Meteo接口说明](https://open-meteo.com/en/docs)。

## 构建及部署

```powershell
python brookesia-apps/flip-clock/tools/generate_assets.py
python codex-quota-monitor/tools/package_clock_faces.py
python codex-quota-monitor/tools/deploy_clock_faces.py --port COM5
python codex-quota-monitor/tools/verify_clock_cat.py --port COM5
```

需要Pillow、Node.js及Windows Bahnschrift/微软雅黑字体；不分发字体文件。
安装包与资源放SD，固件继续s3.58。部署前检查无活动音频和未锁屏，并把旧应用
备份到SD私有resource-backups目录。其他应用、音量、家长设置不变。

## 验证与范围

2026-11-09已安装0.2.1，SD脚本/JSON文本及十六个资源大小读回通过。
单元测试覆盖原翻页午夜/分钟跳变、暂停恢复、三款切换记忆、指针坐标、
敲击生命周期/息屏停更/稳定动画无Flash写入、日出日落精确边界、跨日与并列排版。

实机通过真实上海太阳数据（当天06:15/16:59）读取、临时太阳数据驱动昼夜两套
资源切换以及三款表盘关闭重开。测试未改系统时间，临时缓存已恢复到真实天气。
14应用与60%音量保留；单次SetViewSrc调用最高约10ms，此值不等同于屏幕帧耗时。
暖机后25秒内PSRAM余量约1.49～1.57MiB、内部余量约56～60KiB、DMA最大块32KiB，
该短时检查未见持续下降；尚不能替代长期运行/所有服务并行压力验证。

新版猫咪插画仍有少量帧间几何变化，动画观感与文字布局等待用户实屏确认。
随后提出的“全屏场景、22px状态文字、底部圆点”是下一版排版预览，位于
../../design/typing-cat-v3-layout/，尚未部署，不包含在0.2.1生产布局中。
