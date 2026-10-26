# 本机离线语音资源

- `models.json`：官方 ESP-SR 2.4.5 中六个模型文件的版本、大小和 SHA-256；使用固定组件依赖重建，不重复分发模型二进制。
- `prompts/remaining-00.pcm`：尚未设置睡眠定时；01–45 为剩余分钟；46 为不到一分钟。
- `diagnostic/test-01.pcm`–`test-08.pcm`：本机合成的唤醒词与八条命令，用来验证数字推理，不代表真实童声效果；09–11 为吃苹果、天气和数数等无关语句。
- `audio.json`：PCM 格式、来源、每个数字测试文件实际使用的句子和文件哈希。

提示及数字测试语音使用当前中文 Windows 已安装的 Microsoft Huihui Desktop 离线合成（Rate -2、Volume 75）。没有将孩子录音或任何实录语音放入仓库。重建脚本为 `tools/build_offline_voice_prompts.ps1`。

这些资产部署到 `/sdcard/offline-voice/`；运行时不需要 Wi-Fi。详细操作和限制见 `codex-quota-monitor/OFFLINE_VOICE.md`。
