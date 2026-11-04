"""Print the pip requirements of the Home Assistant components the tests load."""

import json
import pathlib

import homeassistant

root = pathlib.Path(homeassistant.__file__).parent / "components"
seen: set[str] = set()
requirements: set[str] = set()


def visit(domain: str) -> None:
    manifest = root / domain / "manifest.json"
    if domain in seen or not manifest.exists():
        return
    seen.add(domain)
    data = json.loads(manifest.read_text())
    requirements.update(data.get("requirements", []))
    for dep in data.get("dependencies", []) + data.get("after_dependencies", []):
        visit(dep)


for name in ("camera", "stream", "frontend", "websocket_api", "http", "diagnostics", "go2rtc", "webrtc", "config"):
    visit(name)
print("\n".join(sorted(requirements)))
