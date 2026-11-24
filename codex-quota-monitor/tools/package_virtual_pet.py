"""Package the pixel pet and all of its live resources in one BPK."""
import json
from pathlib import Path
import subprocess

from build_learning_packages import archive
from runtime_paths import find_node

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "brookesia-apps/virtual-pet"


def main():
    subprocess.run([find_node(), str(APP / "tests/main.test.cjs")], check=True, cwd=ROOT)
    src = APP / "src"
    package = json.loads((src / "manifest.json").read_bytes())["package"]
    version = json.loads((ROOT / "versions.json").read_bytes())["apps"][package["id"]]
    assert package["version"] == version
    assert json.loads((src / "res/root.json").read_bytes())["version"] == version
    name = f"packages/apps/{package['id']}.debug.{version}.bpk"
    files = {file.relative_to(src).as_posix(): file.read_bytes()
             for file in sorted(src.rglob("*")) if file.is_file()}
    hashes_path = ROOT / "packages/SHA256.json"
    hashes = json.loads(hashes_path.read_bytes())
    hashes[name] = archive(ROOT / name, files)
    assert (ROOT / name).stat().st_size < 100000
    hashes_path.write_text(json.dumps(hashes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{name} verified.")


if __name__ == "__main__":
    main()
