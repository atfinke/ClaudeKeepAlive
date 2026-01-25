#!/usr/bin/env python3
"""
Claude Code Keepalive
Preserves 5-hour rate limit reset boundaries by sending minimal prompts when needed.
"""
import os
import sys
import subprocess
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict
from curl_cffi import requests

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config.json"


def load_config() -> Dict:
    """Load configuration from config.json."""
    with open(CONFIG_PATH) as f:
        return json.load(f)


def log(message: str, log_file: Optional[str]) -> None:
    """Write log message if logging is enabled."""
    if log_file:
        timestamp = datetime.now(timezone.utc).isoformat()
        log_path = Path(log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(f"{timestamp} - {message}\n")


def fetch_usage(org_id: str, session_key: str, log_file: Optional[str], test_mode: bool = False, account_name: str = "") -> Optional[Dict]:
    """Fetch usage data from Claude API with retry logic for network issues."""
    import time

    url = f"https://claude.ai/api/organizations/{org_id}/usage"

    headers = {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Cookie": f"sessionKey={session_key}",
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            log(f"[{account_name}] Fetch attempt {attempt + 1}/{max_retries} - calling {url}", log_file)
            response = requests.get(
                url,
                headers=headers,
                timeout=10,
                impersonate="chrome110",
            )
            response.raise_for_status()
            data = response.json()

            log(f"[{account_name}] ✓ Fetch successful (HTTP {response.status_code}, attempt {attempt + 1}/{max_retries})", log_file)
            if test_mode:
                log(f"[{account_name}] ✓ API credentials valid (HTTP {response.status_code})", log_file)

            return data
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s
                log(f"[{account_name}] ✗ Fetch attempt {attempt + 1}/{max_retries} failed, retrying in {wait_time}s: {e}", log_file)
                time.sleep(wait_time)
            else:
                log(f"[{account_name}] ✗ Failed to fetch usage after {max_retries} attempts: {e}", log_file)
                return None


def should_send_keepalive(usage: Dict, account_name: str, log_file: Optional[str], keepalive_modes: list, force: bool = False) -> bool:
    """Determine if keepalive prompt should be sent based on configured modes."""
    needs_keepalive = False

    for mode in keepalive_modes:
        mode_data = usage.get(mode, {})
        resets_at = mode_data.get("resets_at") if mode_data else None

        if force:
            log(f"[{account_name}] Test mode - forcing keepalive for {mode} (reset boundary: {resets_at or 'none'})", log_file)
            needs_keepalive = True
        elif not resets_at:
            log(f"[{account_name}] No {mode} reset boundary - needs keepalive", log_file)
            needs_keepalive = True
        else:
            log(f"[{account_name}] {mode} reset boundary exists: {resets_at}", log_file)

    return needs_keepalive


def send_prompt(config_dir: Path, claude_bin: str, model: str, prompt: str, log_file: Optional[str]) -> bool:
    """Send minimal prompt to one account."""
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = str(config_dir)

    cmd = [claude_bin, "-p", prompt, "--model", model]
    log(f"[{config_dir.name}] Sending prompt - cmd={' '.join(cmd)}, config_dir={config_dir}", log_file)

    try:
        result = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
        success = result.returncode == 0
        if not success:
            stderr_preview = result.stderr.decode('utf-8', errors='ignore')[:200] if result.stderr else ""
            log(f"[{config_dir.name}] ✗ Failed with code {result.returncode}: {stderr_preview}", log_file)
        else:
            stdout_preview = result.stdout.decode('utf-8', errors='ignore')[:100] if result.stdout else ""
            log(f"[{config_dir.name}] ✓ Sent prompt successfully: {stdout_preview}", log_file)
        return success
    except subprocess.TimeoutExpired:
        log(f"[{config_dir.name}] ✗ Timeout after 30s", log_file)
        return False
    except Exception as e:
        log(f"[{config_dir.name}] ✗ Error: {e}", log_file)
        return False


def process_account(account: Dict, config: Dict, test_mode: bool = False) -> None:
    """Process a single account."""
    name = account["name"]
    config_dir = Path(account["config_dir"]).expanduser()
    org_id = account["org_id"]
    session_key = account["session_key"]
    keepalive_modes = account.get("keepalive_modes", ["five_hour"])
    log_file = config.get("log_file")

    if not org_id or not session_key:
        log(f"[{name}] Missing org_id or session_key", log_file)
        return

    if not config_dir.exists():
        log(f"[{name}] Config directory missing: {config_dir}", log_file)
        return

    log(f"[{name}] Checking modes: {keepalive_modes}", log_file)

    usage = fetch_usage(org_id, session_key, log_file, test_mode=test_mode, account_name=name)
    if not usage:
        return

    if not should_send_keepalive(usage, name, log_file, keepalive_modes, force=test_mode):
        return

    send_prompt(
        config_dir,
        config.get("claude_bin", "/usr/local/bin/claude"),
        config.get("model", "claude-haiku-4-5"),
        config.get("prompt", "hi"),
        log_file,
    )


def main() -> None:
    """Main execution flow."""
    import time

    parser = argparse.ArgumentParser(
        description="Claude Code keepalive automation"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: force send keepalive to all accounts regardless of reset boundary",
    )
    args = parser.parse_args()

    config = load_config()
    log_file = config.get("log_file")

    # Detect if running from launchd (non-interactive)
    is_launchd = not sys.stdin.isatty()
    log(f"Execution context - test_mode={args.test}, is_tty={not is_launchd}, pid={os.getpid()}", log_file)

    # When running from launchd after wake, give network a few seconds to stabilize
    if not args.test and is_launchd:
        log("Running from launchd (non-interactive) - waiting 5s for network to stabilize", log_file)
        time.sleep(5)
        log("Network stabilization wait complete", log_file)

    mode = "test mode" if args.test else "normal mode"
    log(f"Starting keepalive check ({mode})", log_file)

    for account in config.get("accounts", []):
        process_account(account, config, test_mode=args.test)

    log("Keepalive complete", log_file)


if __name__ == "__main__":
    main()
