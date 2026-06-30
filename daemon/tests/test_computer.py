"""OS-level control tools: hotkey parsing, capture cmd, wiring, screenshot bridge.

Live HID injection (clicks/keys) needs macOS Accessibility + Screen-Recording
grants that aren't available under test, so we cover the deterministic logic:
hotkey resolution, the screencapture argv, tool registration, graceful
degradation when Quartz is missing, and the screenshot step callback.
"""

from __future__ import annotations

import pytest

from echlon.tools import build_tools, computer


def test_resolve_hotkey_with_modifiers() -> None:
    flags, keycode = computer._resolve_hotkey("cmd+shift+a")
    assert keycode == 0  # 'a'
    assert flags & computer._MODFLAGS["cmd"]
    assert flags & computer._MODFLAGS["shift"]
    assert not flags & computer._MODFLAGS["ctrl"]


def test_resolve_hotkey_bare_key() -> None:
    assert computer._resolve_hotkey("enter") == (0, 36)


def test_resolve_hotkey_aliases() -> None:
    assert computer._resolve_hotkey("esc")[1] == computer._resolve_hotkey("escape")[1]
    assert computer._resolve_hotkey("opt+c")[0] == computer._resolve_hotkey("option+c")[0]


def test_resolve_hotkey_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown key"):
        computer._resolve_hotkey("cmd+nope")
    with pytest.raises(ValueError, match="unknown modifier"):
        computer._resolve_hotkey("hyper+a")


def test_screencapture_cmd() -> None:
    assert computer._screencapture_cmd("/t/x.png") == ["screencapture", "-x", "-t", "png", "/t/x.png"]
    assert computer._screencapture_cmd("/t/x.png", "2") == \
        ["screencapture", "-x", "-t", "png", "-D", "2", "/t/x.png"]


def test_build_tools_includes_computer_tools_by_default(tmp_path) -> None:
    names = {t.name for t in build_tools(tmp_path)}
    assert {"computer_screenshot", "computer_click", "computer_type",
            "computer_key", "computer_move", "computer_scroll"} <= names


def test_build_tools_can_exclude_computer_tools(tmp_path) -> None:
    names = {t.name for t in build_tools(tmp_path, os_control=False)}
    assert not any(n.startswith("computer_") for n in names)
    assert "shell_exec" in names  # the rest are unaffected


def test_tools_degrade_without_quartz(monkeypatch) -> None:
    # Simulate a box where pyobjc didn't import: tools return errors, never crash.
    monkeypatch.setattr(computer, "Quartz", None)
    assert computer.computer_click(10, 10).startswith("[error]")
    assert computer.computer_type("hi").startswith("[error]")
    assert computer.computer_key("cmd+c").startswith("[error]")


def test_ensure_ready_rejects_non_macos(monkeypatch) -> None:
    monkeypatch.setattr(computer.platform, "system", lambda: "Linux")
    with pytest.raises(RuntimeError, match="macOS only"):
        computer.ensure_os_control_ready()


def test_attach_screenshot_step_moves_pending_to_current_and_clears_old(monkeypatch) -> None:
    from PIL import Image

    class _Step:
        observations_images = None

    prior = _Step()
    prior.observations_images = [Image.new("RGB", (2, 2))]  # an older screenshot
    current = _Step()

    class _Agent:
        class memory:  # noqa: N801
            steps = [prior]

    monkeypatch.setattr(computer, "_pending_image", Image.new("RGB", (4, 4)))
    computer.attach_screenshot_step(current, _Agent())

    assert current.observations_images and current.observations_images[0].size == (4, 4)
    assert prior.observations_images is None  # old screenshot stripped from context
    assert computer._pending_image is None    # consumed


def test_attach_screenshot_step_noop_without_pending(monkeypatch) -> None:
    class _Step:
        observations_images = None

    monkeypatch.setattr(computer, "_pending_image", None)
    step = _Step()
    computer.attach_screenshot_step(step, None)
    assert step.observations_images is None
