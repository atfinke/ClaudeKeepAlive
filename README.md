# Claude Code Keepalive

Sends minimal keepalive prompts to preserve Claude.ai 5-hour rate limit reset boundaries. Runs at minute 59 of every hour, only when no reset boundary exists yet.

## Requirements

- macOS
- Python 3.11+ with `curl_cffi`
- [Claude Code CLI](https://github.com/anthropics/claude-code)

## Setup

### 1. Install

```bash
conda create -n claude-keepalive python=3.11
conda activate claude-keepalive
pip install curl_cffi
```

### 2. Configure Accounts

```bash
# Create directories and authenticate
mkdir -p ~/.claude-account-1
CLAUDE_CONFIG_DIR=~/.claude-account-1 claude
# /login → authenticate → exit
```

### 3. Get Credentials

For each account, from browser DevTools (Network tab):
- `org_id`: Extract from `/api/organizations/{org_id}/usage` URL
- `session_key`: From Cookie header, value after `sessionKey=`

### 4. Create Config

```bash
cp config.example.json config.json
# Edit config.json with your credentials
```

### 5. Install launchd Agent

```bash
cp com.claude.keepalive.example.plist com.claude.keepalive.plist
# Edit plist: update python path and script path
cp com.claude.keepalive.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.claude.keepalive.plist
```

Find python path: `which python` (while in conda env)

## Logs

```bash
tail -f ~/logs/claude_keepalive.log
```

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.claude.keepalive.plist
rm ~/Library/LaunchAgents/com.claude.keepalive.plist
```