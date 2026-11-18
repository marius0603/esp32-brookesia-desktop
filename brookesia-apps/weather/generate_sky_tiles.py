"""Generate small, repeatable native RGB565 sky textures for the weather app."""
import json
from pathlib import Path
import struct


SOURCE = Path(__file__).resolve().parent / "src"
WIDTH = 32
HEIGHT = 480
BAYER = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)


def encode_tile(top_hex: str, bottom_hex: str) -> bytes:
    top = bytes.fromhex(top_hex.removeprefix("#"))
    bottom = bytes.fromhex(bottom_hex.removeprefix("#"))
    pixels = bytearray()
    span = HEIGHT - 1
    denominator = 255 * span
    levels = (31, 63, 31)
    for y in range(HEIGHT):
        values = [
            divmod(((span - y) * start + y * end) * limit, denominator)
            for start, end, limit in zip(top, bottom, levels)
        ]
        row = bytearray()
        for bayer in BAYER[y % 4]:
            threshold = (2 * bayer + 1) * denominator
            red, green, blue = (low + (32 * remainder > threshold) for low, remainder in values)
            row.extend(struct.pack("<H", red << 11 | green << 5 | blue))
        pixels.extend(row * (WIDTH // len(BAYER[0])))

    # LVGL v9 raw RGB565 image header followed by little-endian pixels.
    header = struct.pack("<BBHHHHH", 0x19, 0x12, 0, WIDTH, HEIGHT, WIDTH * 2, 0)
    return header + pixels


def main() -> None:
    app_source = (SOURCE / "app/main.js").read_text(encoding="utf-8")
    palettes, _ = json.JSONDecoder().raw_decode(app_source.split("const SKY_PALETTES = ", 1)[1])
    image_dir = SOURCE / "res/images"
    for name, endpoints in palettes.items():
        (image_dir / f"sky_{name}.bin").write_bytes(encode_tile(*endpoints))


if __name__ == "__main__":
    main()
