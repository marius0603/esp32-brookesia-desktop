# 奶油手绘桌面主题

8 个启动图标（96×96 RGBA PNG）和桌面背景（480×480 JPEG），由内置 image_gen 生成设计原图，再按设备尺寸导出。图标覆盖设置、文件、应用商店、额度、天气、听书、翻页时钟和智能助手。
原图约 141KiB，另附约 87KiB 的 486×486 RGB565/RLE 原生壁纸，供 s3.16 的微移和快速切换使用；无需每次绘制 JPEG 或实时缩放。

部署仅调整 LittleFS 中的图片描述与 Shell 样式，不修改固件、应用代码、NVS 或应用私有数据。旧图片保留，新图片放在 `/littlefs/themes/cream-handdrawn-v1/`。Shell 使用浅色背景与深色标题，其他应用保持原界面。

先停止占用串口的额度采集器，使用已安装本项目依赖的 Python：

```powershell
./codex-quota-monitor/stop.ps1
# 等待采集器退出后执行
python ./codex-quota-monitor/tools/apply_desktop_theme.py ./themes/cream-handdrawn-v1 --port COM5
```

工具验证图片 SHA-256、屏幕分辨率、应用清单和剩余空间，将替换前的 JSON 保存到 `codex-quota-monitor/runtime/theme-backup-日期时间/`，完成图片上传后才切换引用，最后更新 Shell root。USB 上传仍限制在 `/littlefs/usb/`，随后通过 Storage 移动已校验文件，不放宽上传边界。

完成后重启设备，再启动采集器。无需重新烧录固件。

回滚：停止采集器，执行以下命令，再重启设备：

```powershell
python ./codex-quota-monitor/tools/apply_desktop_theme.py --restore ./codex-quota-monitor/runtime/theme-backup-日期时间 --port COM5
```

回滚恢复原 JSON 引用；新主题图片保留在独立目录中，不删除任何原图片。重新安装某个应用或重置系统资源可能覆盖主题引用，此时可重新运行主题部署工具。

重新导出原图时可运行 `tools/build_desktop_theme.py --source 原图目录`。设备部署只需要本目录中的成品资源与 theme.json。

设备检查工具：`codex-quota-monitor/tools/verify_desktop_theme.py`。本次验证发现原生应用商店通过 USB 请求关闭时会超时；它能正常启动，但该关闭路径尚未修复。可加 `--skip-app-store` 检查其余应用，并在报告中保留此限制。智能助手在重启后连续 8 次启动通过，实体触摸打开也已确认恢复，未因此修改语音固件。
