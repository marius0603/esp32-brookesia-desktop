# 工作完成后的微信简报

用户授权每完成一项功能或App、验证并同步GitHub后，向本人绑定的微信发送一条中文简报：完成内容、验证结论、待确认事项和提交链接。普通问答与中间日志不逐条推送。

使用腾讯官方`@tencent-weixin/openclaw-weixin`插件和本机OpenClaw，通过直接消息发送，无需另一次模型调用。电脑需联网；登录失效或微信拒收时仍可能失败，不保证永久绑定或无限量发送。不得自动购买套餐。

本机升级采用独立Node.js/OpenClaw目录，旧配置已备份，账号凭证留在用户OpenClaw目录。默认私有配置在仓库外`../private/openclaw-binding/brief-config.json`：`node`、`cli`为绝对执行路径，`channel`为`openclaw-weixin`，`account`和`target`为已扫码绑定的账号/接收者。这些值及二维码、日志、发送账本均不得提交。另一台电脑需自行安装、绑定并配置，不能只克隆仓库即获得微信授权。

正文先写到本地runtime文件，避免命令行转义损坏。示例（项目根目录）：

```powershell
python tools/wechat_brief.py --body-file codex-quota-monitor/runtime/work-brief.txt --id <已推送的完整提交SHA> --dry-run
python tools/wechat_brief.py --body-file codex-quota-monitor/runtime/work-brief.txt --id <已推送的完整提交SHA>
```

工具必须读取平台`payload.deliveryStatus=sent`才确认成功，不能仅凭CLI退出码。相同工作ID不会自动重发；请求前先记录未确认状态，超时或进程中断时避免重复发送，应先现场检查微信再决定是否用新的ID重发。发送状态本地保存，不保存正文，不自动重试。

2026-11-16本机验证：扫码凭证保存、微信通道运行，用户发送“测试”后收到直接测试回复。初次尚无会话上下文时发送被拒绝；不将绑定成功等同所有情况下均可主动推送。OpenClaw默认模型未登录曾返回AI服务错误，直接发送工具不依赖此模型。

## Codex对话接入与当前验证范围

本机另外安装`@openclaw/codex@2026.11.3`，默认模型为`openai/gpt-6.1-sol`、模型运行时固定`codex`，备用模型列表为空。`plugins.entries.codex.config.appServer.homeScope="user"`显式复用本机Codex的ChatGPT登录，不复制登录密钥进仓库；程序路径使用本机Codex可执行文件。设置`approvalPolicy="on-request"`、`sandbox="workspace-write"`，工作区为本项目，关闭原生会话目录浏览。该对话接入会消耗现有Codex额度，不代表免费无限调用。

微信收到消息后由OpenClaw会话调用Codex，不是自动续接当前Codex桌面对话。项目上下文以本仓库文档和AGENTS.md为准，不同时发起相互冲突的修改。OpenClaw生成的本机IDENTITY.md、SOUL.md、USER.md通过本地Git排除规则保留，不提交个人资料。

该电脑目前直连模型服务超时，通过已有本机代理可访问。网关需使用可用的HTTPS代理，并保留localhost/微信服务的合适直连规则；代理地址是本机部署条件，不是其他电脑的通用设置。Tailscale未安装，本次网关以`--tailscale off`启动；前台启动窗口需要保持打开，没有为此添加系统自启动。

曾出现模型未登录、模型列表请求超时以及微信端DNS/请求超时，不能仅凭扫码或网关running认定对话可用。后续已核对网关与原生Codex子进程均继承本机代理；独立app-server账号读取及8个模型列表约3秒内返回。通过OpenClaw调用gpt-6.1-sol的文字诊断约19.4秒完成，实际返回“连接成功”，状态ok。微信真实消息→Codex→微信完整往返仍待现场复测，暂不保证长期稳定。

官方流程：https://github.com/Tencent/openclaw-weixin
