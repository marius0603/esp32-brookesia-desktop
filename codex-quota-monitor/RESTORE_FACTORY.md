# 恢复原出厂系统

2026-10-18 用户明确允许替换出厂系统。已在写入前完成板上全部 16 MiB Flash 备份，并与开发板端整片 MD5 比对成功；本地 SHA-256 记录在备份 manifest.json 中。

有效备份目录记录在 runtime/verified-backup-path.txt。此次目录为 runtime/backups/20261018-120736-44bd8d789fd8/，内含 factory-full-16MB.bin、manifest.json、progress.json。早前未完成的读取不作为恢复依据。

备份包含原有分区、固件、资源和当时的设备配置，可能含设备凭据，请保留在本机，勿公开或放入发布包。它不包含无法通过 Flash 备份恢复的 eFuse；此次烧录没有修改 eFuse。

仅当需要恢复原 AIChats、Settings、MusicPlayer 等出厂应用时执行以下步骤；当前独立额度程序及其设置会被恢复镜像覆盖。

1. 在本项目目录执行 .\stop.ps1，等待电脑端采集服务退出并释放串口。
2. 使用同一块开发板，确认真实 COM 口。
3. 执行下面命令。脚本会先校验完整备份的 SHA-256 和设备 MAC，再恢复整片 Flash；不需要先执行整片擦除。

~~~powershell
.\tools\idf-tools\python_env\idf5.5_py3.12_env\Scripts\python.exe tools/restore_factory.py --port COM5
~~~

4. 等待写入及校验完成后重新上电，核对原有桌面和设备配置。必要时使用 BOOT 进入下载模式。

恢复脚本已准备，尚未执行恢复；当前运行的是独立额度固件 0.3.0。
