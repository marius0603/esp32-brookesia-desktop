"""Package an application source component, never a replacement system image."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
component = ROOT / "brookesia/components/codex_quota_app"
library = ROOT / "brookesia/compile-check/build/esp-idf/codex_quota_app/libcodex_quota_app.a"
linked = ROOT / "brookesia/compile-check/build/codex_quota_brookesia_compile_check.elf"
binary = linked.with_suffix(".bin")
if not all(path.exists() for path in (library, linked, binary)):
    raise SystemExit("Compile the Brookesia integration fixture first.")
manifest = {
    "type": "brookesia_application_source",
    "version": "0.2.1",
    "device_flash_written": False,
    "complete_factory_source_available": False,
    "validation": "Official public Brookesia core compile/link check only; not deployed in factory firmware",
    "component_archive_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
    "files": {},
}
paths = [path for path in component.rglob("*") if path.is_file()]
if any(path.stat().st_mtime > binary.stat().st_mtime for path in paths):
    raise SystemExit("Component sources changed after the last build; rebuild first.")
for path in paths:
    manifest["files"][str(path.relative_to(component)).replace("\\", "/")] = hashlib.sha256(path.read_bytes()).hexdigest()
out = ROOT / "artifacts/brookesia-codex-quota-app-0.2.1-source.zip"
with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in paths:
        archive.write(path, Path("codex_quota_app") / path.relative_to(component))
    archive.write(ROOT / "brookesia/README.md", "INTEGRATION.md")
    archive.write(ROOT / "brookesia/FACTORY_SOURCE_REQUEST.md", "FACTORY_SOURCE_REQUEST.md")
    archive.write(ROOT / "PROTOCOL.md", "PROTOCOL.md")
    archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
print(out)
