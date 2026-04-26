# Google Bot Account Setup

This repo now supports a repo-managed Google OAuth flow through the custom `google_bot` MCP server. That lets ATLAS use a dedicated Google account, such as `claudiamooney00@gmail.com`, without depending on the Google account connected to your ChatGPT/Codex login.

## What This Setup Does

ATLAS uses the bot account as:

- the Gmail sender identity for outbound mail
- the mailbox identity for reading, archiving, and labeling email
- the organizer calendar for events the bot creates
- a read-only viewer of any human calendars shared to the bot account

## Operating Policy

- `claudiamooney00@gmail.com` is ATLAS's default Google identity.
- Outbound email should be sent only from `claudiamooney00@gmail.com` unless James
  explicitly directs otherwise.
- Bot-created events should be created on Claudia's calendar, not directly on
  `jamesmoon2@gmail.com`.
- When James asks ATLAS to create an event, the default attendee is
  `jamesmoon2@gmail.com` unless he explicitly says not to include himself.
- When Emma should be invited, use `lorzem15@gmail.com`.
- Treat James's calendar as shared read-only context unless James explicitly instructs
  ATLAS to use a different account or calendar.

## One-Time Google Setup

1. Create a Google Cloud Desktop OAuth client with Gmail API and Google Calendar API enabled.
2. Download the OAuth client JSON.
3. Share your calendar to `claudiamooney00@gmail.com`.
4. Share your wife's calendar too if you want ATLAS to check her availability.

The recommended scope set for the bot is:

- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/calendar.readonly`
- `https://www.googleapis.com/auth/calendar.events.owned`

## One-Time ATLAS Setup

### 1. Keep the bot on Codex

Your `.env` should include:

```dotenv
ATLAS_AGENT_PROVIDER=codex
ATLAS_CODEX_HOME=/home/jmooney/atlas-bot/.atlas-codex-home
```

### 2. Install the updated dependencies

From the repo root:

```bash
source venv/bin/activate
pip install -e ".[dev]"
```

### 3. Run the Google bot OAuth setup

Use the OAuth client JSON you downloaded from Google Cloud:

```bash
python3 mcp-servers/google_bot/oauth_setup.py \
  --client-secret-file /absolute/path/to/client_secret.json
```

The setup script will:

- copy the OAuth client JSON into `mcp-servers/credentials/`
- complete the browser-based Google OAuth flow
- save refresh tokens into `mcp-servers/credentials/`
- register a `google_bot` server in `~/.mcp.json`

During the browser login, choose the bot Google account: `claudiamooney00@gmail.com`.

### 4. Verify from the shell

Run:

```bash
python3 check_google_bot_auth.py --expected-email claudiamooney00@gmail.com
```

You should see `Result: ready`.

### 5. Restart the bot

After OAuth setup is complete:

```bash
./restart_atlas_services.sh
```

## Verification in Discord

Run these checks after restart:

1. Ask ATLAS to send a short test email from `claudiamooney00@gmail.com`
2. Ask ATLAS what is already on your calendar tomorrow
3. Ask ATLAS to create a test event on the bot calendar for tomorrow and invite you and your wife
4. Confirm both of you received the invite
5. Ask ATLAS to delete the test event from the bot calendar

If email works but calendar reasoning is missing context, the usual cause is missing calendar sharing to the bot account.
