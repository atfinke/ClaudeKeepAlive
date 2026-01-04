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
    """Fetch usage data from Claude API."""
    url = f"https://claude.ai/api/organizations/{org_id}/usage"

    headers = {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Cookie": f"sessionKey={session_key}",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=10,
            impersonate="chrome110",
        )
        response.raise_for_status()
        data = response.json()

        if test_mode:
            log(f"[{account_name}] ✓ API credentials valid (HTTP {response.status_code})", log_file)

        return data
    except Exception as e:
        log(f"[{account_name}] Failed to fetch usage: {e}", log_file)
        return None


def should_send_keepalive(usage: Dict, account_name: str, log_file: Optional[str], force: bool = False) -> bool:
    """Determine if keepalive prompt should be sent."""
    five_hour = usage.get("five_hour", {})
    resets_at = five_hour.get("resets_at")

    if force:
        log(f"[{account_name}] Test mode - forcing keepalive (reset boundary: {resets_at or 'none'})", log_file)
        return True

    if not resets_at:
        log(f"[{account_name}] No reset boundary - sending keepalive", log_file)
        return True

    log(f"[{account_name}] Reset boundary exists: {resets_at}", log_file)
    return False


def send_prompt(config_dir: Path, claude_bin: str, model: str, prompt: str, log_file: Optional[str]) -> bool:
    """Send minimal prompt to one account."""
    env = os.environ.copy()
    env["CLAUDE_CONFIG_DIR"] = str(config_dir)

    try:
        result = subprocess.run(
            [claude_bin, "-p", prompt, "--model", model],
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
            log(f"[{config_dir.name}] Failed with code {result.returncode}: {stderr_preview}", log_file)
        else:
            log(f"[{config_dir.name}] Sent prompt: success", log_file)
        return success
    except subprocess.TimeoutExpired:
        log(f"[{config_dir.name}] Timeout", log_file)
        return False
    except Exception as e:
        log(f"[{config_dir.name}] Error: {e}", log_file)
        return False


def process_account(account: Dict, config: Dict, test_mode: bool = False) -> None:
    """Process a single account."""
    name = account["name"]
    config_dir = Path(account["config_dir"]).expanduser()
    org_id = account["org_id"]
    session_key = account["session_key"]
    log_file = config.get("log_file")

    if not org_id or not session_key:
        log(f"[{name}] Missing org_id or session_key", log_file)
        return

    if not config_dir.exists():
        log(f"[{name}] Config directory missing: {config_dir}", log_file)
        return

    usage = fetch_usage(org_id, session_key, log_file, test_mode=test_mode, account_name=name)
    if not usage:
        return

    if not should_send_keepalive(usage, name, log_file, force=test_mode):
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

    mode = "test mode" if args.test else "normal mode"
    log(f"Starting keepalive check ({mode})", log_file)

    for account in config.get("accounts", []):
        process_account(account, config, test_mode=args.test)

    log("Keepalive complete", log_file)


if __name__ == "__main__":
    main()
