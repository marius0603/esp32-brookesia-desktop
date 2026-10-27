# 本机模型与设备语音助手

设备录音 → 本机 Qwen3-ASR → 用户配置的 OpenAI 兼容云服务 → 本机 Qwen3-TTS → 设备播放。

运行目录独立放在 `G:\codex_data\qwen-speech`；此目录仅维护可复用源码。模型、Python 环境、API 密钥、配对令牌、输出和运行日志不进入仓库。

## 电脑端

已有 Qwen 模型和环境安装完成后，运行：

```powershell
python pc-voice-bridge/deploy.py --target G:\codex_data\qwen-speech
```

在运行目录重启工作台，打开 `http://127.0.0.1:7860/assistant`。云服务地址、模型名称、声音与 API 密钥在本机页面配置。API 密钥使用 Windows 当前用户 DPAPI 加密保存，接口仅返回是否已配置。

选择公网中转方式后重启工作台：

```powershell
python pc-voice-bridge/configure_public_tunnel.py --target G:/codex_data/qwen-speech --provider localhost-run
```

当前设备验证使用 Windows 自带OpenSSH建立 localhost.run 加密中转，无需向中转提供本机SSH身份密钥；主机公钥存入运行目录专用known-hosts文件。可选 `--provider cloudflare` 使用已安装的 cloudflared；本次该入口在电脑可达而设备TLS连接持续超时，因此改用备用入口。不同网络需以设备实际连通与完整播放测试为准。

两个模型分别保留各自环境，通过有序 JSON 管道常驻运行，GPU 操作串行调度。按句合成，单句最多48字。已取消的任务丢弃后续音频和回答，未完成的回答不加入对话历史；只发送识别文字及有限历史到云端。默认关闭模型深度思考，使用流式正文。

## 跨网络连接

设备与电脑不需要在同一局域网。电脑主动建立公网加密中转，设备连接公网 `wss://…/device`，由 ESP-IDF 证书包校验服务器证书；公网连接仍需设备配对令牌。电脑端网关仅监听回环地址，不开放本机入站端口。

临时入口没有长期可用性保证。免费中转域名可能变化，电脑重启或中转进程退出后重建也可能产生新域名，需要通过USB更新设备地址。日常异地使用应配置固定公网入口或固定域名。仍在运行且身份匹配的中转进程会复用；后台进程已退出则重新创建，并在本机页面提示地址变化。

公网隧道只承载音频和控制消息；原始录音不发送到文本模型接口。设备先在PSRAM连续录制最多30秒，再上传电脑内存转写，避免网络发送阻塞麦克风读取；默认不保存设备录音。网页主动上传的录音和生成文件保存在本机 outputs。电脑和设备均需联网，电脑工作台需运行。

## 音频协议

首个JSON消息为 `hello`，携带配对令牌、16kHz/16位/单声道解码格式及 `encoding=ima_adpcm`。电脑返回相同编码后设备才进入就绪，避免连接到未更新的电脑服务。控制消息带本连接内递增的32位turn ID。旧设备可协商 `pcm_s16le` 兼容格式。

| 消息 | 方向 | 用途 |
| --- | --- | --- |
| listen_start / listen_end | 设备→电脑 | 开始上传、完成提交已缓存的最长30秒录音 |
| user_text / answer / status | 电脑→设备 | 转写、回答字幕与阶段 |
| audio_start / audio_end / done | 电脑→设备 | 音频和本轮完成标记 |
| played | 设备→电脑 | 确认已写入播放器的分片序号 |
| cancel | 设备→电脑 | 停止当前回答，后续数据按 turn ID 丢弃 |

二进制帧：`VPC1`四字节、uint32 little-endian turn、uint32 little-endian sequence、至多1920字节 PCM。电脑发送窗口最多256片，设备播放后合并确认最新进度；设备环形缓冲384片（约725KiB）。每句语音收齐后开始播放，超过256片的长句则以约15.36秒预缓冲开始流式播放；切换到下一句时重新检查该句是否已收齐，避免沿用上一句的播放状态而提前播出半句。网络回调只组包和复制，PCM写入由内部栈工作任务执行，确认由独立内部栈任务发送，网络等待不会阻塞音频写入。云服务密钥不会发送到设备，设备仅保存配对令牌及入口。

当前上下行优先采用 `VPA1`：保留相同turn/sequence头，追加int16初始预测值、uint8步长索引、uint16样本数及4位IMA/DVI ADPCM。每片最多960个样本，携带独立解码状态；恢复成16位PCM后送入ASR或I2S。语音任务内部栈为8KiB、确认任务为4KiB；状态提供内部空闲内存和最大DMA连续块，避免仅看PSRAM余量而漏掉显示刷新所需的内部内存。公网连接及单次写入等待15秒，电脑心跳超时60秒。

编码器使用独立C++实现，测试向量对照CPython 3.12的 [audioop接口](https://docs.python.org/3.12/library/audioop.html)。电脑运行时固定Python 3.12；该标准库模块在Python 3.13移除，升级运行时前需替换编码实现。一次4.26秒实际录音由136,320字节PCM变为35,287字节应用层传输数据，约减少74%；压缩解码后的ASR结果仍为“小猫今天去找朋友了。”。

固件必须启用官方 WebSocket 组件的 `CONFIG_ESP_WS_CLIENT_SEPARATE_TX_LOCK=y`，避免接收占锁时播放确认发送超时；已写入 S3 配置及可复现配置，固件包清单也记录该开关。仅延长发送等待不能消除双向传输的锁冲突。

## 设备与检查

需要固件 s3.25 和智能助手0.2.1。`LocalVoice` 使用最多960,000字节PSRAM录音缓冲，采集期间不执行网络发送；提交后显示上传状态，上传可取消。连接期间关闭Wi-Fi调制解调器省电，断开后恢复原策略。状态同时提供实际录音时长、录音经过时间、最大采集间隔、上传耗时和Wi-Fi信号指标。保留 `VoiceAssistant` 小智模式、音量上限、勿扰、儿童授权、听书互斥和本地录音回放。

先按既有备份及应用分区更新流程安装 s3.25。电脑工作台启动、设备连接 Wi-Fi 后，通过 USB 安装配对的助手：

```powershell
codex-quota-monitor/.venv/Scripts/python.exe codex-quota-monitor/tools/deploy_pc_voice.py --port COM3 --model-root G:/codex_data/qwen-speech
```

端口按实际设备调整，不要同时运行占用串口的额度采集器。安装工具按 `versions.json` 选择对应助手包及固件，备份原助手到 SD，同步电脑公网地址及独立配对令牌；核对助手启动和故事列表保持一致。设备点“说话”，等待按钮显示“发送”后再说话，说完再次点“发送”；点“取消”打断回答，点击“电脑 + DS · 切换”可使用原小智服务。

SSH启动会先输出管理页和文档链接，只有带 `tunneled with tls termination` 的分配声明才作为设备入口；解析时剥离ANSI控制序列。2026-10-27已修复提前误选管理页地址的问题，加入分段启动横幅及多次分配的检查；真实公网WebSocket握手与设备就绪验证通过。

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

`tests/pc_voice_protocol_static.cpp` 检查分片边界、字节序及旧轮次；`tests/pc_voice_adpcm_static.cpp` 对照独立CPython参考向量检查编码字节、解码样本及压缩分片边界。真实公网、模型与设备验证记录保留在私有运行目录；这些样本测试不等同于所有童声、口音或噪声环境的准确率。

诊断识别问题时，可显式开启仅下一段录音的本机留存，记录识别输入PCM的WAV及削顶比例、音量等指标；使用压缩传输时留存的是解码后的音频。采集一次后自动关闭，默认不保存：

```powershell
python pc-voice-bridge/arm_diagnostic.py --target G:/codex_data/qwen-speech
# 取消尚未发生的留存
python pc-voice-bridge/arm_diagnostic.py --target G:/codex_data/qwen-speech --cancel
```

诊断文件只写入运行目录 `outputs/diagnostics`，不得进入Git。现场曾收到仅0.6秒的短录音，识别结果无法覆盖指定整句；s3.25将连续采集和上传分开处理，最终3.84秒录音与3.842秒实际经过时间相符。

2026-10-26 验证：两个模型同时常驻 GPU；本机生成音频转写与预期一致，模拟设备完成公网录音上传、云端回答及播放确认。实机 s3.24 应用分区读回校验通过，助手0.2.0运行，10篇故事保留；真实公网回答“语音助手连接成功。”生成31片、59,520字节PCM，设备播放完后回到 Ready、连接保持正常，静音验证后音量恢复。此检查未打开设备麦克风，现场录音与听感另行确认。

2026-10-27 最终s3.25验证：应用分区读回校验、17项电脑端测试和C++协议/编码检查通过。设备经备用公网入口使用ADPCM，3.84秒真实录音的122,880字节PCM以31,808字节传输（约25.9%），上传4.446秒；识别“小猫今天出去找朋友。”，DS返回后设备完整播放72,320字节解码音频。接收与播放计数匹配，同句最大写入间隔64ms、对话轮次未重连；用户明确确认实际听到完整回答。助手运行无错误，10篇故事和90%音量保留，内部内存最低观测36,447字节、最大DMA连续块31,744字节。该结果是一次真实网络样本，不保证免费中转或其他网络的长期可用性。

上游：[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)、[Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR)、[localhost.run免费入口限制](https://localhost.run/docs/forever-free/)、[Cloudflare临时隧道限制](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)。
