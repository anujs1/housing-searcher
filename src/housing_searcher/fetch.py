"""Capture a Facebook group's feed using *your own* logged-in browser session.

This is the personal-use, low-footprint design:

  * It reuses a session you created by logging in yourself (``login``), so it
    never performs an automated login — the single biggest bot-detection
    trigger.
  * It runs headed by default so you can watch it, and supports a ``manual``
    mode where you do the scrolling and it just records what your own browsing
    already loaded (no extra automated requests at all).
  * It only reads the group feed's GraphQL responses and writes them to disk.
    Parsing and extraction happen offline, so you never re-fetch to re-parse.

It does not, and should not, be pointed at groups you are not a member of, run
at high volume, or used to collect data you intend to redistribute. See the
README for the terms-of-service and risk discussion.
"""

from __future__ import annotations

import json
import random
import time
from typing import Any


def group_url(group_id: str) -> str:
    return f"https://www.facebook.com/groups/{group_id}"


def save_session(state_path: str) -> None:
    """Open a browser, let the user log in by hand, and save the session.

    Run this once. Nothing is automated here except opening the window and
    persisting the resulting cookies/localStorage to ``state_path``.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
        print(
            "\nA browser window has opened. Log in to Facebook by hand "
            "(complete any 2FA).\n"
            "When your normal Facebook home feed is visible, come back here and "
            "press Enter to save the session.\n"
        )
        input("Press Enter once you are logged in... ")
        context.storage_state(path=state_path)
        browser.close()
    print(f"Session saved to {state_path}")


def capture_feed(
    *,
    group_id: str,
    state_path: str,
    capture_path: str,
    manual: bool = False,
    scrolls: int = 8,
    min_delay: float = 2.5,
    max_delay: float = 6.0,
    headless: bool = False,
) -> int:
    """Load the group and record its GraphQL feed responses to ``capture_path``.

    In ``manual`` mode the script does not scroll; you scroll the window
    yourself and press Enter when done. Returns the number of responses saved.
    """
    from playwright.sync_api import sync_playwright

    captured: list[dict[str, Any]] = []

    def on_response(response: Any) -> None:
        if "/api/graphql" not in response.url:
            return
        try:
            body = response.text()
        except Exception:
            return
        if body:
            captured.append({"url": response.url, "body": body})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(storage_state=state_path)
        page = context.new_page()
        page.on("response", on_response)

        page.goto(group_url(group_id), wait_until="domcontentloaded")
        _human_pause(min_delay, max_delay)

        if manual:
            print(
                "\nManual mode: scroll through the group yourself at a normal "
                "pace. The tool is recording the feed data your browsing loads.\n"
                "Press Enter here when you have scrolled far enough back.\n"
            )
            input("Press Enter when done... ")
        else:
            for i in range(scrolls):
                # Scroll a randomized, human-ish distance, then wait.
                page.mouse.wheel(0, random.randint(1400, 2600))
                _human_pause(min_delay, max_delay)
                print(f"  scrolled {i + 1}/{scrolls} — {len(captured)} responses captured")

        browser.close()

    with open(capture_path, "w", encoding="utf-8") as fh:
        for record in captured:
            fh.write(json.dumps(record, ensure_ascii=False))
            fh.write("\n")

    print(f"Saved {len(captured)} GraphQL response(s) to {capture_path}")
    return len(captured)


def _human_pause(min_delay: float, max_delay: float) -> None:
    time.sleep(random.uniform(min_delay, max_delay))
