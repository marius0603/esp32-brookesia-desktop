"""480 x 480 desktop preview with live data, selection and stale-data indication."""
import json
import time
import tkinter as tk
from .model import countdown, display_status, window_name
from .service import ROOT

TEXT = {"ok": "额度已同步", "starting": "正在连接 Codex", "error": "采集失败 · 保留上次数据", "auth_required": "请在电脑端登录 Codex", "stale": "数据已过期", "offline": "采集服务已停止"}


def show_preview(monitor=None, export_path=None):
    root = tk.Tk()
    if export_path:
        root.withdraw()
    root.title("Codex 额度仪表盘 · 480×480 预览")
    root.resizable(False, False)
    canvas = tk.Canvas(root, width=480, height=480, bg="#080c12", highlightthickness=0)
    canvas.pack()
    selected = [0]
    def select(_event):
        selected[0] = 1 - selected[0]
    canvas.bind("<Button-1>", select)
    if monitor:
        root.bind("<r>", lambda _event: monitor.request_refresh())

    def draw():
        try:
            packet = monitor.get_snapshot() if monitor else json.loads((ROOT / "runtime/latest.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            packet = {"status": "starting", "windows": []}
        now = time.time()
        status = display_status(packet, now)
        if not monitor and now - packet.get("bridge_at", now) > 5:
            status = "offline"
        canvas.delete("all")
        canvas.create_text(240, 35, text="CODEX  /  " + (packet.get("plan") or "--").upper(), fill="#dce7f3", font=("Segoe UI", 15, "bold"))
        canvas.create_text(240, 65, text=TEXT.get(status, status), fill="#4ce0b3" if status == "ok" else "#ffb759", font=("Microsoft YaHei UI", 10))
        windows = packet.get("windows", [])
        chosen = windows[selected[0] % len(windows)] if windows else None
        remaining = 100 - chosen["used"] if chosen else None
        def quota_color(value):
            if status != "ok":
                return "#718096"
            if value is not None and value <= packet.get("critical", 10):
                return "#ff6878"
            return "#4ce0b3" if value is None or value > packet.get("warning", 20) else "#ffb759"
        color = quota_color(remaining)
        canvas.create_oval(123, 91, 357, 325, outline="#202b38", width=12)
        if remaining and remaining < 100:
            canvas.create_arc(123, 91, 357, 325, start=90, extent=-remaining * 3.6, style="arc", outline=color, width=12)
        elif remaining == 100:
            canvas.create_oval(123, 91, 357, 325, outline=color, width=12)
        canvas.create_text(240, 156, text=window_name(chosen["minutes"]) if chosen else "暂无额度数据", fill="#9aafc6", font=("Microsoft YaHei UI", 12))
        canvas.create_text(240, 211, text=f"{remaining:g}%" if remaining is not None else "--", fill=color, font=("Segoe UI", 49, "bold"))
        canvas.create_text(240, 259, text="剩余", fill="#9aafc6", font=("Microsoft YaHei UI", 12))
        canvas.create_text(240, 290, text=countdown(chosen.get("reset_at"), now) if chosen else "等待首次同步", fill="#dce7f3", font=("Microsoft YaHei UI", 11))
        other = windows[(selected[0] + 1) % len(windows)] if len(windows) > 1 else None
        if other:
            canvas.create_text(240, 354, text=f"{window_name(other['minutes'])}    剩余 {100-other['used']:g}%", fill="#dce7f3", font=("Microsoft YaHei UI", 12))
            canvas.create_rectangle(105, 379, 375, 385, fill="#202b38", outline="")
            canvas.create_rectangle(105, 379, 105 + 270 * (100-other["used"]) / 100, 385, fill=quota_color(100-other["used"]), outline="")
        sample = packet.get("sampled_at")
        synced = time.strftime("%H:%M:%S", time.localtime(sample)) if sample else "--:--:--"
        canvas.create_text(240, 416, text=f"同步 {synced}  ·  USB {'已连接' if packet.get('device', 'disconnected') != 'disconnected' else '待连接'}", fill="#8295ac", font=("Microsoft YaHei UI", 10))
        canvas.create_text(240, 445, text="点击切换额度" + ("  ·  R 刷新" if monitor else ""), fill="#566a82", font=("Microsoft YaHei UI", 9))
        root.after(1000, draw)
    draw()
    if export_path:
        export_canvas(canvas, export_path)
        root.destroy()
        return
    root.mainloop()


def export_canvas(canvas, path):
    """Render the preview's actual canvas primitives as a PNG (Pillow is a dev dependency)."""
    from PIL import Image, ImageDraw, ImageFont
    scale = 2
    output = Image.new("RGB", (480 * scale, 480 * scale), "#080c12")
    painter = ImageDraw.Draw(output)
    for item in canvas.find_all():
        kind = canvas.type(item)
        coordinates = [round(n * scale) for n in canvas.coords(item)]
        fill = canvas.itemcget(item, "fill") or None
        if kind == "text":
            font_spec = canvas.itemcget(item, "font")
            family, size, *style = canvas.tk.splitlist(font_spec)
            fontfile = "msyh.ttc" if "YaHei" in family else "segoeuib.ttf" if "bold" in style else "segoeui.ttf"
            font = ImageFont.truetype("C:/Windows/Fonts/" + fontfile, round(int(size) * 4 / 3 * scale))
            painter.text(coordinates, canvas.itemcget(item, "text"), fill=fill, font=font, anchor="mm")
        elif kind in ("oval", "rectangle", "arc"):
            outline = canvas.itemcget(item, "outline") or None
            width = round(float(canvas.itemcget(item, "width")) * scale)
            if kind == "oval":
                painter.ellipse(coordinates, fill=fill, outline=outline, width=width)
            elif kind == "rectangle":
                painter.rectangle(coordinates, fill=fill, outline=outline, width=width)
            else:
                start = -float(canvas.itemcget(item, "start"))
                end = start - float(canvas.itemcget(item, "extent"))
                painter.arc(coordinates, start, end, fill=outline, width=width)
    output.save(path)
