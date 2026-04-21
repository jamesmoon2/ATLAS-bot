# Google Bot MCP Server

This MCP server gives ATLAS Gmail and Google Calendar access through a repo-managed Google OAuth flow.

It is designed for a bot-owned Google account, such as `claudiamooney00@gmail.com`, so ATLAS can use a different Google identity than the ChatGPT/Codex account login.

## Setup

1. Create a Google Cloud Desktop OAuth client with Gmail and Calendar APIs enabled.
2. Download the client secret JSON.
3. Run:

```bash
python3 mcp-servers/google_bot/oauth_setup.py --client-secret-file /absolute/path/to/client_secret.json
```

The setup script will:

- copy the OAuth client JSON into `mcp-servers/credentials/`
- complete the browser-based Google OAuth flow
- save refresh tokens under `mcp-servers/credentials/`
- register a `google_bot` server in `~/.mcp.json`

## Scopes

The default scope set is:

- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/calendar.readonly`
- `https://www.googleapis.com/auth/calendar.events.owned`

That supports reading, sending, archiving, and labeling email, plus reading shared calendars and managing events on the bot-owned calendar.
