# Troubleshooting

Run `python3 tools/doctor.py` on macOS or `py tools/doctor.py` on Windows before changing files.

## Installed Console Agent Is Missing

Run the installer again from the complete downloaded repository. The required installed filename is:

```text
~/.resolve-ai-bridge/ResolveConsole.py
```

The repository folder may be renamed. Do not rename the installed agent file.

## Console Says Resolve API Was Not Found

1. Confirm the command was pasted into Resolve's own Console.
2. Confirm the Console language is Py3.
3. Confirm a normal Resolve project is open.
4. Paste the exact line from `~/.resolve-ai-bridge/console-command.txt`.
5. Copy the full Console error into a private support request. Do not include the token.

## Resolve Becomes Unresponsive

This version starts a daemon thread and should return control immediately. If the Console remains busy, restart Resolve and confirm the installed file is the current `ResolveConsole.py`. Do not paste an older agent that ends in a blocking polling loop.

## Agent Is Offline

The MCP process treats the agent as offline when `agent.json` is missing or older than 25 seconds.

1. Keep Resolve open.
2. Check the Console for `RESOLVE AI BRIDGE READY`.
3. Run the Console line again. A running bridge prints its banner without starting a second worker.
4. Run doctor again.

## Token Mismatch

The MCP client and agent are using different tokens.

1. Open `~/.resolve-ai-bridge/mcp-config.json`.
2. Replace the old `resolve-ai-bridge` entry in the provider's MCP config.
3. Restart the provider.
4. Run the Console line again.

Rotate a leaked token with:

```bash
python3 install.py --rotate-token
```

## MCP Server Does Not Appear

- Use absolute paths from generated `mcp-config.json`.
- Preserve valid JSON commas and braces when merging with existing servers.
- Confirm the private venv Python exists.
- Fully restart the AI client after changing its MCP config.
- Check the AI client's MCP log for the first Python exception.

Do not run `bridge/server.py` in a visible terminal and type into it. The AI client starts it and communicates over stdio.

## An Edit Tool Returns False

Resolve rejected the operation. Call `timeline_overview` again and check the open timeline, ids, frame rate, and permissions. Do not assume the edit happened.

Some Resolve APIs differ by version. Include the Resolve version, operating system, exact tool call, returned error, and a redacted `logs/agent.log` when reporting a bug.

## Remotion Command Is Not Found

1. Install the current Node.js LTS release.
2. Close and reopen the terminal.
3. Confirm `node --version` and `npm --version` work.
4. Run Remotion commands from the Remotion project folder, not the Resolve Console.