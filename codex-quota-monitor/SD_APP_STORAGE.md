# SD 应用存储（s3.46）

## 边界

Flash 保留 ESP-IDF / Brookesia 固件、底层驱动与原生服务，以及基础桌面、设置、家长验证、音量、电源管理、公共字体和桌面资源回退，以及 USB 维护和固件恢复入口。家长 PIN、Wi-Fi 与关键设置仍在 NVS；不会随应用迁移复制到公开仓库。附加应用通过 SystemCore 私有存储接口读取的内部卷不可用，默认缓存、数据、文件都选择 SD，防止后续缓存回流 Flash。

听书、天气、时钟、额度、智能助手、轻学习、电子宠物、电台等附加应用的脚本与界面资源使用 `/sdcard/apps/<应用ID>`。故事仍在 `/sdcard/audiobooks/bedtime`。`brookesia.*` 基础组件及 `local.childmode` 不迁移。没有 SD 时只要求基础功能可用；附加应用不可用。重新插卡后重启加载，不支持运行中热拔卡。透明图标目录名带版本时间戳，原来的基础应用索引也曾指向 SD，桌面还强制预载宠物共享图标；s3.46 在图片解析阶段为这些路径增加 Flash 图标及占位回退，避免缺卡时基础应用登记失败。无卡时使用 Flash 保留的经典主题资源，细节可能与 SD 透明图标不同。

## 安装与更新

- USB 的 BPK 从第一字节起写入 SD 的 `/sdcard/packages/.brookesia_usb`；没有 SD 时拒绝 BPK 安装，但 USB 维护与应用分区固件更新仍可使用。应用商店的 BPK 下载也只使用 SD。
- 解包前根据 ZIP 解压尺寸、目录、原应用私有数据和跨卷备份计算所需空间（SD 按最高 512 KiB 分配单元保守估算，Flash 按 4 KiB），额外保留 SD 8 MiB、Flash 256 KiB。该检查解决安装磁盘空间不足，不代表任意大小安装包都能装入 RAM。
- 候选版本先写入 `.installing`，旧版本保留在 `.rollback/<ID>`，注册新版本成功后才提交。失败恢复旧目录与注册；安装日志保存在 `.transactions`，重启先处理未完成事务，再扫描应用。
- 跨卷迁移核对完整文件树的 SHA-256；目标、旧版本备份都校验成功后才移除旧 Flash 目录。保留一代回退副本，不自动删除其他用户目录。跨卷复制回退时另记恢复标记，重启后重做完整复制，避免把半份恢复目录误认为完成。
- SD 应用损坏时记录错误并跳过，避免阻塞基础桌面启动。SD/FAT 硬件损坏、写入断电仍可能造成文件系统损坏；事务回退不能替代卡备份。

## 现有设备迁移

先保留私有完整 Flash 备份，再用 `update_brookesia_app_only.py` 更新到 s3.46。不要执行包含 LittleFS 镜像的整机烧录。

```powershell
python codex-quota-monitor/tools/migrate_apps_to_sd.py --port COM5
```

工具要求音频空闲，保存应用清单、版本、书架和容量到忽略的 `runtime` 目录。迁移整个设备当前目录，保留已安装的图标、页面和私有数据，不用仓库旧 BPK 替换当前内容。已有同名 SD 目录会先完整保留到 `/sdcard/resource-backups/pre-sd-migration-*`。成功后对比目录哈希、版本、30 篇书架和基础组件位置，再重启确认重新登记。

无卡启动后运行 `python codex-quota-monitor/tools/verify_flash_foundation.py --port COM5`（加 `--speaker-test` 会播放短合成音并核对硬件音量，不使用麦克风或网络）；插回并重启后加 `--with-sd` 检查 13 个应用和 30 篇书架恢复。

迁移后旧工具中硬编码 `/littlefs/apps/` 的部署命令需要先查 `SystemCore.AppStorageInfo`，使用返回的实际路径；不能继续直接写旧位置。新安装走 USB `install_bpk`，由固件选择卷。

## 验证与性能

```powershell
python codex-quota-monitor/tools/verify_sd_app_storage.py --port COM5 --phase install
python codex-quota-monitor/tools/verify_sd_app_storage.py --port COM5 --phase prepare-recovery
# 重启设备后：
python codex-quota-monitor/tools/verify_sd_app_storage.py --port COM5 --phase verify-recovery
python codex-quota-monitor/tools/verify_sd_app_storage.py --port COM5 --phase cleanup
# 再重启一次，移除诊断应用的内存登记。
python codex-quota-monitor/tools/benchmark_app_storage.py --port COM5 --rounds 2 --output codex-quota-monitor/runtime/app-storage-after.json
```

诊断只使用隐藏的 `local.storage.test`，检查正常更新、私有数据保留及默认 SD 路由、空间不足/不安全路径拒绝、GUI 注册失败回退，以及重启恢复未完成事务。跨卷半恢复检查可在独立的 `install` 测试后，将 `prepare-recovery` / `verify-recovery` 换成 `prepare-cross-recovery` / `verify-cross-recovery`；该检查只在诊断应用路径制造半份 Flash 恢复目录。不得在正式应用上手工制造失败。移卡验证需关机后移除 SD，再启动检查基础桌面、设置、家长验证、音量、电源和 USB；重新插卡后再重启确认附加应用恢复。

应用打开时读取 SD，首次启动可能改变耗时；运行期间仍保留图标/壁纸 PSRAM 预载和听书 PCM 缓冲。本改造不额外增加全量应用 RAM 缓存，也不改变已有电台网络缓冲。

## 启动耗时对比

迁移前后各两轮，USB StartApp 完成并确认真实前台的中位秒数。天气含联网等待，样本量小，不能据此宣称性能提升。运行期间的帧率另需屏幕观察。

| 应用 | Flash 原位置 | SD 位置 |
| --- | ---: | ---: |
| 时钟 | 2.684 | 1.544 |
| 额度 | 1.827 | 1.941 |
| 天气 | 6.750 | 6.026 |
| 听书 | 1.652 | 1.403 |
| 电台 | 1.749 | 1.783 |
| 轻学习 | 1.449 | 1.509 |
| 宠物 | 1.302 | 1.397 |
| 智能助手 | 1.195 | 1.167 |

电台、轻学习、宠物原本已在 SD，作为同条件对照。其余五个应用本轮从 Flash 迁移。

## 本轮状态

2026-11-04：五个原 Flash 应用已迁移并逐树校验，13 个应用版本、30 篇故事保留。Flash 文件区可用 1,441,792 字节（1.375 MiB），迁移前本轮为 20,480 字节。安装空间预检、路径拒绝、注册失败回退、默认 SD 私有数据路由、未提交更新重启恢复及跨卷半恢复检查通过。

无卡实际暴露并修复基础透明图标和全局宠物图标依赖：仅五个基础组件登记，USB维护/缺卡安装拒绝正常；真实合成音的10/40/0硬件增益检查通过。用户已确认无卡桌面、设置及原PIN正常；20秒定时深睡唤醒后返回桌面通过；插回后13个应用与30篇故事恢复，最终固件八应用打开复测通过。三篇故事解码和一篇20秒连续输出通过，原音量/书签恢复。十份补丁还原58个上游文件并与实际构建目录一致。
