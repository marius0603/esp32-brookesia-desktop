# 本机模型与设备语音助手

设备录音 → 本机 Qwen3-ASR → 用户配置的 OpenAI 兼容云服务 → 本机 Qwen3-TTS → 设备播放。

运行目录独立放在 `G:\codex_data\qwen-speech`；此目录仅维护可复用源码。模型、Python 环境、API 密钥、配对令牌、输出和运行日志不进入仓库。

## 电脑端

已有 Qwen 模型和环境安装完成后，运行：

```powershell
python pc-voice-bridge/deploy.py --target G:\codex_data\qwen-speech
```

在运行目录重启工作台，打开 `http://127.0.0.1:7860/assistant`。云服务地址、模型名称、声音与 API 密钥在本机页面配置。API 密钥使用 Windows 当前用户 DPAPI 加密保存，接口仅返回是否已配置。

两个模型分别保留各自环境，通过有序 JSON 管道常驻运行，GPU 操作串行调度。按句合成，单句最多48字。已取消的任务丢弃后续音频和回答，未完成的回答不加入对话历史；只发送识别文字及有限历史到云端。默认关闭模型深度思考，使用流式正文。

## 跨网络连接

设备与电脑不需要在同一局域网。当前验证方式为电脑主动建立 Cloudflare 公网隧道，设备连接公网 `wss://…/device`，由 ESP-IDF 证书包校验服务器证书；公网连接仍需设备配对令牌。电脑端网关仅监听回环地址，不开放本机入站端口。

临时隧道仅用于验证：没有可用性保证，电脑重启或隧道重建后主机名会变化，需要通过 USB 更新设备连接地址。日常使用应配置固定公网入口或固定域名的隧道。维持现有隧道进程时，重启模型工作台会复用该入口。

公网隧道只承载音频和控制消息；原始录音不发送到文本模型接口。设备对话录音在电脑内存中转写，网页主动上传的录音和生成文件保存在本机 outputs。电脑和设备均需联网，电脑工作台需运行。

## 音频协议

首个 JSON 消息为 `hello`，携带配对令牌和16kHz/16位/单声道格式。控制消息带本连接内递增的32位 turn ID。

| 消息 | 方向 | 用途 |
| --- | --- | --- |
| listen_start / listen_end | 设备→电脑 | 开始、提交最长30秒录音 |
| user_text / answer / status | 电脑→设备 | 转写、回答字幕与阶段 |
| audio_start / audio_end / done | 电脑→设备 | 音频和本轮完成标记 |
| played | 设备→电脑 | 确认已写入播放器的分片序号 |
| cancel | 设备→电脑 | 停止当前回答，后续数据按 turn ID 丢弃 |

二进制帧：`VPC1`四字节、uint32 little-endian turn、uint32 little-endian sequence、至多1920字节 PCM。电脑发送窗口最多256片，设备播放后合并确认最新进度；设备环形缓冲384片（约725KiB）。每句语音收齐后开始播放，超过256片的长句则以约15.36秒预缓冲开始流式播放；切换到下一句时重新检查该句是否已收齐，避免沿用上一句的播放状态而提前播出半句。网络回调只组包和复制，PCM写入由内部栈工作任务执行，确认由独立内部栈任务发送，网络等待不会阻塞音频写入。云服务密钥不会发送到设备，设备仅保存配对令牌及入口。

固件必须启用官方 WebSocket 组件的 `CONFIG_ESP_WS_CLIENT_SEPARATE_TX_LOCK=y`，避免接收占锁时播放确认发送超时；已写入 S3 配置及可复现配置，固件包清单也记录该开关。仅延长发送等待不能消除双向传输的锁冲突。

## 设备与检查

需要固件 s3.24 和智能助手0.2.0，新增 `LocalVoice` 服务。保留 `VoiceAssistant` 小智模式、音量上限、勿扰、儿童授权、听书互斥和本地录音回放。

先按既有备份及应用分区更新流程安装 s3.24。电脑工作台启动、设备连接 Wi-Fi 后，通过 USB 安装配对的助手：

```powershell
codex-quota-monitor/.venv/Scripts/python.exe codex-quota-monitor/tools/deploy_pc_voice.py --port COM3 --model-root G:/codex_data/qwen-speech
```

端口按实际设备调整，不要同时运行占用串口的额度采集器。安装工具备份原助手到 SD，安装0.2.0并同步电脑公网地址及独立配对令牌；核对助手启动和故事列表保持一致。设备点“说话”，说完再次点“发送”；点“取消”打断回答，点击“电脑 + DS · 切换”可使用原小智服务。

临时隧道地址变化后，仅更新配对，不重装应用：

```powershell
codex-quota-monitor/.venv/Scripts/python.exe codex-quota-monitor/tools/pair_pc_voice.py --port COM3 --model-root G:/codex_data/qwen-speech
```

如果网页提示临时入口失效，先显式重建，再执行上面的 USB 配对命令：

```powershell
G:/codex_data/qwen-speech/envs/tts/Scripts/python.exe pc-voice-bridge/restart_public_tunnel.py --target G:/codex_data/qwen-speech
```

配对需要 USB 接触设备，因此当前临时入口不适合设备长期放在异地、电脑经常重启的场景。固定入口配置完成前请保留这一限制。云服务地址若使用 HTTP，该段请求不加密；公网设备音频通道使用 WSS。

下行检查会暂时静音，调用真实云服务及 TTS，通过设备播放计数确认音频写入，并要求播放期间未重连、同一句内相邻写入间隔小于250ms，然后恢复原音量；不打开麦克风，现场听感仍需单独确认：

```powershell
codex-quota-monitor/.venv/Scripts/python.exe codex-quota-monitor/tools/verify_pc_voice.py --port COM3
```

```powershell
python -m unittest discover -s pc-voice-bridge/tests -v
node brookesia-apps/voice-assistant/tests/main.test.cjs
```

`tests/pc_voice_protocol_static.cpp` 检查分片边界、字节序及旧轮次。真实公网、模型与设备验证记录保留在私有运行目录；这些样本测试不等同于所有童声、口音或噪声环境的准确率。

2026-10-26 验证：两个模型同时常驻 GPU；本机生成音频转写与预期一致，模拟设备完成公网录音上传、云端回答及播放确认。实机 s3.24 应用分区读回校验通过，助手0.2.0运行，10篇故事保留；真实公网回答“语音助手连接成功。”生成31片、59,520字节PCM，设备播放完后回到 Ready、连接保持正常，静音验证后音量恢复。此检查未打开设备麦克风，现场录音与听感另行确认。

2026-10-27 连续播放验证：独立收发锁及整句缓冲版本实机读回校验通过，公网测试完成49,280字节PCM播放，同句最大写入间隔65ms，测试轮次未发生重连；音量恢复到70%，10篇故事保留，助手连接时剩余PSRAM约2.5MB。另一次采样显示收包暂停且缓存耗尽时播放停顿，支持重点排查已合成音频的下传/接收节奏；尚未精确区分公网与设备接收调度的耗时。现场长回答听感仍需单独确认。

上游：[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)、[Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR)、[Cloudflare 临时隧道限制](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)。
