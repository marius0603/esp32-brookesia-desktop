"""Build the full-screen pet layout and its transparent gesture surface."""
import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


def place(x, y, width, height):
    return {"mode": "absolute", "x": x, "y": y, "width": width, "height": height}


def image(name, asset, x, y, width, height):
    return {
        "type": "image", "id": name, "placement": place(x, y, width, height),
        "commonProps": {"clickable": False, "scrollable": False},
        "bindings": {"placement.x": "x", "placement.y": "y"},
        "imageProps": {"src": "${image." + asset + "}", "innerAlign": "center"},
    }


def main():
    touch = {
        "type": "container", "id": "touch", "placement": place(0, 0, 480, 440),
        "commonProps": {"clickable": True, "scrollable": False, "pressLock": True},
        "style": {"bgOpacity": 0, "padding": 0, "borderWidth": 0},
        "events": [
            {"type": "pressed", "action": "facePress"},
            {"type": "pressing", "action": "faceMove"},
            {"type": "released", "action": "faceRelease"},
            {"type": "pressLost", "action": "faceCancel"},
        ],
    }
    screen = {
        "type": "viewScreen", "id": "main", "commonProps": {"scrollable": False},
        "style": {"bgColor": "#000000", "padding": 0},
        "children": [
            image("crown", "crown", 80, 30, 320, 90),
            image("left", "eye_open", 70, 150, 130, 140),
            image("right", "eye_open", 280, 150, 130, 140),
            image("mouth", "mouth_idle", 200, 320, 80, 50),
            touch,
        ],
    }
    (APP / "src/res/screens/main.json").write_text(
        json.dumps(screen, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
