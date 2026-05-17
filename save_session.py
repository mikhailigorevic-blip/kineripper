#!/usr/bin/env python3
"""
save_session.py — one-time browser session capture for kineripper.

Usage:
    python save_session.py <login-url>

Opens a visible Chromium window at the given URL. Log in to the course
platform manually, open one lesson with a video and let it play for at
least ~10 seconds (so the Kinescope CDN cookies are set), then close the
browser. The cookie jar is saved to ~/.kineripper/session.json.

The script never reads, transmits, or stores your username or password.
Only the resulting browser cookies are persisted.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright


DEFAULT_SESSION = Path.home() / ".kineripper" / "session.json"


async def run(start_url: str, session_path: Path) -> int:
    session_path.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--autoplay-policy=no-user-gesture-required"],
        )
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx.new_page()
        await page.goto(start_url)

        print()
        print("=" * 72)
        print("  Browser window is open.")
        print()
        print("  1. Log in with your username and password.")
        print("  2. Open one lesson with a video and press Play.")
        print("     Let it play for at least 10 seconds.")
        print("  3. Close the browser window when done.")
        print()
        print("  Your credentials are NOT seen by this script.")
        print("  Only the browser cookies will be saved.")
        print("=" * 72)
        print()

        # wait until the user closes the window
        try:
            await page.wait_for_event("close", timeout=0)
        except Exception:
            pass

        try:
            await ctx.storage_state(path=str(session_path))
        except Exception as exc:
            print(f"Failed to write session file: {exc}", file=sys.stderr)
            await browser.close()
            return 1

        await browser.close()

    print(f"Session saved to {session_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-time login capture for kineripper.",
    )
    parser.add_argument(
        "url",
        help="Login or home URL of your course platform, e.g. https://learn.example.com",
    )
    parser.add_argument(
        "--session",
        type=Path,
        default=DEFAULT_SESSION,
        help=f"Where to write the session JSON (default: {DEFAULT_SESSION})",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.url, args.session))


if __name__ == "__main__":
    sys.exit(main())
