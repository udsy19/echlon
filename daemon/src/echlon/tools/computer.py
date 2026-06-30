"""Computer-control tools — drive the *whole* macOS desktop, not just the browser.

This is the OS-level analog of browser.py. Where the browser tools read a page's
accessibility tree and act on elements by ref, these tools work on any native
app/window the way a human does: look at the screen, then move/click/type at
pixel coordinates. That makes the agent general across the entire laptop (Finder,
Mail, Photoshop, a game, anything) instead of web-only.

Perception is a screenshot; action is a synthetic HID event:
  - screenshots come from the built-in `screencapture` (no extra binary), resized
    to the display's *logical* (point) resolution so the coordinates the model
    reads off the image map 1:1 onto the coordinates we feed CGEvent — this avoids
    the classic Retina 2x off-by-scale bug.
  - mouse/keyboard are posted via Quartz CGEvents (pyobjc), the same mechanism
    pyautogui uses on macOS.

The screenshot reaches the model through a step callback (attach_screenshot_step)
that sets the current step's `observations_images` — the same hook smolagents'
own vision-browser example uses. CodeAgent does not forward tool-returned images
on its own, so this callback is required.

Requires a *vision-capable* model (Claude, or a local VLM like qwen2-vl /
llama3.2-vision) — a text-only local coder model can't read the screenshot. And
two macOS permissions, granted to whatever process runs the daemon (Terminal,
or the packaged app): Screen Recording (to capture) and Accessibility (to inject
input). Both are TCC-gated and can only be granted by the user in System Settings.

Env:
  ECHLON_SCREENSHOT_DISPLAY   1-based display index to capture (default: main)
"""

from __future__ import annotations

import os
import platform
import subprocess
import time
from typing import Optional

from smolagents import tool

from . import context

try:  # pyobjc is macOS-only and an optional install; degrade with a clear message
    import Quartz  # type: ignore

    from ApplicationServices import AXIsProcessTrusted  # type: ignore

    _IMPORT_ERROR: Optional[str] = None
except Exception as exc:  # noqa: BLE001
    Quartz = None  # type: ignore
    AXIsProcessTrusted = None  # type: ignore
    _IMPORT_ERROR = str(exc)

try:
    from PIL import Image
except Exception as exc:  # noqa: BLE001 — pillow is a hard dep, but be defensive
    Image = None  # type: ignore
    _IMPORT_ERROR = _IMPORT_ERROR or str(exc)


# The most recent screenshot, waiting to be attached to the model's next step.
_pending_image = None


# --- key tables (pure data; used by _resolve_hotkey) -------------------------

# macOS virtual key codes for the keys an agent realistically needs.
_KEYCODES: dict[str, int] = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8,
    "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "9": 25, "7": 26,
    "8": 28, "0": 29, "o": 31, "u": 32, "i": 34, "p": 35, "l": 37, "j": 38,
    "k": 40, "n": 45, "m": 46,
    "=": 24, "-": 27, "]": 30, "[": 33, "'": 39, ";": 41, "\\": 42, ",": 43,
    "/": 44, ".": 47, "`": 50,
    "return": 36, "enter": 36, "tab": 48, "space": 49, " ": 49,
    "delete": 51, "backspace": 51, "forwarddelete": 117,
    "escape": 53, "esc": 53,
    "left": 123, "right": 124, "down": 125, "up": 126,
    "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
}

# Quartz CGEventFlags modifier masks, by alias.
_MODFLAGS: dict[str, int] = {
    "cmd": 1 << 20, "command": 1 << 20, "meta": 1 << 20, "super": 1 << 20,
    "shift": 1 << 17,
    "alt": 1 << 19, "option": 1 << 19, "opt": 1 << 19,
    "ctrl": 1 << 18, "control": 1 << 18,
    "fn": 1 << 23,
}


def _resolve_hotkey(combo: str) -> tuple[int, int]:
    """Parse 'cmd+shift+a' -> (flags_mask, keycode). Pure; raises ValueError.

    The final '+'-separated token is the key; everything before it is a modifier.
    """
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    if not parts:
        raise ValueError("empty hotkey")
    *mods, key = parts
    if key not in _KEYCODES:
        raise ValueError(f"unknown key {key!r} (known: {', '.join(sorted(_KEYCODES))})")
    flags = 0
    for mod in mods:
        if mod not in _MODFLAGS:
            raise ValueError(f"unknown modifier {mod!r} (use cmd/shift/alt/ctrl/fn)")
        flags |= _MODFLAGS[mod]
    return flags, _KEYCODES[key]


def _screencapture_cmd(path: str, display: str | None = None) -> list[str]:
    """Build the screencapture argv. Pure; `-x` = silent, `-t png`."""
    cmd = ["screencapture", "-x", "-t", "png"]
    if display:
        cmd += ["-D", str(display)]
    cmd.append(path)
    return cmd


# --- readiness / preflight ---------------------------------------------------

def ensure_os_control_ready() -> None:
    """Raise RuntimeError with actionable guidance if OS control can't work."""
    if platform.system() != "Darwin":
        raise RuntimeError("OS-level control is implemented for macOS only.")
    if _IMPORT_ERROR is not None or Quartz is None or Image is None:
        raise RuntimeError(
            f"OS control needs pyobjc + pillow ({_IMPORT_ERROR}). "
            "Reinstall deps: `uv sync` in daemon/."
        )
    problems = []
    if hasattr(Quartz, "CGPreflightScreenCaptureAccess") and not Quartz.CGPreflightScreenCaptureAccess():
        problems.append("Screen Recording (to capture the screen)")
    if AXIsProcessTrusted is not None and not AXIsProcessTrusted():
        problems.append("Accessibility (to move the mouse / type)")
    if problems:
        raise RuntimeError(
            "Grant these to the app running Echlon in System Settings > Privacy & "
            "Security, then restart it: " + "; ".join(problems) + "."
        )


def _require() -> None:
    if Quartz is None or Image is None:
        raise RuntimeError(
            f"OS control unavailable: pyobjc/pillow not importable ({_IMPORT_ERROR})."
        )


# --- low-level event posting (only reached when Quartz is present) -----------

_TAP = None  # kCGHIDEventTap, resolved lazily


def _tap() -> int:
    global _TAP
    if _TAP is None:
        _TAP = Quartz.kCGHIDEventTap
    return _TAP


def _logical_size() -> tuple[int, int]:
    """Main display size in *points* (logical pixels)."""
    bounds = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
    return int(round(bounds.size.width)), int(round(bounds.size.height))


def _clamp(x: int, y: int) -> tuple[int, int]:
    w, h = _logical_size()
    return max(0, min(int(x), w - 1)), max(0, min(int(y), h - 1))


def _post_mouse(x: int, y: int, down: int, up: int, button: int, clicks: int) -> None:
    point = Quartz.CGPointMake(float(x), float(y))
    for state in range(1, clicks + 1):
        for etype in (down, up):
            ev = Quartz.CGEventCreateMouseEvent(None, etype, point, button)
            if clicks > 1:
                Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, state)
            Quartz.CGEventPost(_tap(), ev)
            time.sleep(0.01)


# --- tools -------------------------------------------------------------------

@tool
def computer_screenshot() -> str:
    """Capture the screen so you can see the whole desktop, then decide where to act.

    The image is attached to your NEXT step (not this one) — so take a screenshot,
    end the turn, and on the following step read the image and choose coordinates.
    Coordinates are in pixels from the top-left of the returned image; pass those
    same x,y to computer_click / computer_move. Re-screenshot after any action that
    changes the screen, since the layout (and thus coordinates) will have moved.
    """
    global _pending_image
    try:
        _require()
        ensure_os_control_ready()
    except RuntimeError as exc:
        return f"[error] {exc}"
    shots = context.workspace() / ".echlon" / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    path = shots / "latest.png"
    display = os.getenv("ECHLON_SCREENSHOT_DISPLAY")
    try:
        subprocess.run(_screencapture_cmd(str(path), display), check=True, timeout=15)
        img = Image.open(path).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        return f"[error] screenshot failed: {str(exc)[:200]}"
    w, h = _logical_size()
    if img.size != (w, h):
        img = img.resize((w, h), Image.LANCZOS)
    _pending_image = img
    return (
        f"[ok] screenshot captured ({w}x{h} points); it is attached to your next step. "
        "Read it, then click/type using x,y pixel coordinates within that image."
    )


@tool
def computer_click(x: int, y: int, button: str = "left", double: bool = False) -> str:
    """Click the mouse at a screen coordinate (from the latest screenshot).

    Args:
        x: X pixel coordinate (left edge = 0), as read off the latest screenshot.
        y: Y pixel coordinate (top edge = 0), as read off the latest screenshot.
        button: "left" (default) or "right".
        double: If true, double-click (e.g. to open a file/app).
    """
    try:
        _require()
    except RuntimeError as exc:
        return f"[error] {exc}"
    cx, cy = _clamp(x, y)
    if button == "right":
        down, up, btn = Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp, Quartz.kCGMouseButtonRight
    else:
        down, up, btn = Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp, Quartz.kCGMouseButtonLeft
    try:
        _post_mouse(cx, cy, down, up, btn, clicks=2 if double else 1)
    except Exception as exc:  # noqa: BLE001
        return f"[error] click failed: {str(exc)[:200]}"
    return f"[ok] {'double-' if double else ''}{button}-clicked at ({cx},{cy}). Re-screenshot to see the result."


@tool
def computer_move(x: int, y: int) -> str:
    """Move the mouse pointer to a screen coordinate without clicking (e.g. to hover).

    Args:
        x: X pixel coordinate from the latest screenshot.
        y: Y pixel coordinate from the latest screenshot.
    """
    try:
        _require()
    except RuntimeError as exc:
        return f"[error] {exc}"
    cx, cy = _clamp(x, y)
    try:
        ev = Quartz.CGEventCreateMouseEvent(
            None, Quartz.kCGEventMouseMoved, Quartz.CGPointMake(float(cx), float(cy)), 0
        )
        Quartz.CGEventPost(_tap(), ev)
    except Exception as exc:  # noqa: BLE001
        return f"[error] move failed: {str(exc)[:200]}"
    return f"[ok] moved to ({cx},{cy})."


@tool
def computer_type(text: str) -> str:
    """Type a string of text wherever the keyboard focus currently is.

    Use this for entering text into the focused field. Click the field first if it
    isn't already focused. For shortcuts and special keys (Enter, Cmd+C, arrows),
    use computer_key instead.

    Args:
        text: The literal text to type.
    """
    try:
        _require()
    except RuntimeError as exc:
        return f"[error] {exc}"
    try:
        for ch in text:
            for keydown in (True, False):
                ev = Quartz.CGEventCreateKeyboardEvent(None, 0, keydown)
                Quartz.CGEventKeyboardSetUnicodeString(ev, len(ch), ch)
                Quartz.CGEventPost(_tap(), ev)
            time.sleep(0.005)
    except Exception as exc:  # noqa: BLE001
        return f"[error] type failed: {str(exc)[:200]}"
    return f"[ok] typed {len(text)} chars."


@tool
def computer_key(keys: str) -> str:
    """Press a key or keyboard shortcut (combine with '+').

    Examples: "enter", "esc", "tab", "cmd+c", "cmd+shift+4", "down", "cmd+space".

    Args:
        keys: A key name, or modifiers + key joined by '+' (cmd/shift/alt/ctrl/fn).
    """
    try:
        _require()
        flags, keycode = _resolve_hotkey(keys)
    except (RuntimeError, ValueError) as exc:
        return f"[error] {exc}"
    try:
        for keydown in (True, False):
            ev = Quartz.CGEventCreateKeyboardEvent(None, keycode, keydown)
            if flags:
                Quartz.CGEventSetFlags(ev, flags)
            Quartz.CGEventPost(_tap(), ev)
            time.sleep(0.01)
    except Exception as exc:  # noqa: BLE001
        return f"[error] key press failed: {str(exc)[:200]}"
    return f"[ok] pressed {keys}."


@tool
def computer_scroll(dy: int, dx: int = 0) -> str:
    """Scroll the view under the mouse. Positive dy scrolls up, negative scrolls down.

    Args:
        dy: Vertical scroll amount in lines (positive = up, negative = down).
        dx: Horizontal scroll amount in lines (positive = left). Default 0.
    """
    try:
        _require()
    except RuntimeError as exc:
        return f"[error] {exc}"
    try:
        ev = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitLine, 2, int(dy), int(dx))
        Quartz.CGEventPost(_tap(), ev)
    except Exception as exc:  # noqa: BLE001
        return f"[error] scroll failed: {str(exc)[:200]}"
    return f"[ok] scrolled dy={dy} dx={dx}."


# --- step callback: surface the screenshot to the (vision) model -------------

def attach_screenshot_step(step, agent=None) -> None:
    """Attach the most recent screenshot to this step's images so the model sees it.

    Runs as a smolagents step callback. CodeAgent fires callbacks *before*
    appending the step to memory, so `agent.memory.steps` here holds only prior
    steps — we attach to the current `step` and strip images off the older ones,
    keeping just the latest screenshot in context (bounds payload + token cost).
    """
    global _pending_image
    if _pending_image is None:
        return
    try:
        step.observations_images = [_pending_image]
        if agent is not None:
            for prev in getattr(agent.memory, "steps", []):
                if getattr(prev, "observations_images", None):
                    prev.observations_images = None
    finally:
        _pending_image = None


COMPUTER_TOOLS = [
    computer_screenshot,
    computer_click,
    computer_move,
    computer_type,
    computer_key,
    computer_scroll,
]
