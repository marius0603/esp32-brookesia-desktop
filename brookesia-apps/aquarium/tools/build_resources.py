"""Scale the original aquarium pixel art and build its native view document."""
from array import array
import json
from pathlib import Path
import struct
import sys

from PIL import Image, ImageDraw, ImageOps

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP.parents[1] / "tools"))
from build_wallpaper_render import rle_pixels

ART = APP / "art"
RES = APP / "src/res"
BAND_HEIGHT = 120
FISH = [
    ("gold", 78, 68, 1),
    ("moon", 105, 105, -1),
    ("school", 111, 43, 1),
    ("school", 124, 52, 1),
    ("school", 134, 40, 1),
    ("school", 121, 32, 1),
]
FISH_SCALE = {"gold": 3, "moon": 3, "school": 2}


def write_native_image(image, path, compressed):
    width, height = image.size
    rgb = image.convert("RGB").tobytes()
    pixels = array("H", ((red >> 3) << 11 | (green >> 2) << 5 | (blue >> 3)
                         for red, green, blue in zip(rgb[::3], rgb[1::3], rgb[2::3])))
    if sys.byteorder != "little":
        pixels.byteswap()
    alpha = image.getchannel("A").tobytes() if image.mode == "RGBA" else b""
    color_format = 0x14 if alpha else 0x12
    raw = pixels.tobytes() + alpha
    header = struct.pack("<BBHHHHH", 0x19, color_format, 8 if compressed else 0,
                         width, height, width * 2, 0)
    if compressed:
        encoded = rle_pixels(raw)
        raw = struct.pack("<III", 1, len(encoded), len(raw)) + encoded
    path.write_bytes(header + raw)


def write_json(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def place(x, y, w, h):
    return {"mode": "absolute", "x": x, "y": y, "width": w, "height": h}


def container(name, x, y, w, h, **extra):
    return {"type": "container", "id": name, "placement": place(x, y, w, h),
            "commonProps": {"clickable": False, "scrollable": False},
            "style": {"bgOpacity": 0, "padding": 0, "borderWidth": 0}, **extra}


def label(name, text, x, y, w, h, size=22, center=False):
    return {"type": "label", "id": name, "placement": place(x, y, w, h),
            "style": {"font": "${font.zh_CN}", "fontSize": size,
                      "textColor": "#dcf4e6", "textAlign": "center" if center else "left"},
            "labelProps": {"text": text}}


def button(name, text, x, y, w, h=48):
    value = container(name, x, y, w, h, children=[label("label", text, 0, 10, w, 30, 22, True)])
    value["commonProps"]["clickable"] = True
    value["style"].update(bgColor="#0B353E", bgOpacity=255, radius=6,
                          borderColor="#467D78", borderWidth=1)
    value["events"] = [{"type": "clicked", "action": name}]
    return value


def picture(name, image, x, y, w, h, moves=False):
    node = container(name, x, y, w, h)
    node.update(type="image", imageProps={"src": "${image." + image + "}", "innerAlign": "center"})
    if moves:
        node["bindings"] = {"placement.x": "x", "placement.y": "y"}
    return node


def main():
    images_dir = RES / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    images = []

    def export(name, art, extension, compressed=True):
        filename = name + extension
        dest = images_dir / filename
        if extension == ".bin":
            write_native_image(art, dest, compressed)
        else:
            art.save(dest, optimize=True)
        images.append(dict(id=name, src=filename, width=art.width, height=art.height, preload=True))

    for light in ("day", "night"):
        with Image.open(ART / (light + ".png")) as art:
            scene = art.convert("RGB").resize((480, 480), Image.Resampling.NEAREST)
            for band, y in enumerate(range(0, 480, BAND_HEIGHT)):
                export(f"{light}{band}", scene.crop((0, y, 480, y + BAND_HEIGHT)), ".bin")

    sizes = {}
    for kind, scale in FISH_SCALE.items():
        for phase in range(2):
            with Image.open(ART / f"{kind}{phase}.png") as art:
                size = (art.width * scale, art.height * scale)
                sizes[kind] = size
                expanded = art.resize(size, Image.Resampling.NEAREST)
                # Keep both goldfish poses on the same per-pixel alpha path.
                extension = ".png" if kind == "gold" else ".bin"
                compressed = kind == "moon" and phase == 1
                export(f"{kind}_r{phase}", expanded, extension, compressed)
                export(f"{kind}_l{phase}", ImageOps.mirror(expanded), extension, compressed)

    icon = Image.new("RGBA", (46, 46))
    pen = ImageDraw.Draw(icon)
    pen.rounded_rectangle((1, 1, 44, 44), radius=9, fill="#164A57", outline="#40878A")
    pen.line((4, 29, 14, 29, 18, 32, 31, 32, 35, 29, 42, 29), fill="#247365", width=2)
    with Image.open(ART / "gold0.png") as art:
        fish = art.crop(art.getbbox())
        fish.thumbnail((34, 26), Image.Resampling.NEAREST)
        icon.alpha_composite(fish, ((46-fish.width)//2, 9))
    export("launcher_icon", icon.resize((92, 92), Image.Resampling.NEAREST), ".png")
    write_json(images_dir / "index.json", {"type": "imageSet", "images": images})

    nodes = [picture(f"backdrop{band}", f"day{band}", 0, y, 480, BAND_HEIGHT)
             for band, y in enumerate(range(0, 480, BAND_HEIGHT))]
    bubble = container("bubble", 394, 345, 7, 7)
    bubble["bindings"] = {"placement.y": "y"}
    bubble["style"].update(radius=4, borderWidth=1, borderColor="#87C8BC")
    nodes.append(bubble)
    ripple = container("ripple", 0, 0, 20, 20, bindings={
        "placement.x": "x", "placement.y": "y", "placement.width": "w",
        "placement.height": "h", "commonProps.hidden": "hidden",
    })
    ripple["commonProps"]["hidden"] = True
    ripple["style"].update(radius=32767, borderWidth=2, borderColor="#A5EAD8")
    nodes.append(ripple)
    for i, (kind, x, y, facing) in enumerate(FISH):
        w, h = sizes[kind]
        nodes.append(picture("fish" + str(i), f"{kind}_{'r' if facing > 0 else 'l'}0",
                             x*3-w//2, y*3-h//2, w, h, True))

    touch = container("water", 0, 0, 480, 440)
    touch["commonProps"].update(clickable=True, pressLock=True)
    touch["events"] = [
        {"type": event, "action": name}
        for event, name in (("pressed", "waterPress"), ("released", "waterRelease"), ("pressLost", "waterCancel"))
    ]
    lighting = button("light", "日景", 24, 24, 72)
    lighting["children"][0]["bindings"] = {"labelProps.text": "text"}
    nodes.extend([touch, lighting, button("book", "鱼册", 374, 390, 82)])

    options = [button(name, text, x, 50, 134) for name, text, x in (
        ("gold", "金鳞", 22), ("moon", "月影", 173), ("school", "蓝线", 324))]
    for option in options:
        option["bindings"] = {"style.bgColor": "color"}
    description = label("description", "好奇 · 喜欢靠近水波", 22, 112, 430, 32)
    description["bindings"] = {"labelProps.text": "text"}
    panel = container("sheet", 0, 292, 480, 148, children=[
        label("heading", "鱼册", 22, 12, 128, 32, 25),
        button("dismiss", "关闭", 376, 3, 82, 46),
        *options,
        description,
    ])
    panel["commonProps"].update(clickable=True, hidden=True)
    panel["style"].update(bgColor="#082831", bgOpacity=255, borderColor="#3F7A74", borderWidth=1)
    panel["bindings"] = {"commonProps.hidden": "hidden"}
    nodes.append(panel)
    write_json(RES / "screens/main.json", {"type": "viewScreen", "id": "main",
               "commonProps": {"scrollable": False}, "style": {"bgColor": "#0D3440", "padding": 0},
               "children": nodes})


if __name__ == "__main__":
    main()
