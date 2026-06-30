"""Verify the browser tools drive a real Chrome (headless, temp profile, data:
URLs — no network). Proves ref-based grounding: snapshot -> act by [ref=eN]."""

from __future__ import annotations

import re

import pytest

from echlon.tools import browser


@pytest.fixture()
def headless_browser(tmp_path, monkeypatch):
    monkeypatch.setenv("ECHLON_BROWSER_HEADLESS", "1")
    monkeypatch.setenv("ECHLON_CHROME_PROFILE", str(tmp_path / "chrome"))
    monkeypatch.delenv("ECHLON_CHROME_CDP", raising=False)
    # Fresh session bound to the headless/temp env for this test.
    browser._session = browser._Session()
    yield
    browser._session.close()


def _first_ref(snapshot: str, needle: str) -> str:
    """Return the [ref=eN] on the snapshot line containing `needle`."""
    for line in snapshot.splitlines():
        if needle in line:
            m = re.search(r"\[ref=(e\d+)\]", line)
            if m:
                return m.group(1)
    raise AssertionError(f"no ref for {needle!r} in:\n{snapshot}")


def test_navigate_snapshot_click_type(headless_browser) -> None:
    page = (
        "data:text/html,"
        "<title>Start</title>"
        "<button onclick=\"document.title='Clicked';this.textContent='Done'\">Press</button>"
        "<input placeholder='Query'>"
    )

    snap = browser.browser_navigate(page)
    assert "Start" in snap
    assert "button \"Press\"" in snap

    # Click by ref -> updated snapshot reflects the DOM change.
    ref = _first_ref(snap, 'button "Press"')
    after_click = browser.browser_click(ref)
    assert "Clicked" in after_click  # title updated
    assert "Done" in after_click     # button text updated

    # Type into the textbox by ref -> no error, snapshot still renders.
    snap2 = browser.browser_snapshot()
    box = _first_ref(snap2, "textbox")
    typed = browser.browser_type(box, "hello world")
    assert not typed.startswith("[error]")
    assert browser.browser_read_text(). strip() is not None
