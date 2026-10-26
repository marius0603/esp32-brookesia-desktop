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

二进制帧：`VPC1`四字节、uint32 little-endian turn、uint32 little-endian sequence、至多1920字节 PCM。电脑发送窗口最多12片，设备播放后确认；设备环形缓冲32片，网络回调只做组包和复制，音频写入由内部栈工作任务执行。云服务密钥不会发送到设备，设备仅保存配对令牌及入口。

## 设备与检查

需要固件 s3.24 和智能助手0.2.0，新增 `LocalVoice` 服务。保留 `VoiceAssistant` 小智模式、音量上限、勿扰、儿童授权、听书互斥和本地录音回放。

```powershell
python -m unittest discover -s pc-voice-bridge/tests -v
node brookesia-apps/voice-assistant/tests/main.test.cjs
```

`tests/pc_voice_protocol_static.cpp` 检查分片边界、字节序及旧轮次。真实公网、模型与设备验证记录保留在私有运行目录；这些样本测试不等同于所有童声、口音或噪声环境的准确率。

上游：[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)、[Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR)、[Cloudflare 临时隧道限制](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)。
