# 口袋鱼缸

微雪 ESP32-S3-Touch-AMOLED-2.16 上的 Brookesia 独立应用。首版为 480×480 像素鱼缸，包含金鳞、月影和四条蓝线鱼。

- 点水面产生水纹。金鳞会靠过来，蓝线鱼会结伴转向，附近的月影会游开。
- 点击鱼或右下角的「鱼册」查看鱼种和习性。
- 点击左上角的日景或夜景切换水景。夜景游速更慢，重新进入时会恢复上次选择。
- 从屏幕底边上滑回桌面。退出后暂停鱼缸绘制。

游动和触摸响应由本地规则驱动，可以离线使用。首版尚未接入端侧模型。

## 构建和安装

在仓库根目录运行以下命令。资源构建使用 Pillow，打包前会通过 Node.js 检查上述交互和定时器生命周期。

```powershell
python brookesia-apps/aquarium/tools/build_resources.py
python codex-quota-monitor/tools/package_aquarium.py
python codex-quota-monitor/tools/deploy_aquarium.py --port COM5
```

用设备的实际串口替换 `COM5`。BPK 通过现有安装器写入 SD，无需重刷固件。已在 `0.8.3-s3.92` 上验证。日夜偏好保存在 `/littlefs/aquarium-settings.json`。
