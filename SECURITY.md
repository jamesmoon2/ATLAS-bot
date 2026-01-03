# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in ATLAS Bot, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email the maintainer directly or use GitHub's private vulnerability reporting
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes

## Security Considerations

### What ATLAS Bot Has Access To

- **Filesystem**: Read/write access to configured paths
- **Discord**: Bot token with message permissions
- **Claude Code CLI**: Executes with user's Claude authentication

### Best Practices

1. **Keep `.env` secure**: Never commit tokens or secrets
2. **Restrict file paths**: Configure `VAULT_PATH` to limit access
3. **Review tool permissions**: Audit `CHANNEL_PERMISSIONS` in bot.py
4. **Use private Discord server**: Limit who can interact with the bot
5. **Monitor sessions**: Periodically review `sessions/` directory

### Known Limitations

- Bot executes Claude Code with same permissions as the user running it
- Pre-approved tools can read/write files without per-action confirmation
- Session history is stored locally in plaintext

## Updates

Security updates will be released as patch versions and announced in the changelog.
