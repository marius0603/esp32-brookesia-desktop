"""Build the self-contained aquarium app archive."""
import json
from pathlib import Path
import subprocess

from build_learning_packages import archive
from runtime_paths import find_node

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "brookesia-apps/aquarium"


def main():
    subprocess.run([find_node(), str(APP / "tests/main.test.cjs")], cwd=ROOT, check=True)
    src = APP / "src"
    manifest = json.loads((src / "manifest.json").read_bytes())["package"]
    app_id, version = manifest["id"], manifest["version"]
    assert json.loads((ROOT / "versions.json").read_bytes())["apps"][app_id] == version
    assert json.loads((src / "res/root.json").read_bytes())["version"] == version
    name = f"packages/apps/{app_id}.debug.{version}.bpk"
    files = {path.relative_to(src).as_posix(): path.read_bytes()
             for path in sorted(src.rglob("*")) if path.is_file()}
    hashes_path = ROOT / "packages/SHA256.json"
    hashes = json.loads(hashes_path.read_bytes())
    hashes[name] = archive(ROOT / name, files)
    hashes_path.write_text(json.dumps(hashes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{name} verified ({(ROOT / name).stat().st_size} bytes).")


if __name__ == "__main__":
    main()
