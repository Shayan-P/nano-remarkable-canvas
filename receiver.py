#!/usr/bin/env python3
"""
receiver.py — Virtual Board Event Receiver

1. Launches a fullscreen overlay so you can drag a bounding box over any app.
2. Starts a WebSocket server (ws://localhost:8765).
3. Receives normalized stroke events from board.py and replays them as real
   mouse events inside the selected bounding box.

Requirements:
    pip install pyautogui websockets

macOS note: grant Accessibility permissions to Terminal/iTerm in
System Settings → Privacy & Security → Accessibility.
"""

import asyncio
import json
import sys
import threading

import pyautogui
import websockets

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

WS_HOST = "localhost"
WS_PORT = 8765

# ── bounding box selection (PyObjC — truly transparent) ───────────────────────

def select_bounding_box() -> tuple[int, int, int, int] | None:
    """
    Native macOS transparent overlay via PyObjC.
    The window background is completely clear — you see the desktop at full
    fidelity. Only the dim vignette, crosshair, and selection chrome are drawn.

    Install: pip install pyobjc-framework-Cocoa
    """
    try:
        import time
        from AppKit import (
            NSApplication, NSWindow, NSView, NSColor, NSBezierPath,
            NSWindowStyleMaskBorderless, NSBackingStoreBuffered,
            NSScreen, NSCursor, NSFont, NSAttributedString,
            NSForegroundColorAttributeName, NSFontAttributeName,
            NSEvent, NSGraphicsContext,
            NSCompositingOperationClear, NSCompositingOperationSourceOver,
            NSFloatingWindowLevel,
            NSTimer,
        )
        from Foundation import NSMakeRect, NSMakePoint
        from Foundation import NSObject
    except ImportError:
        print("\nERROR: pyobjc-framework-Cocoa not installed.")
        print("Run: pip install pyobjc-framework-Cocoa\n")
        sys.exit(1)

    result: list = []

    sf = NSScreen.mainScreen().frame()
    W  = int(sf.size.width)
    H  = int(sf.size.height)

    # Design tokens
    ACCENT_C = NSColor.colorWithRed_green_blue_alpha_(0.37, 0.91, 1.00, 1.0)
    HANDLE_C = NSColor.colorWithRed_green_blue_alpha_(1.00, 0.37, 0.67, 1.0)
    GLOW_C   = NSColor.colorWithRed_green_blue_alpha_(0.37, 0.91, 1.00, 0.25)
    DIM_C    = NSColor.colorWithWhite_alpha_(0.0, 0.45)

    # Shared mutable state (class vars updated before setNeedsDisplay_)
    _state = {"start": None, "end": None, "mouse": None}
    _app_box: list = []  # holds NSApplication ref so _stop() can reach it
    _last_mouse_display_time = [0.0]  # list to allow mutation in nested scope

    def _stop():
        # Defer stop to the next run loop iteration so we're not inside an event
        # handler when stop runs — otherwise the run loop may not exit cleanly.
        class StopRunner(NSObject):
            def timerFire_(self, timer):
                # Close overlay and restore cursor immediately when selection is done
                win = _app_box[1]
                win.orderOut_(None)
                NSCursor.pop()
                a = _app_box[0]
                a.stop_(None)
                dummy = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                    15, NSMakePoint(0, 0), 0, 0, 0, None, 0, 0, 0)
                a.postEvent_atStart_(dummy, True)
        runner = StopRunner.alloc().init()
        _app_box.append(runner)  # keep alive
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.001, runner, "timerFire:", None, False)

    def _pt(event, view):
        p = view.convertPoint_fromView_(event.locationInWindow(), None)
        return (p.x, p.y)

    class OverlayView(NSView):

        def isOpaque(self):      return False
        def acceptsFirstResponder(self): return True

        def mouseDown_(self, e):
            x, y = _pt(e, self)
            _state["start"] = _state["end"] = _state["mouse"] = (x, y)
            self.setNeedsDisplay_(True)

        def mouseDragged_(self, e):
            x, y = _pt(e, self)
            _state["end"] = _state["mouse"] = (x, y)
            self.setNeedsDisplay_(True)

        def mouseUp_(self, e):
            x, y = _pt(e, self)
            _state["end"] = (x, y)
            s, en = _state["start"], _state["end"]
            if s and abs(en[0]-s[0]) > 20 and abs(en[1]-s[1]) > 20:
                result.append((*s, *en))
            # Always stop the run loop so the overlay closes (valid or invalid selection)
            _stop()

        def mouseMoved_(self, e):
            _state["mouse"] = _pt(e, self)
            # Throttle redraws to ~60 fps so we don't flood the run loop
            now = time.monotonic()
            if now - _last_mouse_display_time[0] >= 0.016:
                _last_mouse_display_time[0] = now
                self.setNeedsDisplay_(True)

        def keyDown_(self, e):
            if e.keyCode() == 53:
                _stop()

        # ── drawing ──────────────────────────────────────────────────────────
        def drawRect_(self, _dirty):
            b  = self.bounds()
            bw = b.size.width
            bh = b.size.height

            # 1. Fully transparent base
            NSColor.clearColor().setFill()
            NSBezierPath.fillRect_(b)

            # 2. Subtle dim vignette over the whole screen
            DIM_C.setFill()
            NSBezierPath.fillRect_(b)

            ctx = NSGraphicsContext.currentContext()
            s, en = _state["start"], _state["end"]

            if s and en:
                rx = min(s[0], en[0]);  rw = abs(en[0] - s[0])
                ry = min(s[1], en[1]);  rh = abs(en[1] - s[1])
                sel = NSMakeRect(rx, ry, rw, rh)

                # 3. Punch through → desktop fully visible inside selection
                ctx.setCompositingOperation_(NSCompositingOperationClear)
                NSColor.blackColor().setFill()
                NSBezierPath.fillRect_(sel)
                ctx.setCompositingOperation_(NSCompositingOperationSourceOver)

                # 4. Outer glow halo
                GLOW_C.setStroke()
                halo = NSBezierPath.bezierPathWithRect_(
                    NSMakeRect(rx - 6, ry - 6, rw + 12, rh + 12))
                halo.setLineWidth_(12.0)
                halo.stroke()

                # 5. Crisp 2 px selection border
                ACCENT_C.setStroke()
                border = NSBezierPath.bezierPathWithRect_(sel)
                border.setLineWidth_(2.0)
                border.stroke()

                # 6. Corner handles (pink squares)
                hs = 6
                for cx, cy in [(rx, ry), (rx+rw, ry), (rx, ry+rh), (rx+rw, ry+rh)]:
                    hp = NSBezierPath.bezierPathWithRect_(
                        NSMakeRect(cx - hs, cy - hs, hs * 2, hs * 2))
                    HANDLE_C.setFill(); hp.fill()
                    NSColor.whiteColor().setStroke()
                    hp.setLineWidth_(1.0); hp.stroke()

                # 7. Edge mid-handles (cyan squares)
                ms = 4
                for cx, cy in [(rx + rw/2, ry), (rx + rw/2, ry + rh),
                               (rx, ry + rh/2), (rx + rw, ry + rh/2)]:
                    mp = NSBezierPath.bezierPathWithRect_(
                        NSMakeRect(cx - ms, cy - ms, ms * 2, ms * 2))
                    ACCENT_C.setFill(); mp.fill()
                    NSColor.whiteColor().setStroke()
                    mp.setLineWidth_(1.0); mp.stroke()

                # 8. Dimension badge (floating in centre)
                self._draw_badge(f" {int(rw)} × {int(rh)} px ",
                                 rx + rw / 2, ry + rh / 2)

            # 9. Crosshair + custom cursor
            m = _state["mouse"]
            if m:
                self._draw_crosshair(m[0], m[1], bw, bh)

            # 10. Instruction pill near top
            self._draw_pill(
                "  Drag to select drawing area   ·   Esc to cancel  ",
                bw / 2, bh - 64)

        def _draw_badge(self, text, cx, cy):
            from AppKit import (NSAttributedString,
                                NSForegroundColorAttributeName, NSFontAttributeName)
            from Foundation import NSMakePoint
            font  = NSFont.monospacedSystemFontOfSize_weight_(13, 0.4)
            attrs = {NSForegroundColorAttributeName: ACCENT_C,
                     NSFontAttributeName: font}
            astr  = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
            sz    = astr.size()
            pad   = 7
            bx, by = cx - sz.width / 2, cy - sz.height / 2
            bg = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                NSMakeRect(bx - pad, by - pad/2,
                           sz.width + pad*2, sz.height + pad), 5, 5)
            NSColor.colorWithWhite_alpha_(0.06, 0.90).setFill(); bg.fill()
            ACCENT_C.setStroke(); bg.setLineWidth_(1.0); bg.stroke()
            astr.drawAtPoint_(NSMakePoint(bx, by))

        def _draw_pill(self, text, cx, cy):
            from AppKit import (NSAttributedString,
                                NSForegroundColorAttributeName, NSFontAttributeName)
            from Foundation import NSMakePoint
            font  = NSFont.systemFontOfSize_weight_(14, 0.3)
            attrs = {NSForegroundColorAttributeName: NSColor.whiteColor(),
                     NSFontAttributeName: font}
            astr  = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
            sz    = astr.size()
            pad   = 12
            bx, by = cx - sz.width / 2, cy - sz.height / 2
            bg = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                NSMakeRect(bx - pad, by - pad/2,
                           sz.width + pad*2, sz.height + pad), 8, 8)
            NSColor.colorWithWhite_alpha_(0.08, 0.93).setFill(); bg.fill()
            ACCENT_C.setStroke(); bg.setLineWidth_(1.0); bg.stroke()
            astr.drawAtPoint_(NSMakePoint(bx, by))

        def _draw_crosshair(self, mx, my, bw, bh):
            from Foundation import NSMakePoint
            ch = NSColor.colorWithWhite_alpha_(1.0, 0.13)
            ch.setStroke()
            for p1, p2 in [((0, my), (bw, my)), ((mx, 0), (mx, bh))]:
                ln = NSBezierPath.bezierPath()
                ln.moveToPoint_(NSMakePoint(*p1))
                ln.lineToPoint_(NSMakePoint(*p2))
                ln.setLineWidth_(1.0); ln.stroke()

            r = 6
            ACCENT_C.setStroke()
            ring = NSBezierPath.bezierPathWithOvalInRect_(
                NSMakeRect(mx - r, my - r, r * 2, r * 2))
            ring.setLineWidth_(2.0); ring.stroke()

            for p1, p2 in [((mx-14, my), (mx-r-2, my)),
                           ((mx+r+2, my), (mx+14,  my)),
                           ((mx, my-14), (mx,      my-r-2)),
                           ((mx, my+r+2),(mx,      my+14))]:
                tick = NSBezierPath.bezierPath()
                tick.moveToPoint_(NSMakePoint(*p1))
                tick.lineToPoint_(NSMakePoint(*p2))
                tick.setLineWidth_(1.5); tick.stroke()

    # ── window setup ─────────────────────────────────────────────────────────

    # Subclass NSWindow so borderless window can become key (required for
    # keyboard events to reach our view / local monitors).
    class OverlayWindow(NSWindow):
        def canBecomeKeyWindow(self):  return True
        def canBecomeMainWindow(self): return True

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)          # Accessory — no Dock icon
    _app_box.append(app)

    win = OverlayWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        sf, NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False)
    _app_box.append(win)  # so _stop() can close the overlay when selection is done
    win.setBackgroundColor_(NSColor.clearColor())
    win.setOpaque_(False)
    win.setLevel_(NSFloatingWindowLevel + 2)
    win.setIgnoresMouseEvents_(False)
    win.setAcceptsMouseMovedEvents_(True)
    win.makeKeyAndOrderFront_(None)

    view = OverlayView.alloc().initWithFrame_(sf)
    win.setContentView_(view)
    win.makeFirstResponder_(view)

    # Global monitor — fires regardless of which app is key, so Escape is
    # always caught even if the window briefly loses focus.
    NSEventMaskKeyDown = 1 << 10
    def _on_key(event):
        if event.keyCode() == 53:   # Escape
            _stop()
    key_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
        NSEventMaskKeyDown, _on_key)

    NSCursor.crosshairCursor().push()
    app.activateIgnoringOtherApps_(True)
    app.run()                            # blocks until _stop() is called (overlay already closed in timer)
    NSEvent.removeMonitor_(key_monitor)

    if not result:
        return None

    sx, sy, ex, ey = result[0]
    x1 = int(min(sx, ex));  x2 = int(max(sx, ex))
    # NSView origin is bottom-left; pyautogui origin is top-left
    y1_ns = int(min(sy, ey)); y2_ns = int(max(sy, ey))
    return (x1, H - y2_ns, x2, H - y1_ns)


# ── WebSocket server ──────────────────────────────────────────────────────────

BBOX: tuple[int, int, int, int] | None = None
_mouse_down = False


def map_to_screen(nx: float, ny: float) -> tuple[int, int]:
    x1, y1, x2, y2 = BBOX  # type: ignore[misc]
    return int(x1 + nx * (x2 - x1)), int(y1 + ny * (y2 - y1))


async def handle(websocket):
    global _mouse_down
    addr = websocket.remote_address
    print(f"  [+] client connected: {addr}")
    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            kind = msg.get("type")
            nx = float(msg.get("x", 0.0))
            ny = float(msg.get("y", 0.0))
            sx, sy = map_to_screen(nx, ny)

            if kind == "mousedown":
                pyautogui.moveTo(sx, sy)
                pyautogui.mouseDown()
                _mouse_down = True
            elif kind == "mousemove" and _mouse_down:
                pyautogui.moveTo(sx, sy)
            elif kind == "mouseup":
                pyautogui.moveTo(sx, sy)
                pyautogui.mouseUp()
                _mouse_down = False
            elif kind == "clear":
                if _mouse_down:
                    pyautogui.mouseUp()
                    _mouse_down = False
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if _mouse_down:
            pyautogui.mouseUp()
            _mouse_down = False
        print(f"  [-] client disconnected: {addr}")


async def serve():
    print(f"\nWebSocket server listening on ws://{WS_HOST}:{WS_PORT}")
    print("Open board.py's page and start drawing!\n")
    async with websockets.serve(handle, WS_HOST, WS_PORT):
        await asyncio.Future()  # run forever


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    global BBOX
    print("=" * 55)
    print("  Virtual Board — Receiver")
    print("=" * 55)
    print("\nA fullscreen overlay will appear.")
    print("Drag a box over the target app (e.g. Jamboard), then release.\n")

    BBOX = select_bounding_box()
    if not BBOX:
        print("No bounding box selected — exiting.")
        sys.exit(1)

    x1, y1, x2, y2 = BBOX
    print(f"Bounding box set: ({x1},{y1}) → ({x2},{y2})  "
          f"[{x2-x1} × {y2-y1} px]")

    def run_server():
        asyncio.run(serve())

    server_thread = threading.Thread(target=run_server, daemon=False)
    server_thread.start()
    server_thread.join()


if __name__ == "__main__":
    main()
