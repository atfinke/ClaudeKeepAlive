# Claude Code Keepalive

Sends minimal keepalive prompts to preserve Claude.ai 5-hour rate limit reset boundaries. Scheduled to run at minute 55 of every hour, only when no reset boundary exists yet.

**Note:** When the Mac sleeps, launchd runs missed jobs upon wake. Timing may be delayed, but the script includes network stabilization delays and retry logic to ensure reliability.

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
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.claude.keepalive.plist
```

Find python path: `which python` (while in conda env)

To reload after changes:
```bash
launchctl bootout gui/$(id -u)/com.claude.keepalive
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.claude.keepalive.plist
```

## Testing

Test that all accounts are properly configured and can send messages:

```bash
claude_keepalive.py --test
```

This will:
- Verify each account can fetch usage data (tests org_id and session_key)
- Force send a keepalive prompt to each account (tests config_dir and authentication)
- Log all activity to `~/logs/claude_keepalive.log`

## Logs

```bash
tail -f ~/logs/claude_keepalive.log
```

## Wake Scheduling (Optional - Improves Timing)

For better timing reliability when your Mac sleeps, you can schedule automatic wake events to ensure the Mac is awake when :55 jobs run.

### Setup

**1. Configure sudoers (one-time)**
```bash
sudo visudo -f /etc/sudoers.d/claude-keepalive
# Add this line (replace YOUR_USERNAME with your actual username):
YOUR_USERNAME ALL=(ALL) NOPASSWD: /usr/bin/pmset
```

**2. Test manually**
```bash
python schedule_wakes.py
```

This schedules wake events at :55 for the next 24 hours.

**3. Verify scheduled events**
```bash
pmset -g sched
```

You should see 24 wake events listed.

**4. Install automated daily scheduler**
```bash
cp com.claude.keepalive.wake-scheduler.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.claude.keepalive.wake-scheduler.plist
```

This runs `schedule_wakes.py` daily at noon to keep wake events fresh.

**Why this helps:**
- Without wake scheduling: Jobs may run late when Mac sleeps
- With wake scheduling: Jobs run within seconds of :55

**To uninstall wake scheduler:**
```bash
launchctl bootout gui/$(id -u)/com.claude.keepalive.wake-scheduler
rm ~/Library/LaunchAgents/com.claude.keepalive.wake-scheduler.plist
sudo pmset schedule cancelall
```

## Uninstall

```bash
launchctl bootout gui/$(id -u)/com.claude.keepalive
rm ~/Library/LaunchAgents/com.claude.keepalive.plist
```