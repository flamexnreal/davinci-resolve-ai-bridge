#!/usr/bin/env python
"""Workspace > Scripts > Resolve AI Bridge > Start AI Bridge.

One click, no paths to edit.

Resolve usually injects ``resolve`` into this script's globals, and those
globals are handed straight to the installed worker. It does not always do so
for a Scripts-menu run, which is why every object this script can see is
collected here and why the worker also knows how to obtain Resolve from its
scripting library on disk. Between the two, the menu click behaves the same as
a Console paste.
"""

import builtins
import os
import sys

HOME = os.path.expanduser(
    os.environ.get("RESOLVE_AI_BRIDGE_HOME", "~/.resolve-ai-bridge")
)
AGENT = os.path.join(HOME, "ResolveConsole.py")
HOST_NAMES = ("resolve", "app", "fusion", "fu", "bmd")


def host_namespace():
    """Every Resolve object visible from this script, wherever Resolve put it."""
    found = {}
    for name in HOST_NAMES:
        value = globals().get(name)
        if value is None:
            value = getattr(builtins, name, None)
        if value is not None:
            found[name] = value
    return found


def main():
    if not os.path.isfile(AGENT):
        print("Resolve AI Bridge is not installed yet.")
        print("Expected: %s" % AGENT)
        print("Run install.py from the downloaded project folder, then restart DaVinci Resolve.")
        return
    if HOME not in sys.path:
        sys.path.insert(0, HOME)

    namespace = host_namespace()
    # The worker autostarts on import using the globals it is given, so hand it
    # a namespace that already carries whatever Resolve exposed to this script.
    worker_globals = dict(globals())
    worker_globals.update(namespace)
    worker_globals["__name__"] = "resolve_ai_bridge_worker"

    try:
        with open(AGENT, encoding="utf-8") as handle:
            source = handle.read()
        exec(compile(source, AGENT, "exec"), worker_globals)
    except Exception as error:  # A menu script that dies silently is the worst case.
        print("\nRESOLVE AI BRIDGE DID NOT START")
        print("%s: %s" % (type(error).__name__, error))
        print("Log: %s" % os.path.join(HOME, "logs", "agent.log"))
        print("Fallback, Workspace > Console with the Py3 tab selected:")
        print(
            '  import os;exec(open(os.path.expanduser'
            '("~/.resolve-ai-bridge/ResolveConsole.py"),encoding="utf-8").read())'
        )
        return

    # Keep the worker reachable from the Console in this Resolve session.
    for key, value in worker_globals.items():
        if key.startswith("__resolve_ai_bridge") or key in ("start_bridge", "stop_bridge"):
            setattr(builtins, key, value)


main()
