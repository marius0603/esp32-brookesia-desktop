# 电子宠物 · 小栗

`local.virtualpet` 0.1.4 面向 ESP32-S3-Touch-AMOLED-2.16 的 480×480 方屏。黑底蓝色点阵铺满屏幕，小栗保留一对长耳朵、一撮斜鬃毛、两只眼睛和一张小嘴。

- 轻点会笑，双击会睁大眼睛并竖起耳朵。
- 长按约半秒会眯眼放松，松手后恢复。拖动时眼睛跟手，松手后回正。
- 小栗平时会偶尔眨眼，默认按北京时间 22:00 至次日 07:00 入睡。升级会继续读取已有的睡眠时段。设备尚未校时时显示日常表情。
- 从屏幕底边向上滑返回桌面。

各表情由 RGB565 点阵图层合成。表情图片随应用包发布，打开页面时预载。拖动只更新图层位置，静止时复用上一帧。

## 构建、安装与校验

构建需要 Python、Pillow 和 Node.js。部署工具使用已有的 USB 维护环境。

```powershell
python brookesia-apps/virtual-pet/tools/build_assets.py
python brookesia-apps/virtual-pet/tools/build_screen.py
python codex-quota-monitor/tools/package_virtual_pet.py
python codex-quota-monitor/tools/deploy_virtual_pet.py --port COM5
python codex-quota-monitor/tools/verify_virtual_pet.py --port COM5
```

应用包为 [0.1.4](../../packages/apps/local.virtualpet.debug.0.1.4.bpk)。部署器通过标准安装器更新 SD 上的应用，校验安装文件，并保留升级前的应用目录备份。设备之前保存的睡眠配置保存在 `/sdcard/pets/xiaoli/schedule.json`，更新时保持原文件。旧版 0.1.3 的独立资源包可用于恢复旧版。

自动校验通过 USB 打开和关闭正式应用，再短暂加载测试脚本，回放与触摸回调相同参数的动作，检查板上实际图层位置。结束时恢复发布脚本，核对整棵安装目录的哈希，并重新打开正式应用。
