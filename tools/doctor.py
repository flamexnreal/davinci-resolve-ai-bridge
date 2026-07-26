#!/usr/bin/env python3
"""Diagnose the installed bridge without importing Resolve."""

import json
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOME = Path(os.environ.get("RESOLVE_AI_BRIDGE_HOME", Path.home() / ".resolve-ai-bridge")).expanduser()
failures = 0
warnings = 0


def result(ok, label, detail="", warning=False):
    global failures, warnings
    if ok:
        prefix = "[OK]"
    elif warning:
        prefix = "[WARN]"
        warnings += 1
    else:
        prefix = "[FAIL]"
        failures += 1
    print("%-6s %s%s" % (prefix, label, (": " + detail) if detail else ""))


def check_python_sources():
    files = [ROOT / "install.py"]
    for folder in ("agent", "bridge", "tools"):
        files.extend(sorted((ROOT / folder).glob("*.py")))
    errors = []
    for path in files:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except Exception as exc:
            errors.append("%s: %s" % (path.relative_to(ROOT), exc))
    result(not errors, "Python source syntax", "; ".join(errors) if errors else "%d files compiled in memory" % len(files))


def main():
    print("\nResolve AI Bridge doctor")
    print("Runtime: %s\n" % HOME)

    result(sys.version_info >= (3, 10), "Python version", sys.version.split()[0])
    check_python_sources()
    result((HOME / "ResolveConsole.py").exists(), "Installed Console agent", str(HOME / "ResolveConsole.py"))
    result((HOME / "bridge" / "server.py").exists(), "Installed MCP server", str(HOME / "bridge" / "server.py"))
    venv_python = HOME / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    result(venv_python.exists(), "Private Python", str(venv_python))

    token_path = HOME / "token.txt"
    token = ""
    try:
        token = token_path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    result(token.startswith("rab_") and len(token) > 30, "Local token", "present and hidden" if token else "missing")

    config_path = HOME / "mcp-config.json"
    config_ok = False
    config_detail = str(config_path)
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        entry = config["mcpServers"]["resolve-ai-bridge"]
        config_ok = (
            Path(entry["command"]).exists()
            and Path(entry["args"][0]).exists()
            and entry.get("env", {}).get("RESOLVE_AI_BRIDGE_TOKEN") == token
        )
        if not config_ok:
            config_detail = "paths or token do not match; rerun install.py"
    except Exception as exc:
        config_detail = str(exc)
    result(config_ok, "MCP configuration", config_detail)

    heartbeat_path = HOME / "agent.json"
    heartbeat = None
    try:
        heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    online = bool(heartbeat and time.time() - float(heartbeat.get("time", 0)) < 25)
    detail = "offline"
    if heartbeat:
        detail = "age %.1fs, project %s, timeline %s" % (
            max(0, time.time() - float(heartbeat.get("time", 0))),
            heartbeat.get("project") or "none",
            heartbeat.get("timeline") or "none",
        )
    result(online, "Resolve Console agent", detail)

    if online:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        try:
            from bridge import client

            status = client.call("status", timeout=8)
            result(bool(status and status.get("online")), "Authenticated round trip", "Resolve answered status")
        except Exception as exc:
            result(False, "Authenticated round trip", str(exc))
    else:
        result(False, "Authenticated round trip", "skipped until the Console agent is online", warning=True)

    print("\nSummary: %d failure(s), %d warning(s)" % (failures, warnings))
    if failures:
        print("Open 00_START_HERE.html and follow the Help section in order.")
    else:
        print("The local bridge checks passed.")
    print()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())