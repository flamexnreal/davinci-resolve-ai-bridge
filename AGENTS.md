# Resolve AI Bridge Agent Instructions

Read `README.md` and `skills/resolve-ai-editing/SKILL.md` before changing the Python bridge or editing a Resolve project.

## Architecture rules

- `bridge/operations.py` is the single implementation of every Resolve operation. Add new capability there, not in a transport. It must stay standard library only, and must never import `mcp` or `fusionscript`.
- `agent/ResolveConsole.py` may depend only on the standard library, `bridge/operations.py`, and Resolve's injected objects.
- Never import Resolve from `bridge/server.py`, `bridge/client.py`, or `tools/`. Only `bridge/direct.py` loads Resolve's native module, and only in a process that can afford to die.
- `bridge/direct.py` must keep probing in a disposable subprocess before loading the native module in-process. A native module built for another Python can abort the process, and the MCP server has to survive that.
- Every transport failure must fall back to the Console queue rather than raising to the client.
- Never write normal output to stdout from `bridge/`; stdio is reserved for MCP JSON-RPC.
- Preserve token validation on every queue request.
- Preserve the non-blocking Console start. Do not replace the daemon worker with a blocking loop.
- Use absolute installed paths in MCP configuration.

## Setup rules

- Nothing a user copies may contain a personal path. The Console line must stay a single portable line that expands `~` at runtime.
- Keep the three start routes working: direct attach, the Workspace > Scripts launcher, and the Console line.
- Menu launcher files live in `agent/menu/` and are copied by the installer. They must degrade with a readable message when the runtime is missing.

## Honesty rules

- Report what Resolve actually did. `add_image` returning a shorter clip than requested must say so; `insert_title` must report whether the text was really set.
- Be explicit about anything not tested against a real Resolve instance.
- Do not add tools for API calls that are Studio-only or that cannot be verified.

Run the doctor check and the web build after changes when the environment allows it. Keep `00_START_HERE.html` and `src/App.tsx` in agreement.
