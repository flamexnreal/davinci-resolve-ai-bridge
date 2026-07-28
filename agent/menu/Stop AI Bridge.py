#!/usr/bin/env python
"""Workspace > Scripts > Resolve AI Bridge > Stop AI Bridge.

Ends the worker started in this Resolve session. Your AI client then reports
the bridge as offline until it is started again.
"""

import os
import sys

HOME = os.path.expanduser(
    os.environ.get("RESOLVE_AI_BRIDGE_HOME", "~/.resolve-ai-bridge")
)
AGENT = os.path.join(HOME, "ResolveConsole.py")


def main():
    if not os.path.isfile(AGENT):
        print("Resolve AI Bridge is not installed. Nothing to stop.")
        return
    if HOME not in sys.path:
        sys.path.insert(0, HOME)
    os.environ["RESOLVE_AI_BRIDGE_NO_AUTOSTART"] = "1"
    try:
        with open(AGENT, encoding="utf-8") as handle:
            source = handle.read()
        exec(compile(source, AGENT, "exec"), globals())
        globals()["stop_bridge"]()
    finally:
        os.environ.pop("RESOLVE_AI_BRIDGE_NO_AUTOSTART", None)


main()
