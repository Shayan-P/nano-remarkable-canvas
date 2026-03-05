#!/usr/bin/env python3
"""
Mouse control — move and click. On macOS uses Quartz; elsewhere uses pyautogui.
All coordinates are screen pixels with origin top-left.

macOS: Grant Accessibility in System Settings → Privacy & Security → Accessibility
for your terminal/IDE. When first requested, a pop-up usually appears—click
"Open System Settings" to enable it.

Exports: mouse_move, mouse_down, mouse_up (for stroke_replay).
Standalone usage:
  python mouse_control.py              # demo: move to center and click
  python mouse_control.py 400 300      # move to (400, 300) and click
  python mouse_control.py 400 300 move # move only
"""

import sys

if sys.platform == "darwin":
    from Quartz.CoreGraphics import (
        CGDisplayBounds,
        CGEventCreateMouseEvent,
        CGEventPost,
        CGMainDisplayID,
        kCGHIDEventTap,
        kCGEventLeftMouseDown,
        kCGEventLeftMouseUp,
        kCGEventMouseMoved,
        kCGMouseButtonLeft,
    )

    _bounds = CGDisplayBounds(CGMainDisplayID())
    _screen_width = int(_bounds.size.width)
    _screen_height = int(_bounds.size.height)

    def mouse_move(x: int, y: int) -> None:
        qy = _screen_height - y
        ev = CGEventCreateMouseEvent(None, kCGEventMouseMoved, (x, qy), kCGMouseButtonLeft)
        CGEventPost(kCGHIDEventTap, ev)

    def mouse_down(x: int, y: int) -> None:
        qy = _screen_height - y
        ev = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, (x, qy), kCGMouseButtonLeft)
        CGEventPost(kCGHIDEventTap, ev)

    def mouse_up(x: int, y: int) -> None:
        qy = _screen_height - y
        ev = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, (x, qy), kCGMouseButtonLeft)
        CGEventPost(kCGHIDEventTap, ev)
else:
    import pyautogui

    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0

    def mouse_move(x: int, y: int) -> None:
        pyautogui.moveTo(x, y)

    def mouse_down(x: int, y: int) -> None:
        pyautogui.moveTo(x, y)
        pyautogui.mouseDown()

    def mouse_up(x: int, y: int) -> None:
        pyautogui.moveTo(x, y)
        pyautogui.mouseUp()


def main() -> None:
    if sys.platform != "darwin":
        print("Standalone demo uses Quartz and is for macOS only.", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) >= 3:
        x, y = int(sys.argv[1]), int(sys.argv[2])
        mouse_move(x, y)
        if len(sys.argv) < 4 or sys.argv[3].lower() != "move":
            mouse_down(x, y)
            mouse_up(x, y)
        print(f"Mouse: ({x}, {y})")
    else:
        x, y = _screen_width // 2, _screen_height // 2
        print(f"Demo: moving to center ({x}, {y}) and clicking...")
        mouse_move(x, y)
        mouse_down(x, y)
        mouse_up(x, y)
        print("Done.")


if __name__ == "__main__":
    main()
