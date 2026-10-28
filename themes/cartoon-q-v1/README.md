# Q 版主题 cartoon-q-v1

资源来自用户提供的 `cartoon-q-v1.zip`；九枚 96×96 图标、480×480 壁纸及 486×486 RLE 壁纸原图保持原样，`source/` 保存较大源图，`preview.png` 可预览。本次直接使用这些现成素材，仅为回退图标调整尺寸和色数。

固件 s3.21 从 `/sdcard/themes/cartoon-q-v1/` 读取全彩图标与壁纸，保留 `/littlefs/themes/cream-handdrawn-v1/` 作为兼容的 Flash 资源槽位。该旧目录名是已有资源引用路径，内容部署后是新的 Q 版；不用迁移应用程序或家长数据。

`flash-fallback/` 是相同图案的 64×64、96 色压缩副本，九枚合计约 19.5 KB，SD 不可用时使用。可重新导出：

```powershell
python tools/build_theme_fallbacks.py --theme themes/cartoon-q-v1 --size 64 --colors 96
```

已有设备先烧录 s3.21，再运行 `codex-quota-monitor/tools/deploy_cartoon_theme.py --repo <仓库目录>`。工具逐个备份文件到 SD、校验传输、更换图标索引与桌面颜色，最后需重启清除预加载和图片缓存。壁纸沿用整屏 RLE 合成和每分钟 ±3 像素微移。部署不会更改家长 PIN、应用白名单、网络或时段设置。

当前s3.30设备已采用用户确认的流畅桌面，保留原壁纸：`launcher-optimized/`保留这九枚Q版图案并加入轻学习图标，统一预处理为92×92 RGB565/RLE，合成暖白图标底色，布局不在滑动时缩放或混合透明图标。原始PNG与壁纸继续保留。安装、恢复及实测记录见[手机式桌面说明](../../codex-quota-monitor/PHONE_LAUNCHER.md)。
