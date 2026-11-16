# 连续镜头的绘制缓存

配套版本：迷宫0.1.7、固件0.8.3-s3.68。保持连续跟随、碰撞索引与现有操控参数，调整静态场景的绘制方式和显示传输频率。

## 实现

- 主地图和缩略图各保留一张Canvas，墙段只在生成地图或切换深浅主题时绘制。移动时只更新镜头、小马、星星可见性和缩略图标记，不重建墙段命令。
- 主缓存固定为720×720 RGB565，缩略图76×76，按当前步长合计1048352字节；内存位于普通PSRAM堆，不新增内部DMA条带缓冲。关闭应用释放Canvas，不写入Flash或SD缓存文件。
- `cached-canvas-rect.patch`增加矩形/圆角矩形绘制，按原生颜色格式的行步长分配字节缓冲；属性快照携带解析后的尺寸，确保Canvas缓冲使用解析后的实际尺寸。
- `qspi-display-80mhz.patch`将此板的显示QSPI从40MHz改为80MHz；内部DMA暂存仍为4096字节、在途队列仍为1，原偶数行/列对齐与等待完成后复用缓冲的规则保留。

微雪说明该板默认40MHz，可尝试80MHz并以实测稳定性为准，见[官方AMOLED教程](https://docs.waveshare.net/ESP32-Peripheral-Tutorials/Display/AMOLED/)。不占用音频或其他GPIO模拟TE信号，也不把提高频率描述为硬件同步无撕裂保证。

## 重建

`tools/prepare_workspace.py`顺序应用16份补丁。已有工作区更新补丁后，需要重新执行板级代码生成，再编译；单独执行CMake reconfigure不会重写已生成的SPI配置。请保留原有sdkconfig，不改变原128KiB内部预留池、蓝牙和音频选项。

```powershell
python codex-quota-monitor/tools/brookesia_idf6.py gen-bmgr-config -b esp32_s3_touch_amoled_2_16
python codex-quota-monitor/tools/brookesia_idf6.py build
```

打包器核对生成代码的80MHz参数。新App启动时检查固件的`maze_canvas_cache`能力标识；旧固件会明确拒绝，避免显示空白地图。更新已有设备仍需先完整备份，再走应用分区更新和SD应用包部署，保存原配置、PIN和进度。

## 验证边界

填充命令也必须携带整数x/y/width/height；缺少这些字段时原生解析器会拒绝整组命令。本次修正该契约，并检查墙角和地面真实像素，之前未通过像素检查的白色缓存候选不计作性能结论。

应用替身测试确认只有两个固定Canvas，移动中不重画静态缓存，切换主题各重画一次，旧固件能力缺失时拒绝启动。补丁重建检查与完整固件编译覆盖运行时尺寸快照和原生RGB565路径。

`verify_maze_load.py`在实机临时自动引导第十关后检查Canvas实际尺寸、实际缓冲字节数及墙/地面像素颜色，并恢复正式代码、进度和音量；不能仅凭脚本帧计数判断图像正确。额外运行音频/蓝牙与配置保留检查。最终测量及实屏结果见[验证记录](VERIFICATION.md)，不将随机路线下的更新次数直接当作固定帧率。
