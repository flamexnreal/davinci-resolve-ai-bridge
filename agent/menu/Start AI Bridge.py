#!/usr/bin/env python
"""Workspace > Scripts > Resolve AI Bridge > Start AI Bridge.

Outputs the activation command to paste into DaVinci Resolve's Py3 Console.
"""

import os

HOME = os.path.expanduser(
    os.environ.get("RESOLVE_AI_BRIDGE_HOME", "~/.resolve-ai-bridge")
)
AGENT = os.path.join(HOME, "ResolveConsole.py")

PORTABLE_CMD = (
    'import os;exec(open(os.path.expanduser('
    '"~/.resolve-ai-bridge/ResolveConsole.py"),encoding="utf-8").read())'
)
EXPLICIT_CMD = 'exec(open("%s", encoding="utf-8").read())' % AGENT


def main():
    print("\n" + "=" * 72)
    print("RESOLVE AI BRIDGE - PY3 CONSOLE ACTIVATION")
    print("=" * 72)
    print("In DaVinci Resolve (especially Free version), external API menu execution")
    print("is restricted by Blackmagic Design. To activate the AI Bridge:")
    print("")
    print("1. Open Workspace > Console in DaVinci Resolve.")
    print("2. Click the 'Py3' tab at the top of the Console window.")
    print("3. Copy and paste the command below, then press Enter:\n")
    print("   " + PORTABLE_CMD)
    print("")
    if os.path.isfile(AGENT):
        print("Or copy and paste this explicit path version:")
        print("   " + EXPLICIT_CMD)
        print("")
    print("Log file location: %s" % os.path.join(HOME, "logs", "agent.log"))
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()

