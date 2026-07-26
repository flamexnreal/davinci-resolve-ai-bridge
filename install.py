#!/usr/bin/env python3
"""Install Resolve AI Bridge into a stable per-user runtime folder."""

import argparse
import json
import os
import secrets
import shlex
import shutil
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HOME = Path(os.environ.get("RESOLVE_AI_BRIDGE_HOME", Path.home() / ".resolve-ai-bridge")).expanduser()
TOKEN_FILE = HOME / "token.txt"


def fail(message):
    print("\nINSTALL FAILED")
    print(message)
    raise SystemExit(1)


def copy_runtime():
    HOME.mkdir(parents=True, exist_ok=True)
    for folder in ("inbox", "outbox", "logs"):
        (HOME / folder).mkdir(exist_ok=True)

    source_agent = ROOT / "agent" / "ResolveConsole.py"
    if not source_agent.exists():
        fail("agent/ResolveConsole.py is missing. Download or clone the complete repository.")
    shutil.copy2(source_agent, HOME / "ResolveConsole.py")

    source_bridge = ROOT / "bridge"
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


def venv_python():
    return HOME / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def install_dependencies(skip=False):
    target = HOME / ".venv"
    if not venv_python().exists():
        print("[1/4] Creating the private Python environment...")
        venv.EnvBuilder(with_pip=True, clear=False).create(str(target))
    else:
        print("[1/4] Reusing the private Python environment...")
    if skip:
        print("      Dependency install skipped by request.")
        return
    requirements = ROOT / "requirements.txt"
    if not requirements.exists():
        fail("requirements.txt is missing.")
    print("[2/4] Installing the MCP dependency...")
    command = [str(venv_python()), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)]
    try:
        subprocess.run(command, check=True)
    except (subprocess.CalledProcessError, OSError) as exc:
        fail("pip could not install requirements.txt. Check your internet connection and rerun the installer.\n%s" % exc)


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
    (HOME / "claude-server-entry.json").write_text(json.dumps(claude_entry, indent=2) + "\n", encoding="utf-8")
    (HOME / "mcp-config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    installed_agent = (HOME / "ResolveConsole.py").resolve()
    if os.name == "nt":
        console_line = 'exec(open(r"%s", encoding="utf-8").read())' % installed_agent
    else:
        console_line = 'exec(open("%s", encoding="utf-8").read())' % installed_agent
    (HOME / "console-command.txt").write_text(console_line + "\n", encoding="utf-8")
    if os.name == "nt":
        launch = subprocess.list2cmdline([entry["command"], entry["args"][0]])
    else:
        launch = "%s %s" % (shlex.quote(entry["command"]), shlex.quote(entry["args"][0]))
    codex_line = "codex mcp add resolve-ai-bridge --env RESOLVE_AI_BRIDGE_TOKEN=%s -- %s" % (token, launch)
    (HOME / "codex-command.txt").write_text(codex_line + "\n", encoding="utf-8")
    if os.name == "nt":
        claude_line = (
            '$entry = Get-Content -Raw "%s"; '
            "claude mcp add-json resolve-ai-bridge $entry --scope user"
        ) % (HOME / "claude-server-entry.json")
    else:
        claude_line = (
            'claude mcp add-json resolve-ai-bridge "$(cat %s)" --scope user'
            % shlex.quote(str(HOME / "claude-server-entry.json"))
        )
    (HOME / "claude-command.txt").write_text(claude_line + "\n", encoding="utf-8")
    return entry, config, console_line, claude_line, codex_line


def install_skills():
    source = ROOT / "skills" / "resolve-ai-editing" / "SKILL.md"
    if not source.exists():
        return []
    installed = []
    targets = [
        Path.home() / ".claude" / "skills" / "resolve-ai-editing" / "SKILL.md",
        Path.home() / ".codex" / "skills" / "resolve-ai-editing" / "SKILL.md",
    ]
    for target in targets:
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
    print("Remove the resolve-ai-bridge entry from your AI client's MCP settings separately.")


def main():
    parser = argparse.ArgumentParser(description="Install Resolve AI Bridge")
    parser.add_argument("--rotate-token", action="store_true", help="Create a new token and rewrite MCP snippets")
    parser.add_argument("--skip-deps", action="store_true", help="Copy files without running pip")
    parser.add_argument("--uninstall", action="store_true", help="Remove the installed per-user runtime")
    args = parser.parse_args()

    if args.uninstall:
        remove_runtime()
        return
    if sys.version_info < (3, 10):
        fail("Python 3.10 or newer is required. Current: %s" % sys.version.split()[0])

    print("\nResolve AI Bridge installer")
    print("Runtime: %s\n" % HOME)
    copy_runtime()
    print("[0/4] Copied the Console agent and MCP bridge.")
    token = get_token(rotate=args.rotate_token)
    install_dependencies(skip=args.skip_deps)
    print("[3/4] Writing the authenticated MCP configuration...")
    _entry, _config, console_line, claude_line, codex_line = write_configs(token)
    skill_paths = install_skills()
    print("[4/4] Installed the Resolve editing skill in standard skill locations.")

    print("\n" + "=" * 72)
    print("INSTALL COMPLETE")
    print("\n1. Open Resolve and your project.")
    print("2. Open Workspace > Console and select Py3.")
    print("3. Paste this exact line:\n")
    print(console_line)
    print("\n4. Copy the MCP config printed by Resolve into your AI client.")
    print("   A filled copy is also saved at: %s" % (HOME / "mcp-config.json"))
    print("\nClaude Code users can run this exact command in a normal terminal:\n")
    print(claude_line)
    print("\nCodex users can run this exact command in a normal terminal:\n")
    print(codex_line)
    print("\nToken: %s" % token)
    print("Keep this token private. Use --rotate-token if it is exposed.")
    if not shutil.which("node"):
        print("\nHEAVILY RECOMMENDED: Install the current Node.js LTS release for Remotion.")
        print("Then follow the Remotion section in 00_START_HERE.html.")
    if skill_paths:
        print("\nResolve editing skill copies:")
        for path in skill_paths:
            print("  %s" % path)
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()