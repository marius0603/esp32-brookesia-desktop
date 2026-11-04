# 构建依赖与补丁

本仓库提供源码、十份上游补丁、固定下载清单、重建脚本、已发布安装包，以及原安卓签名的加密备份。工具链、下载缓存、明文签名、加密密码、账号凭据、运行日志、完整Flash备份和下载录音继续保存在仓库外。

| 内容 | 仓库位置 / 恢复入口 |
| --- | --- |
| 上游提交、固件、应用、30篇书库及20首儿歌版本 | `versions.json` |
| ESP-Brookesia十份适配补丁 | `patches/`，按`tools/build-inputs.json`顺序应用 |
| 固件源码覆盖层与完整配置 | `platform/super_s3_216/`、`sdkconfig.reproducible` |
| 上游重建及补丁验证 | `tools/prepare_workspace.py`、`tools/check_patch_chain.py` |
| ESP-IDF工具链准备 | `codex-quota-monitor/tools/bootstrap_idf6.py`，详见主README |
| 安卓JDK / Android平台与工具 / Bouncy Castle | `phone-remote/tools/downloads.json`固定地址与SHA256，使用`bootstrap_android.py`下载到外部目录 |
| 签名备份与恢复 | [加密签名说明](phone-remote/signing/README.md)；加密依赖固定于`requirements-signing.txt` |
| USB通信依赖 | `codex-quota-monitor/requirements.txt`及仓库自带`vendor-source/brookesia-usb`源码 |
| 已发布安装包校验 | `packages/SHA256.json` |
| 故事来源及音频重建 | `samples/stories/library-20261101.json`、`samples/stories/library-20261103.json`、[书库说明](codex-quota-monitor/STORY_LIBRARY.md)；录音不入Git |

| 儿歌曲库与播放器 | `brookesia-apps/nursery-songs/README.md`；20首曲目及来源、原始/成品哈希、响度为`samples/songs/library-20261104.json`；准备/部署/验证工具在`codex-quota-monitor/tools`，录音不入Git |

## 在新电脑继续

1. 克隆本仓库。若使用稀疏检出，确保包含`phone-remote`、`patches`、`platform`、`tools`、`codex-quota-monitor`及需要的`packages`目录。
2. 应用层开发按主README安装Python/Node依赖；安卓工具用下载脚本准备。继续更新现有手机应用前先恢复原签名。
3. 固件开发使用`python tools/prepare_workspace.py`恢复固定上游与十份补丁，再按主README准备ESP-IDF和编译。
4. 已有其他上游修改时不要直接覆盖；重建脚本遇到内容差异会停止，先核对修改。设备更新仍需本地私有备份，不能把出厂完整Flash参数直接用于已有设备。

2026-11-04验证：新增SD应用存储补丁后，十份补丁按顺序应用成功，共还原58份上游源码，且与实际固件构建目录逐文件一致。此前签名解密和使用恢复签名重新构建安卓APK通过。`tools/build-inputs.json`记录公开输入文件的SHA256，便于换电脑核对。
