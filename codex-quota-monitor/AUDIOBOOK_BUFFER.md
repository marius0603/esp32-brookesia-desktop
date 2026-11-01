# 故事播放缓冲：s3.39 / 听书0.3.5

原问题：每篇故事约每一两秒停顿一次，锁屏后仍出现。修正版已安装到开发板，用户连续试听后确认播放流畅、卡顿消失。

## 实现

- `platform/super_s3_216/main/modules/audiobook/buffered_pcm.hpp`提供64KiB PSRAM队列，预填32KiB。SD读取和MP3解码在原生产任务中运行，独立输出任务使用8KiB内部RAM栈，将PCM以至多2048字节的块提交到喇叭。
- 队列带跳转代次和源文件位置；暂停保留音频，跳转淘汰旧数据，手动停止、睡眠到时或取消时退出输出。书签在实际提交后推进，正常结尾排空队列。
- 播放模式用`Audiobook.SetPlayMode`和`GetState.play_mode`共享。首次读取由Storage服务完成，之后仅实际模式变化才保存；手机状态查询和设备每秒刷新不再重复读模式文件。
- 听书0.3.5必须配合s3.39。原故事、主题、模式文件和书签兼容；原文件下载录音、测试日志及完整Flash备份不入Git。

## 更新已有s3.38设备

先关闭正在占用USB的额度采集器，取消睡眠定时并解锁设备。在仓库根目录执行，端口和备份路径按本机调整：

```powershell
python codex-quota-monitor/tools/backup_current_firmware.py --port COM5 --label before-buffered-audio
# 解压 packages/firmware/brookesia-0.8.3-s3.39-app-only.zip 到仓库外目录
python codex-quota-monitor/tools/update_brookesia_app_only.py --port COM5 --build <解压目录> --backup <本次校验的私有备份目录>
python codex-quota-monitor/tools/deploy_audiobook_buffer.py --port COM5
```

最后重新启动开发板刷新应用版本缓存。安装器只备份并更新`app/main.js`与`manifest.json`，通过SD暂存和SHA256读回核对，保留已有主题图标及媒体资源。首次安装还需完整听书应用和既有资源，不能仅用此增量工具。

## 已完成验证（2026-11-01）

固件编译、应用分区写入读回、应用文件与BPK源码核对通过。原20篇书库保留，恢复原故事《棉花姑娘》、书签、顺序模式和88%音量。回归包括播放模式同步、暂停/继续、暂停后跳转20秒、停止以及10秒加速睡眠定时，到时停止且不会自动续播。

每篇下列故事连续运行15秒，每32个解码块注入200ms延迟，输出数据持续增加：

| 故事 | 队列断粮次数 | 输出调用间隔最大值 | 最大解码耗时（含注入延迟） | 输出栈最少空余 |
| --- | ---: | ---: | ---: | ---: |
| 小马过河 | 0 | 187µs | 244147µs | 5564字节 |
| 小公鸡和小鸭子 | 0 | 102µs | 276038µs | 5552字节 |
| 小壁虎借尾巴 | 0 | 113µs | 270896µs | 5552字节 |

“输出调用间隔”是上次codec写入返回至下一次调用开始的间隔，不是声学测量。测试覆盖短时调度延迟与控制回归，未代表全部20篇完整播完或长期运行测试。最终用户试听确认原有周期性卡顿消失。

复现工具：`python codex-quota-monitor/tools/verify_audiobook_buffer.py --port COM5`。工具会临时静音、注入延迟、检查控制动作并恢复原偏好和播放；先停止其他USB客户端。诊断接口`Audiobook.TestDecodeDelay`仅测试使用，不持久化，正常播放值为0。
