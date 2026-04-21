# Garmin MCP Server

Repo-managed Garmin Connect MCP server for ATLAS. It replaces the external `uvx` Garmin server
path with a local repo-owned server process and a stricter token policy:

- prefer saved tokens over fresh login attempts
- never try interactive login from the MCP subprocess
- keep the workout-logging compatibility tools ATLAS already expects

## Tools

- `get_profile`
- `get_activities_by_date`
- `get_activities_fordate`
- `get_activity`
- `get_activity_splits`
- `get_activity_hr_in_timezones`
- `get_stats`
- `get_sleep_data`
- `get_hrv_data`
- `get_training_readiness`
- `get_body_battery`
- `get_body_battery_events`

## Setup

1. Install the repo environment with the MCP dependencies.
2. Run:

```bash
python mcp-servers/garmin/oauth_setup.py
```

The setup script will:

- reuse repo-managed Garmin tokens if they already exist
- import valid tokens from `~/.garminconnect` when possible
- only prompt for Garmin credentials if a real refresh is needed
- register the repo-owned `garmin` server in `~/.mcp.json`

## Verify Existing Tokens

```bash
python mcp-servers/garmin/oauth_setup.py --verify-only
```

## Manual Run

```bash
python mcp-servers/garmin/mcp_server.py
```
