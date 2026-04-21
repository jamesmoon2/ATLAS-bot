# WHOOP MCP Server

Repo-managed WHOOP MCP server for ATLAS. It exposes provider-agnostic high-level tools so both
Claude Code and Codex can query WHOOP using the same names:

- `get_daily_sleep`
- `get_daily_recovery`
- `get_daily_cycle`
- `get_daily_workouts`

## Setup

1. Install the bot in a Python environment that includes the MCP dependencies.
2. Run:

```bash
python mcp-servers/whoop/oauth_setup.py
```

3. Complete the WHOOP OAuth flow in the browser.
4. Restart ATLAS and Claude Code after setup.

The setup script stores ignored files under `mcp-servers/credentials/`:

- `whoop-oauth.keys.json`
- `whoop-tokens.json`

It also updates `~/.mcp.json` so Claude Code uses the repo-owned WHOOP server, while Codex gets
the same server through ATLAS-managed config generation in `agent_runner.py`.

## OAuth Notes

- Redirect URIs must exactly match the URI registered in the WHOOP developer dashboard.
- The OAuth flow requests `offline` so the server receives a refresh token.
- Refresh tokens rotate on use, so the latest refresh token from each response is persisted
  immediately.

## Running Manually

```bash
python mcp-servers/whoop/mcp_server.py
```
