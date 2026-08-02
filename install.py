#!/usr/bin/env python3
"""Install Resolve AI Bridge into a stable per-user runtime folder."""

import argparse
import json
import os
import platform
import secrets
import shlex
import shutil
import subprocess
import sys
import venv
from pathlib import Path


VERSION = "1.2.0"
ROOT = Path(__file__).resolve().parent
HOME = Path(os.environ.get("RESOLVE_AI_BRIDGE_HOME", Path.home() / ".resolve-ai-bridge")).expanduser()
TOKEN_FILE = HOME / "token.txt"

MENU_FOLDER = "Resolve AI Bridge"
# Stray scripts from earlier hand-made experiments that clutter Workspace >
# Scripts. The installer moves any it finds out of Resolve's Utility folder into
# a reversible backup rather than deleting them outright. Matching is by exact
# name or by these prefixes.
SUPERSEDED_SCRIPT_NAMES = {
    "Resolve AI Bridge.py",
    "Start Resolve AI Bridge.py",
    "add_explosion_overlay.py",
}
SUPERSEDED_SCRIPT_PREFIXES = ("RFAIB_",)
CONSOLE_LINE = (
    'import os;exec(open(os.path.expanduser("~/.resolve-ai-bridge/ResolveConsole.py"),'
    'encoding="utf-8").read())'
)


def fail(message):
    print("\nINSTALL FAILED")
    print(message)
    raise SystemExit(1)


def venv_python():
    return HOME / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


# --------------------------------------------------------------- runtime copy


def copy_runtime():
    HOME.mkdir(parents=True, exist_ok=True)
    for folder in ("inbox", "outbox", "logs"):
        (HOME / folder).mkdir(exist_ok=True)

    source_agent = ROOT / "agent" / "ResolveConsole.py"
    if not source_agent.exists():
        fail("agent/ResolveConsole.py is missing. Download or clone the complete repository.")
    shutil.copy2(source_agent, HOME / "ResolveConsole.py")

    source_bridge = ROOT / "bridge"
    if not (source_bridge / "operations.py").exists():
        fail("bridge/operations.py is missing. Download or clone the complete repository.")
    target_bridge = HOME / "bridge"
    if target_bridge.exists():
        shutil.rmtree(target_bridge)
    shutil.copytree(
        source_bridge,
        target_bridge,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )


def get_token(rotate=False):
    if TOKEN_FILE.exists() and not rotate:
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = "rab_" + secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(token + "\n", encoding="utf-8")
    try:
        os.chmod(str(TOKEN_FILE), 0o600)
    except OSError:
        pass
    return token


def install_dependencies(skip=False):
    target = HOME / ".venv"
    if not venv_python().exists():
        print("[1/5] Creating the private Python environment...")
        venv.EnvBuilder(with_pip=True, clear=False).create(str(target))
    else:
        print("[1/5] Reusing the private Python environment...")
    if skip:
        print("      Dependency install skipped by request.")
        return
    requirements = ROOT / "requirements.txt"
    if not requirements.exists():
        fail("requirements.txt is missing.")
    print("[2/5] Installing the MCP dependency...")
    command = [
        str(venv_python()),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "-r",
        str(requirements),
    ]
    try:
        subprocess.run(command, check=True)
    except (subprocess.CalledProcessError, OSError) as exc:
        fail(
            "pip could not install requirements.txt. Check your internet connection and rerun the "
            "installer.\n%s" % exc
        )


def write_configs(token):
    entry = {
        "command": str(venv_python().resolve()),
        "args": [str((HOME / "bridge" / "server.py").resolve())],
        "env": {"RESOLVE_AI_BRIDGE_TOKEN": token},
    }
    config = {"mcpServers": {"resolve-ai-bridge": entry}}
    (HOME / "mcp-server-entry.json").write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
    claude_entry = dict(entry)
    claude_entry["type"] = "stdio"
    (HOME / "claude-server-entry.json").write_text(
        json.dumps(claude_entry, indent=2) + "\n", encoding="utf-8"
    )
    (HOME / "mcp-config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    # One portable line. os.path.expanduser resolves the home folder inside
    # Resolve's own interpreter, so there is never a user name to substitute
    # and the same text works on macOS, Windows, and Linux.
    (HOME / "console-command.txt").write_text(CONSOLE_LINE + "\n", encoding="utf-8")

    if os.name == "nt":
        launch = subprocess.list2cmdline([entry["command"], entry["args"][0]])
        claude_line = (
            '$entry = Get-Content -Raw "%s"; '
            "claude mcp add-json resolve-ai-bridge $entry --scope user"
        ) % (HOME / "claude-server-entry.json")
    else:
        launch = "%s %s" % (shlex.quote(entry["command"]), shlex.quote(entry["args"][0]))
        claude_line = 'claude mcp add-json resolve-ai-bridge "$(cat %s)" --scope user' % shlex.quote(
            str(HOME / "claude-server-entry.json")
        )
    codex_line = "codex mcp add resolve-ai-bridge --env RESOLVE_AI_BRIDGE_TOKEN=%s -- %s" % (
        token,
        launch,
    )
    (HOME / "codex-command.txt").write_text(codex_line + "\n", encoding="utf-8")
    (HOME / "claude-command.txt").write_text(claude_line + "\n", encoding="utf-8")
    return entry, config, claude_line, codex_line


# ------------------------------------------------------- Resolve Scripts menu


def resolve_script_roots():
    """Per-user folders DaVinci Resolve scans for Workspace > Scripts entries.

    Taken from Blackmagic's own scripting README. Resolve reads these once at
    startup, so a new entry appears after the next Resolve launch.
    """
    home = Path.home()
    if sys.platform.startswith("darwin"):
        return [home / "Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts"]
    if os.name == "nt":
        appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
        return [
            appdata / "Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts",
            appdata / "Blackmagic Design/DaVinci Resolve/Fusion/Scripts",
        ]
    return [
        home / ".local/share/DaVinciResolve/Fusion/Scripts",
        Path("/opt/resolve/Fusion/Scripts"),
    ]


def _is_superseded_script(name):
    if name in SUPERSEDED_SCRIPT_NAMES:
        return True
    return any(name.startswith(prefix) for prefix in SUPERSEDED_SCRIPT_PREFIXES)


def tidy_superseded_scripts():
    """Move earlier stray Resolve scripts into a reversible backup folder.

    Keeps Workspace > Scripts > Utility clean without destroying work: anything
    matched is moved under HOME/removed-scripts-backup, never deleted, so the
    user can restore or bin it themselves.
    """
    backup = HOME / "removed-scripts-backup"
    moved = []
    for root in resolve_script_roots():
        utility = root / "Utility"
        if not utility.is_dir():
            continue
        for entry in utility.iterdir():
            if entry.is_file() and _is_superseded_script(entry.name):
                try:
                    backup.mkdir(parents=True, exist_ok=True)
                    target = backup / entry.name
                    if target.exists():
                        target = backup / ("%s.%d%s" % (entry.stem, int(entry.stat().st_mtime), entry.suffix))
                    shutil.move(str(entry), str(target))
                    moved.append((str(entry), str(target)))
                except OSError:
                    continue
    return moved


def install_menu_scripts():
    """Copy the one-click launchers into Workspace > Scripts > Utility."""
    source = ROOT / "agent" / "menu"
    if not source.is_dir():
        return []
    installed = []
    roots = resolve_script_roots()
    existing = [root for root in roots if root.is_dir()]
    targets = existing or roots[:1]
    for root in targets:
        folder = root / "Utility" / MENU_FOLDER
        try:
            folder.mkdir(parents=True, exist_ok=True)
            for script in sorted(source.glob("*.py")):
                shutil.copy2(script, folder / script.name)
            installed.append(str(folder))
        except OSError:
            continue
    return installed


def remove_menu_scripts():
    removed = []
    for root in resolve_script_roots():
        folder = root / "Utility" / MENU_FOLDER
        if folder.is_dir():
            try:
                shutil.rmtree(folder)
                removed.append(str(folder))
            except OSError:
                pass
    return removed


def install_skills():
    source = ROOT / "skills" / "resolve-ai-editing" / "SKILL.md"
    if not source.exists():
        return []
    installed = []
    for target in (
        Path.home() / ".claude" / "skills" / "resolve-ai-editing" / "SKILL.md",
        Path.home() / ".codex" / "skills" / "resolve-ai-editing" / "SKILL.md",
    ):
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            installed.append(str(target))
        except OSError:
            pass
    runtime_skill = HOME / "skills" / "resolve-ai-editing" / "SKILL.md"
    runtime_skill.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, runtime_skill)
    installed.append(str(runtime_skill))
    return installed


def probe_direct_attach():
    """Ask the private venv Python whether it can attach to Resolve on its own."""
    python = venv_python()
    if not python.exists():
        return {"ok": False, "loadable": False, "reason": "The private Python is not installed yet."}
    source = (
        "import json,sys;"
        "sys.path.insert(0, %r);"
        "from bridge import direct;"
        "sys.stdout.write(json.dumps(direct.probe_in_process()))" % str(HOME)
    )
    try:
        finished = subprocess.run(
            [str(python), "-c", source],
            capture_output=True,
            text=True,
            timeout=25,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        )
        return json.loads((finished.stdout or "").strip())
    except Exception as exc:
        return {"ok": False, "loadable": False, "reason": str(exc)}


def remove_runtime():
    if not HOME.exists():
        print("Nothing to remove at %s" % HOME)
        return
    answer = input("Delete %s and its token? Type DELETE to confirm: " % HOME).strip()
    if answer != "DELETE":
        print("Uninstall cancelled.")
        return
    shutil.rmtree(HOME)
    print("Removed %s" % HOME)
    for folder in remove_menu_scripts():
        print("Removed %s" % folder)
    print("Remove the resolve-ai-bridge entry from your AI client's MCP settings separately.")


def main():
    parser = argparse.ArgumentParser(description="Install Resolve AI Bridge %s" % VERSION)
    parser.add_argument("--rotate-token", action="store_true", help="Create a new token and rewrite MCP snippets")
    parser.add_argument("--skip-deps", action="store_true", help="Copy files without running pip")
    parser.add_argument("--no-menu", action="store_true", help="Skip the Workspace > Scripts menu entries")
    parser.add_argument("--uninstall", action="store_true", help="Remove the installed per-user runtime")
    args = parser.parse_args()

    if args.uninstall:
        remove_runtime()
        return
    if sys.version_info < (3, 10):
        fail("Python 3.10 or newer is required. Current: %s" % sys.version.split()[0])

    print("\nResolve AI Bridge installer %s" % VERSION)
    print("Runtime: %s" % HOME)
    print("System:  %s %s\n" % (platform.system(), platform.release()))

    copy_runtime()
    print("[0/5] Copied the Console worker and MCP bridge.")
    token = get_token(rotate=args.rotate_token)
    install_dependencies(skip=args.skip_deps)
    print("[3/5] Writing the authenticated MCP configuration...")
    _entry, _config, claude_line, codex_line = write_configs(token)
    menu_paths = [] if args.no_menu else install_menu_scripts()
    tidied = [] if args.no_menu else tidy_superseded_scripts()
    print("[4/5] %s" % (
        "Installed the Workspace > Scripts menu entries."
        if menu_paths
        else "Skipped the Workspace > Scripts menu entries."
    ))
    if tidied:
        print("      Moved %d superseded script(s) out of the Scripts menu into %s"
              % (len(tidied), HOME / "removed-scripts-backup"))
    skill_paths = install_skills()
    print("[5/5] Installed the Resolve editing skill in standard skill locations.")

    direct = probe_direct_attach()

    print("\n" + "=" * 72)
    print("INSTALL COMPLETE")

    print("\nSTEP 1  Connect your AI client. Nothing here needs editing.")
    print("        Claude Code, in a normal terminal:")
    print("          %s" % claude_line)
    print("        Codex, in a normal terminal:")
    print("          %s" % codex_line)
    print("        Antigravity or Cursor, paste this file's contents into the MCP raw config:")
    print("          %s" % (HOME / "mcp-config.json"))

    print("\nSTEP 2  Start Resolve.")
    if direct.get("ok"):
        print("        Direct attach works on this computer, so there is nothing to start")
        print("        inside Resolve. Open a project and your AI is connected.")
        print("        Detected: %s %s" % (direct.get("product", ""), direct.get("version", "")))
    else:
        print("        Resolve was not running during this check, so a direct attach could not be")
        print("        confirmed. Your AI may connect with no further steps. If it reports the")
        print("        bridge as offline, use the one-click launcher below.")
        if direct.get("reason"):
            print("        Check detail: %s" % direct["reason"])

    if menu_paths:
        print("\nSTEP 3  Console launcher helper:")
        print("        Restart DaVinci Resolve once, then choose")
        print("        Workspace > Scripts > Resolve AI Bridge > Start AI Bridge.")
        print("        It prints the exact Py3 Console command into Resolve's Console for easy copy-pasting.")
        for path in menu_paths:
            print("          %s" % path)

    print("\n        Direct Console command (Workspace > Console, Py3 tab):")
    print("          %s" % CONSOLE_LINE)
    print("        The same line is saved at %s" % (HOME / "console-command.txt"))

    print("\nVERIFY  python3 tools/doctor.py")
    print("        Then ask your AI: \"Call resolve_status and tell me what is open.\"")

    print("\nToken: %s" % token)
    print("Keep this token private. Use --rotate-token if it is ever exposed.")
    if not shutil.which("node"):
        print("\nHEAVILY RECOMMENDED: install the current Node.js LTS release for Remotion.")
        print("Then follow the Remotion section in 00_START_HERE.html.")
    if skill_paths:
        print("\nResolve editing skill copies:")
        for path in skill_paths:
            print("  %s" % path)
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
