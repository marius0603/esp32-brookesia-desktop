"""Export the approved 48-cell face as small, presized LVGL images."""
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP.parents[1] / "tools"))
from build_cyberpunk_theme import native

BLUE = "#76D7FA"
PIXEL = 10
PARTS = {
    "ear": ["##....", "###...", "####..", "##.##.", "##..##",
            "##..##", ".##.##", "..####", "...##."],
    "forelock": [".......#####.", "....#########", "..#########..", ".#####..##...",
                 "...####......", "..####.......", ".##.........."],
    "eye_open": ["...#######...", "..#########..", ".###########.", *(["#############"] * 5),
                 ".###########.", "..#########..", "...#######..."],
    "eye_blink": [".###########.", "..#########.."],
    "eye_happy": ["....#####....", "..#########..", ".####...####.", "###.......###", "##.........##"],
    "eye_sleep": ["##.........##", ".###.....###.", "..#########..", "....#####...."],
    "eye_calm": [".###########.", "#############", "#############", ".###########.", "...#######..."],
    "eye_surprised": ["....#####....", "...#######...", "..#########..", ".###########.",
                      *(["#############"] * 6), ".###########.", "..#########..",
                      "...#######...", "....#####...."],
    "mouth_idle": ["..####.."],
    "mouth_happy": ["##....##", "########", ".######.", "..####.."],
    "mouth_sleep": ["...##...", "..#..#..", "...##..."],
    "mouth_calm": [".#....#.", ".######.", "...##..."],
    "mouth_surprised": ["..####..", ".######.", ".######.", ".######.", "..####.."],
}


def stamp(image, rows, x=0, y=0, mirror=False):
    draw = ImageDraw.Draw(image)
    for dy, row in enumerate(rows):
        for dx, pixel in enumerate(row[::-1] if mirror else row):
            if pixel == "#":
                left, top = (x + dx) * PIXEL, (y + dy) * PIXEL
                draw.rectangle((left, top, left + PIXEL - 1, top + PIXEL - 1), fill=BLUE)


def main():
    output = APP / "src/res/images"
    images = [{"id": "launcher_icon", "src": "launcher_icon.png", "width": 92, "height": 92, "preload": True}]

    def export(name, image):
        filename = f"{name}.bin"
        native(image, output / filename)
        images.append({"id": name, "src": filename, "width": image.width,
                       "height": image.height, "preload": True})

    crown = Image.new("RGB", (320, 90))
    stamp(crown, PARTS["ear"])
    stamp(crown, PARTS["ear"], 26, mirror=True)
    stamp(crown, PARTS["forelock"], 9, 2)
    export("crown", crown)
    for name, rows in PARTS.items():
        if name.startswith(("eye_", "mouth_")):
            # Every sprite in a group shares its bounds, so changing a source
            # never shifts its drawing inside the LVGL image.
            size = (130, 140) if name.startswith("eye_") else (80, 50)
            image = Image.new("RGB", size)
            stamp(image, rows)
            export(name, image)
    (output / "index.json").write_text(
        json.dumps({"type": "imageSet", "images": images}, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
