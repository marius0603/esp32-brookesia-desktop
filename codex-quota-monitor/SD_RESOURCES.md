当前 s3.21 使用 `cartoon-q-v1` 九枚图标与壁纸，更新请使用 `tools/deploy_cartoon_theme.py --repo <仓库目录>`，见仓库 `themes/cartoon-q-v1/README.md`。下文为 s3.20 及之前奶油主题的迁移流程，勿用其旧主题提交步骤覆盖当前 Q 版回退图标。

# SD 卡资源分层

系统固件、应用 JS/JSON、基础字库、儿童模式及 PIN 保存在内部 Flash。
书籍音频位于 `/sdcard/audiobooks`。
可选主题图标和壁纸从 `/sdcard/themes/cream-handdrawn-v1` 优先加载。

内部保留一份小壁纸，以及八个同风格的精简 PNG 图标（总计约 23KB）作为缺卡回退。
SD 卡资源暂时不可用时也不会切回原先的文字图标。“儿童模式”的图标与页面仍在 Flash。
这会释放文件系统空间，不会扩展 ESP32 的 RAM，也不代表长期运行卡顿已经消除。

固件 s3.11 的图像资源解析钩子在选择 SD 文件前检查其存在性；
所有 Flash 元数据访问复用 Storage 服务的内部栈任务。
所选路径可通过 `SdResources.GetState` 查看。
桌面已加载的图片会缓存，插拔卡或更新 SD 资源后建议重新启动。
SD 文件不存在时可以回退；存在但损坏的图片仍需从备份恢复。

停止电脑端额度同步后，在 `codex-quota-monitor` 目录执行：

```powershell
.venv\Scripts\python.exe tools/migrate_theme_to_sd.py stage --theme ..\themes\cream-handdrawn-v1 --port COM5
# 重启支持 SD 资源的固件，检查桌面。
.venv\Scripts\python.exe tools/migrate_theme_to_sd.py commit --fallbacks ..\themes\cream-handdrawn-v1\flash-fallback --port COM5
```

stage 先复制九个资源到 SD，并在 `/sdcard/resource-backups/<时间>` 保存独立备份；
commit 需确认实际 GUI 已使用 SD，再把八个内部图标替换为精简版，不递归删除目录。
精简版由仓库根目录的 `tools/build_theme_fallbacks.py` 从原主题导出，保持 96×96 尺寸。
部署记录在私有 `runtime/sd-theme-migration.json`。
恢复内部副本：

```powershell
.venv\Scripts\python.exe tools/migrate_theme_to_sd.py restore --port COM5
```

迁移后重新应用旧版主题安装脚本会再次写入 Flash 图标，需重新同步 SD 副本。
大音频及未来新增的大图片优先使用 SD，新增应用的程序与必要控制界面继续留在 Flash。

2026-10-21 实机检查：暂时重命名 SD 主题目录后重启，八个图标均由精简 Flash PNG
加载，壁纸由内部副本加载，GUI 记录八次 Flash 资源解析，家长 PIN 保留。
随后已恢复 SD 主题目录。此检查模拟资源不存在，未进行物理拔卡。

s3.13 同时修复了图标索引发现：启动时先直接读取 `res/images/index.json`，
匹配图标 ID 成功后立即使用；非标准布局才使用原有目录扫描。
此前天气资源目录的 FSList 超过 5000ms，导致 manifest 的 icon_path 为空、
桌面显示首字“天”。仅验证图片文件存在无法发现此故障；启动回归必须在打开
天气 App 之前，检查其 icon_path 非空及实际图标资源已注册。

实机 s3.13 连续两次重启检查通过：天气保持 Installed（未打开），icon_path 为
`res/images/index.json`，九个可见应用均有图标路径，SD 图标解析计数为 8，
启动日志无图标扫描超时。用户确认桌面手绘天气图标显示正常。
