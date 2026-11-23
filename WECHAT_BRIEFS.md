# 工作完成后的微信简报

用户授权每完成一项功能或App、验证并同步GitHub后，向本人绑定的微信发送一条中文简报：完成内容、验证结论、待确认事项和提交链接。普通问答与中间日志不逐条推送。

使用腾讯官方`@tencent-weixin/openclaw-weixin`插件和本机OpenClaw，通过直接消息发送，无需另一次模型调用。电脑需联网；登录失效或微信拒收时仍可能失败，不保证永久绑定或无限量发送。不得自动购买套餐。

本机升级采用独立Node.js/OpenClaw目录，旧配置已备份，账号凭证留在用户OpenClaw目录。默认私有配置在仓库外`../private/openclaw-binding/brief-config.json`：`node`、`cli`为绝对执行路径，`channel`为`openclaw-weixin`，`account`和`target`为已扫码绑定的账号/接收者。这些值及二维码、日志、发送账本均不得提交。另一台电脑需自行安装、绑定并配置，不能只克隆仓库即获得微信授权。

正文先写到本地runtime文件，避免命令行转义损坏。示例（项目根目录）：

```powershell
python tools/wechat_brief.py --body-file codex-quota-monitor/runtime/work-brief.txt --id <已推送的完整提交SHA> --dry-run
python tools/wechat_brief.py --body-file codex-quota-monitor/runtime/work-brief.txt --id <已推送的完整提交SHA>
```

当前工具通过常驻Gateway的`send` RPC发送：只有响应的`runId`与本次稳定请求标识一致、`channel`一致且存在`messageId`才确认成功，不能仅凭CLI退出码。当前安装版本的Gateway仅在通道发送成功后生成该回执。旧版`message send`路径使用的`payload.deliveryStatus=sent`不再作为新RPC的判据。相同工作ID不会自动重发；请求前先记录未确认状态，超时或进程中断时避免重复发送，应先现场检查微信再决定是否用新的ID重发。发送状态本地保存，不保存正文，不自动重试。

### 2026-11-23 Codex 对话启动失败恢复

微信显示 `OpenClaw couldn't finish this request` 时，网关记录了 Codex 进程启动 `ENOENT`。本机配置仍指向已被 Windows 应用更新替换的旧版本程序目录。核对 `Get-Command codex.exe` 和 `codex.exe --version` 后，更新 `plugins.entries.codex.config.appServer.command`，备份旧配置并安全重启网关。网关健康检查和一次关闭外部投递的独立 Codex 对话均通过。

同日 09:51 的简报拒绝发生在微信接口的 `prepare failed` 阶段。简报发送直接使用 Gateway 的 `send` RPC，Codex 对话恢复不改变微信主动推送的会话限制。后续 Windows 应用更新后，如对话再次出现 `ENOENT`，先检查此程序路径。

### 2026-11-18 微信接口拒绝检测和实测恢复

摇篮曲验收简报发送时本机 Gateway 健康检查通过。微信接口实际返回 `sendMessage ret=-2 errmsg=prepare failed`，旧脚本将它归为缺少回执。发送器现在将这条明确的拒绝记录为 `rejected / wechat_prepare_rejected`，日志只保存状态和耗时。相同工作 ID 保持防重复。

用户在微信 ClawBot 发来一条新消息后，发送器发出的验证消息拿到了匹配回执。新的入站消息可恢复本次会话。该错误与上游报告的主动推送失效现象一致，接口会话有效期及无人发消息时的长期主动推送能力尚未确认。 [微信插件上游复现](https://github.com/Tencent/openclaw-weixin/issues/389)

### 2026-11-17：发送超时修复及自启动核对

旧发送器每次启动独立`message send`，整个进程仅允许55秒；超时丢失阶段耗时和部分标准输出，留下一条uncertain。用户确认未收到。原始超时没有留下足够阶段证据，不能断言是CLI启动、网络或微信登录失效。后续日志存在独立的DNS/TCP长轮询错误，不把它们冒充本次发送失败的确定根因。

测量：版本查询0.09秒、Gateway健康1.56秒、本地发送dry-run7.34秒；直接发送命令与自启动Gateway的代理环境不同。新路径先检查已运行Gateway，再调用其`send` RPC，复用服务的插件、身份和环境，不额外调用模型。请求含稳定`idempotencyKey`；同一请求实测8.14秒成功，再查1.28秒返回相同回执。Gateway去重有运行期限制，不替代本机持久化防重复记录。

正式Python发送器实测健康检查1.31秒、发送3.09秒，平台回执通过，用户已在手机微信确认收到。7项回归覆盖：健康失败不发出、不占用工作ID；发送超时保留uncertain且不自动重发；错误回执不能报成功；已收到回执但CLI退出超时仍保留成功；dry-run/超时边界；持久防重复；诊断日志不含正文、账号或收件者。

默认外层等待180秒，可用`--timeout-seconds 30..300`调整；Gateway请求设独立期限。私有配置同目录的`brief-attempts.jsonl`只记录事件哈希、阶段、时间、耗时与状态，不记录正文或服务原始响应。健康检查失败返回`not_sent/gateway_unavailable`；请求已提交但无确定回执返回`uncertain`，不自动退回另一路发送。

Windows登录自启动原已开启，本次继续使用`OpenClaw Gateway.vbs → gateway.cmd → gateway-with-proxy.exe`，核对入口及文件存在，并再次启动此入口；当前配置端口只有一个监听进程，随后正式发送成功。发送器由工作完成流程调用，依赖自启动常驻网关，无需再手动打开独立同步程序。本次未重启整台电脑，不宣称新的冷启动现场验收；旧版真实重启记录见下文。

2026-11-16本机验证：扫码凭证保存、微信通道运行，用户发送“测试”后收到直接测试回复。初次尚无会话上下文时发送被拒绝；不将绑定成功等同所有情况下均可主动推送。OpenClaw默认模型未登录曾返回AI服务错误，直接发送工具不依赖此模型。

## Codex对话接入与当前验证范围

本机另外安装`@openclaw/codex@2026.11.3`，默认模型为`openai/gpt-6.1-sol`、模型运行时固定`codex`，备用模型列表为空。`plugins.entries.codex.config.appServer.homeScope="user"`显式复用本机Codex的ChatGPT登录，不复制登录密钥进仓库；程序路径使用本机Codex可执行文件。设置`approvalPolicy="on-request"`、`sandbox="workspace-write"`，工作区为本项目，关闭原生会话目录浏览。该对话接入会消耗现有Codex额度，不代表免费无限调用。

微信收到消息后由OpenClaw会话调用Codex，不是自动续接当前Codex桌面对话。项目上下文以本仓库文档和AGENTS.md为准，不同时发起相互冲突的修改。OpenClaw生成的本机IDENTITY.md、SOUL.md、USER.md通过本地Git排除规则保留，不提交个人资料。

该电脑目前直连模型服务超时，通过已有本机代理可访问。网关需使用可用的HTTPS代理，并保留localhost/微信服务的合适直连规则；代理地址是本机部署条件，不是其他电脑的通用设置。Tailscale未安装，已持久设置为off。初版通过手动前台窗口运行，后续按用户要求配置了下面的登录自启动，不再需要保留该手动窗口。

曾出现模型未登录、模型列表请求超时以及微信端DNS/请求超时，不能仅凭扫码或网关running认定对话可用。后续已核对网关与原生Codex子进程均继承本机代理；独立app-server账号读取及8个模型列表约3秒内返回。通过OpenClaw调用gpt-6.1-sol的文字诊断约19.4秒完成，实际返回“连接成功”，状态ok。用户随后在微信发送7加8，明确确认收到15，完整往返通过；不保证长期稳定。

## Windows登录自启动与自动重连

检查时未发现已有OpenClaw任务、服务或启动项。使用OpenClaw官方`gateway install`安装，当前账号采用原生Startup-folder回退：启动文件夹的`OpenClaw Gateway.vbs`以隐藏窗口调用用户目录下`gateway.cmd`。服务状态可能标为Scheduled Task，但runtime.detail明确为Startup-folder login item；不要因此声称安装了开机前运行的系统服务。

本机最终入口通过`gateway-with-proxy.exe`运行，固定Node.js 24.22.3、OpenClaw 2026.11.3、已有本机代理与NO_PROXY；源代码见[Windows启动包装器](tools/windows/GatewayProxyWrapper.cs)，重建见[说明](tools/windows/README.md)。仅设置config.env.vars的首轮启动测试没有把代理传给实际Codex子进程，因此未计作成功；批处理wrapper被Windows直接spawn拒绝后，改用原生exe并重新完成安装。旧手动进程与服务命令不匹配，迁移时验证了进程身份后结束旧实例，未停止Codex桌面。

最终核对：启动项存在并隐藏运行、官方service.loaded=true、RPC健康通过；新PID替代旧手动网关，实际网关和Codex子进程均继承代理；微信configured/running且lastError为空，未重新扫码。通过新网关调用gpt-6.1-sol约13.6秒返回“自启动验证：微信已自动重连，Codex回复正常。”，根级deliveryStatus.status=sent且succeeded=true。不能把CLI的sourceReplyDeliveryState=missing单独当作投递失败，它针对源会话，显式reply目标的投递以deliveryStatus为准。

已验证启动项调用路径、网关重新启动后的自动连接和实际消息投递；没有重启整机或执行真实注销/再登录，不能声称整机重启现场验收通过。需Windows登录、电脑联网、本机代理可用；网络或代理未就绪时消息仍可能超时。凭证过期时仍可能需要重新扫码。机器特定启动器、二进制、用户配置、凭证和日志均留在本机，不随Git上传。

### 首次真实重启失败及修正

用户于2026-11-16重启电脑后反馈微信无回复。系统启动时间14:04:48，日志14:06:47显示`Windows task supervisor lost its original CMD launcher`：启动项已触发，但旧EXE直接启动Node，使监督器的直接父进程不符合CMD身份契约。此前运行中重启/投递的成功不能证明该真实登录路径正确，前述验证范围应按本条更新。

修正版让EXE启动系统CMD，再由CMD启动Node，并明确选择官方支持的CMD生命周期所有者；保留代理和原身份验证，不删除锁文件或重新绑定微信。保留旧源文件/二进制本机备份，重新编译后从同一`OpenClaw Gateway.vbs`启动。初次40秒监听检查未就绪，不计成功；预热后观察到受监督网关运行，祖先链含CMD/监督器/包装器/原CMD/WScript，代理正确，微信消息处理和回传成功。用户随后发送“只回复：重启测试正常”，明确确认收到“重启测试正常”。

实际编译包装器的安全参数拒绝/版本执行两项测试，以及简报发送/防重复两项测试通过。当前确认同一Windows登录入口恢复可用且微信现场往返通过；修正后没有再次重启整台电脑，仍需区分本次启动入口验证与下次完整冷启动现场验收。首次启动可能需要较长预热，不按固定40秒断言失败或直接再开一个实例。

### 再次真实重启：自启动成功但就绪很慢

用户再次重启后最初未收到回复，随后确认约四分钟后收到“已收到重启后的消息，微信连接和Codex回复正常”。此次系统启动14:32:54、WScript/包装器14:34:13自动出现，原生监督器及网关持续存活，网关ready约14:37:30、微信投递日志14:38:10成功，无需手动启动或扫码。这是修正版的真实开机/登录成功证据；此次不能继续归因为网关退出或绑定丢失。

启动日志显示网关自身初始化约151秒，插件runtime-post-bind约74秒。默认加载43个插件，其中包含大量没有配置账号的模型/媒体供应商。使用官方`plugins.allow`收敛到[15项保留列表](tools/windows/openclaw-plugin-allowlist.json)，仍保留微信、Codex、OpenAI、记忆、浏览器、GitHub、文件、文档等原有基础工具；其余供应商仍安装，不删除配置，原配置已在本机备份。今后使用其他供应商需将相应插件加入列表。

配置校验与加载列表检查通过，实际加载15项；运行中网关日志确认plugins.allow热重载成功，使用官方safe restart后ready阶段记录初始化约41.4秒，Codex文字测试约18.5秒完成，实际投递sent。四项既有启动器/简报测试通过。该调整减少待加载插件数量，但本次只测运行中重启，不能将暖机耗时作为下一次整机冷启动耗时或承诺开机即刻回复。Windows登录启动等待与代理/网络就绪仍是独立因素。

官方流程：https://github.com/Tencent/openclaw-weixin
