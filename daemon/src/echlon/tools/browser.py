"""Browser tools — Playwright driving a real headful Chrome (PLAN.md §3).

Grounding model: each tool returns an accessibility snapshot where interactive
elements are tagged ``[ref=eN]`` (Playwright ``aria_snapshot(mode="ai")``). The
model reads the snapshot and acts on elements by ref — works without a vision
model, which matters for the open-source-model path.

Threading: Playwright's sync API binds every object to the thread that created
it, but smolagents runs each agent step in a different thread. So the whole
browser lives on a single dedicated worker thread and every tool call is
marshalled to it — otherwise the second step hits "cannot switch to a different
thread". The browser session is long-lived so refs and page state persist
across tool calls.

By default we launch the user's installed Chrome with a dedicated persistent
profile (logins survive across runs, the user can watch). Set ECHLON_CHROME_CDP
to attach to an already-running Chrome instead.

Env:
  ECHLON_CHROME_CDP        attach over CDP, e.g. http://localhost:9222
  ECHLON_CHROME_PROFILE    persistent user-data-dir (default ~/.echlon/chrome)
  ECHLON_BROWSER_HEADLESS  "1" to run headless (used by tests)
"""

from __future__ import annotations

import atexit
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from playwright.sync_api import Page, sync_playwright
from smolagents import tool

from . import context

_MAX_SNAPSHOT_CHARS = 8000


class _Session:
    """Long-lived browser pinned to one worker thread; tool calls marshal to it."""

    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="echlon-browser")
        self._pw = None
        self._ctx = None
        self._page: Page | None = None

    def run(self, fn: Callable[[Page], str]) -> str:
        """Run fn(page) on the browser thread and return its result."""
        return self._pool.submit(self._invoke, fn).result()

    def _invoke(self, fn: Callable[[Page], str]) -> str:
        return fn(self._ensure_page())

    def _ensure_page(self) -> Page:  # always runs on the worker thread
        if self._page is not None:
            return self._page
        self._pw = sync_playwright().start()
        cdp = os.getenv("ECHLON_CHROME_CDP")
        if cdp:
            browser = self._pw.chromium.connect_over_cdp(cdp)
            self._ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        else:
            profile = os.getenv("ECHLON_CHROME_PROFILE") or str(Path.home() / ".echlon" / "chrome")
            Path(profile).mkdir(parents=True, exist_ok=True)
            headless = os.getenv("ECHLON_BROWSER_HEADLESS") == "1"
            self._ctx = self._pw.chromium.launch_persistent_context(
                user_data_dir=profile,
                channel="chrome",
                headless=headless,
                args=["--no-first-run", "--no-default-browser-check"],
            )
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        atexit.register(self.close)
        return self._page

    def _close_on_thread(self) -> str:
        for closer in (lambda: self._ctx and self._ctx.close(), lambda: self._pw and self._pw.stop()):
            try:
                closer()
            except Exception:
                pass
        self._pw = self._ctx = self._page = None
        return "[ok] browser closed"

    def close(self) -> None:
        try:
            self._pool.submit(self._close_on_thread).result(timeout=10)
        except Exception:
            pass
        self._pool.shutdown(wait=False)


_session = _Session()


def reset() -> None:
    """Close the browser and start fresh — call between agent sessions so page
    state and refs from one task don't leak into the next."""
    global _session
    _session.close()
    _session = _Session()


def _snapshot(page: Page) -> str:
    """Render the current page as a ref-tagged accessibility snapshot."""
    try:
        snap = page.aria_snapshot(mode="ai")
    except Exception as exc:  # noqa: BLE001 — surface, don't hide (keep-errors-visible)
        return f"[error] could not snapshot page: {str(exc)[:200]}"
    header = f"# {page.title()}\n{page.url}\n\n"
    return header + context.truncate_restorable(snap, _MAX_SNAPSHOT_CHARS, label="snapshot")


def _settle(page: Page) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass


@tool
def browser_navigate(url: str) -> str:
    """Open a URL in the browser and return an accessibility snapshot of the page.

    Interactive elements are tagged ``[ref=eN]``; pass those refs to
    browser_click / browser_type.

    Args:
        url: The URL to open (include the scheme, e.g. https://).
    """

    def _go(page: Page) -> str:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as exc:  # noqa: BLE001
            return f"[error] navigation to {url} failed: {str(exc)[:200]}"
        return _snapshot(page)

    return _session.run(_go)


@tool
def browser_snapshot() -> str:
    """Return a fresh accessibility snapshot of the current page (elements tagged [ref=eN])."""
    return _session.run(_snapshot)


@tool
def browser_click(ref: str) -> str:
    """Click the element with the given ref and return the updated page snapshot.

    Args:
        ref: An element ref from a snapshot, e.g. "e5".
    """

    def _click(page: Page) -> str:
        try:
            page.locator(f"aria-ref={ref}").click(timeout=10000)
        except Exception as exc:  # noqa: BLE001
            return f"[error] could not click {ref}: {str(exc)[:200]}"
        _settle(page)
        return _snapshot(page)

    return _session.run(_click)


@tool
def browser_type(ref: str, text: str, submit: bool = False) -> str:
    """Type text into the element with the given ref, then return the updated snapshot.

    Args:
        ref: An element ref from a snapshot, e.g. "e5".
        text: The text to enter.
        submit: If true, press Enter after typing (e.g. to submit a search).
    """

    def _type(page: Page) -> str:
        try:
            loc = page.locator(f"aria-ref={ref}")
            loc.fill(text, timeout=10000)
            if submit:
                loc.press("Enter")
                _settle(page)
        except Exception as exc:  # noqa: BLE001
            return f"[error] could not type into {ref}: {str(exc)[:200]}"
        return _snapshot(page)

    return _session.run(_type)


@tool
def browser_read_text() -> str:
    """Return the visible text of the current page, for reading or extraction.

    Long pages are truncated; for very large content, save what you need to a
    file with file_write rather than holding it all in context.
    """

    def _read(page: Page) -> str:
        try:
            txt = page.inner_text("body")
        except Exception as exc:  # noqa: BLE001
            return f"[error] could not read page text: {str(exc)[:200]}"
        return context.truncate_restorable(txt, _MAX_SNAPSHOT_CHARS, label="page text")

    return _session.run(_read)
