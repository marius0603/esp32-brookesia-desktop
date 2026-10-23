# 离线晚安语音

`goodnight_pcm.inc` 是这台 Windows 上的 Microsoft Huihui Desktop 中文合成语音，文字为“晚安”，16 kHz 单声道 signed 16-bit PCM，约 1.05 秒。使用本机语音库生成，不依赖在线模型或密钥。固件以四分之一数字增益播报，并在两端加入短包络；保留系统音量、儿童上限与勿扰控制。

生成参数与原创示例故事一致，见 `tools/synthesize_mandarin.ps1`，Rate=-2、Volume=75。转换为整数数组时裁掉首尾静音，保留开头 50 ms、结尾 100 ms。语音库版本不同可能产生不同样本，仓库保留当前发布所用数据。
