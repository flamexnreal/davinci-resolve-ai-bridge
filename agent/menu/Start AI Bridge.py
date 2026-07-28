#!/usr/bin/env python
"""Workspace > Scripts > Resolve AI Bridge > Start AI Bridge.

One click, no paths to edit. Resolve injects ``resolve`` into this script's
globals, and those globals are handed straight to the installed worker.
"""

import os
import sys

HOME = os.path.expanduser(
    os.environ.get("RESOLVE_AI_BRIDGE_HOME", "~/.resolve-ai-bridge")
)
AGENT = os.path.join(HOME, "ResolveConsole.py")


def main():
    if not os.path.isfile(AGENT):
        print("Resolve AI Bridge is not installed yet.")
        print("Expected: %s" % AGENT)
        print("Run install.py from the downloaded project folder, then restart DaVinci Resolve.")
        return
    if HOME not in sys.path:
        sys.path.insert(0, HOME)
    with open(AGENT, encoding="utf-8") as handle:
        source = handle.read()
    exec(compile(source, AGENT, "exec"), globals())


main()
