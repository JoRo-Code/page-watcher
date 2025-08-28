#!/usr/bin/env python3
"""
Site Update Watcher
-------------------
A tiny Python script to detect changes on a web page and email you when it changes.
Designed to be run via cron every 30 minutes (or whatever you prefer).

Environment variables (required unless noted):
  WATCH_URL           - The full URL to watch.
  RESEND_API_KEY      - Your Resend API key (starts with re_...).
  TO_EMAIL            - Where to send the alert (single address or comma-separated list).
  FROM_EMAIL          - The verified sender identity in Resend (e.g. "Alerts <alerts@yourdomain.com>").

Optional environment variables:
  STATE_DIR           - Directory to store state (default: .watch_state next to the script).
  REQUEST_TIMEOUT     - HTTP timeout in seconds (default: 20).
  SUBJECT_PREFIX      - Prepended to email subject (default: "[Page Watch]").
  USER_AGENT          - Custom User-Agent string for the request.

What it does:
  1) Fetches the page content.
  2) Normalizes the HTML to readable text (strips <script>/<style>, collapses whitespace).
  3) Compares to the previously saved normalized text.
  4) If different, saves the new content and emails you a unified diff via Resend.

Notes:
  • Be a good citizen: check the site's robots.txt and terms of use.
  • If the site is highly dynamic, consider targeting a more stable sub-URL or using a CSS selector.
  • For multiple pages, run separate cron entries with different STATE_DIRs.
"""
from __future__ import annotations

import os
import sys
import json
import time
import hashlib
import html
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import requests
from bs4 import BeautifulSoup
import difflib

RESEND_ENDPOINT = "https://api.resend.com/emails"


def env(key: str, default: str | None = None) -> str:
    val = os.getenv(key, default)
    if val is None:
        print(f"ERROR: Missing required env var {key}", file=sys.stderr)
        sys.exit(2)
    return val


def normalize_html_to_text(html_content: str) -> str:
    """Return readable, stable text from HTML by stripping noisy parts."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script/style and comments
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Get visible text with line breaks
    text = soup.get_text("\n", strip=True)

    # Collapse excessive blank lines
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_previous(state_dir: Path) -> str:
    prev = state_dir / "previous.txt"
    if prev.exists():
        return prev.read_text(encoding="utf-8")
    return ""


def save_current(state_dir: Path, content_text: str) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "previous.txt").write_text(content_text, encoding="utf-8")
    (state_dir / "previous.sha256").write_text(sha256(content_text), encoding="utf-8")


def make_diff(old: str, new: str, *, max_lines: int = 2000) -> str:
    diff_lines = list(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile="previous",
            tofile="current",
            lineterm="",
        )
    )
    if len(diff_lines) > max_lines:
        head = diff_lines[: max_lines // 2]
        tail = diff_lines[-max_lines // 2 :]
        diff_lines = head + ["... (diff truncated) ..."] + tail
    return "\n".join(diff_lines)


def send_email_via_resend(
    api_key: str,
    from_email: str,
    to_emails: List[str],
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": from_email,
        "to": to_emails,
        "subject": subject,
        "html": html_body,
    }
    if text_body:
        payload["text"] = text_body

    r = requests.post(RESEND_ENDPOINT, headers=headers, json=payload, timeout=20)
    try:
        data = r.json()
    except Exception:
        r.raise_for_status()
        raise
    if r.status_code >= 300:
        raise RuntimeError(f"Resend error {r.status_code}: {data}")
    return data


def fetch_url(url: str, timeout: int, user_agent: str | None) -> str:
    headers = {}
    if user_agent:
        headers["User-Agent"] = user_agent
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text


def main() -> int:
    url = env("WATCH_URL")
    api_key = env("RESEND_API_KEY")
    to_email = env("TO_EMAIL")
    from_email = env("FROM_EMAIL")

    state_dir = Path(os.getenv("STATE_DIR", ".watch_state"))
    timeout = int(os.getenv("REQUEST_TIMEOUT", "20"))
    subject_prefix = os.getenv("SUBJECT_PREFIX", "[Page Watch]")
    user_agent = os.getenv("USER_AGENT")

    # Fetch current content
    try:
        html_content = fetch_url(url, timeout=timeout, user_agent=user_agent)
    except Exception as e:
        print(f"ERROR: failed to fetch {url}: {e}", file=sys.stderr)
        return 1

    current_text = normalize_html_to_text(html_content)
    previous_text = load_previous(state_dir)

    if not previous_text:
        # Bootstrap: save and exit quietly
        save_current(state_dir, current_text)
        ts = datetime.now(timezone.utc).isoformat()
        print(f"[{ts}] Initialized state for {url}")
        return 0

    if sha256(previous_text) == sha256(current_text):
        # No change
        return 0

    # Change detected: compute diff and send email
    diff_str = make_diff(previous_text, current_text)
    ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    subject = f"{subject_prefix} Change detected @ {ts}"

    # Build safe HTML email
    safe_diff_html = html.escape(diff_str)
    html_body = f"""
    <div>
      <p>Change detected on <a href=\"{html.escape(url)}\">{html.escape(url)}</a> at {html.escape(ts)}.</p>
      <p><strong>Unified diff</strong> (previous → current):</p>
      <pre style=\"white-space:pre-wrap; word-wrap:break-word;\">{safe_diff_html}</pre>
    </div>
    """

    text_body = f"Change detected on {url} at {ts}.\n\nUnified diff (previous → current):\n\n{diff_str}"

    try:
        res = send_email_via_resend(
            api_key=api_key,
            from_email=from_email,
            to_emails=[e.strip() for e in to_email.split(",") if e.strip()],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )
        print(f"Sent alert via Resend: {res}")
    except Exception as e:
        print(f"ERROR: failed to send email via Resend: {e}", file=sys.stderr)
        # Even if email fails, still update local state to avoid spamming on next run
    finally:
        save_current(state_dir, current_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
