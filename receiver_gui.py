"""
receiver_gui.py — Fullscreen overlay to select a bounding box on screen.

Native macOS transparent overlay via PyObjC. No WebSocket, no stroke processing.
Install: pip install pyobjc-framework-Cocoa
"""

import sys
import time


def select_bounding_box() -> tuple[int, int, int, int] | None:
    """
    Show fullscreen overlay; user drags to select a rectangle.
    Returns (x1, y1, x2, y2) in screen coords (pyautogui top-left origin) or None if cancelled.
    """
    try:
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

    ACCENT_C = NSColor.colorWithRed_green_blue_alpha_(0.37, 0.91, 1.00, 1.0)
    HANDLE_C = NSColor.colorWithRed_green_blue_alpha_(1.00, 0.37, 0.67, 1.0)
    GLOW_C = NSColor.colorWithRed_green_blue_alpha_(0.37, 0.91, 1.00, 0.25)
    DIM_C = NSColor.colorWithWhite_alpha_(0.0, 0.45)

    _state = {"start": None, "end": None, "mouse": None}
    _app_box: list = []
    _last_mouse_display_time = [0.0]

    def _stop():
        class StopRunner(NSObject):
            def timerFire_(self, timer):
                win = _app_box[1]
                win.orderOut_(None)
                NSCursor.pop()
                a = _app_box[0]
                a.stop_(None)
                dummy = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                    15, NSMakePoint(0, 0), 0, 0, 0, None, 0, 0, 0)
                a.postEvent_atStart_(dummy, True)

        runner = StopRunner.alloc().init()
        _app_box.append(runner)
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.001, runner, "timerFire:", None, False)

    def _pt(event, view):
        p = view.convertPoint_fromView_(event.locationInWindow(), None)
        return (p.x, p.y)

    class OverlayView(NSView):
        def isOpaque(self):
            return False

        def acceptsFirstResponder(self):
            return True

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
            if s and abs(en[0] - s[0]) > 20 and abs(en[1] - s[1]) > 20:
                result.append((*s, *en))
            _stop()

        def mouseMoved_(self, e):
            _state["mouse"] = _pt(e, self)
            now = time.monotonic()
            if now - _last_mouse_display_time[0] >= 0.016:
                _last_mouse_display_time[0] = now
                self.setNeedsDisplay_(True)

        def keyDown_(self, e):
            if e.keyCode() == 53:
                _stop()

        def drawRect_(self, _dirty):
            b = self.bounds()
            bw = b.size.width
            bh = b.size.height

            NSColor.clearColor().setFill()
            NSBezierPath.fillRect_(b)
            DIM_C.setFill()
            NSBezierPath.fillRect_(b)

            ctx = NSGraphicsContext.currentContext()
            s, en = _state["start"], _state["end"]

            if s and en:
                rx = min(s[0], en[0])
                rw = abs(en[0] - s[0])
                ry = min(s[1], en[1])
                rh = abs(en[1] - s[1])
                sel = NSMakeRect(rx, ry, rw, rh)

                ctx.setCompositingOperation_(NSCompositingOperationClear)
                NSColor.blackColor().setFill()
                NSBezierPath.fillRect_(sel)
                ctx.setCompositingOperation_(NSCompositingOperationSourceOver)

                GLOW_C.setStroke()
                halo = NSBezierPath.bezierPathWithRect_(
                    NSMakeRect(rx - 6, ry - 6, rw + 12, rh + 12))
                halo.setLineWidth_(12.0)
                halo.stroke()

                ACCENT_C.setStroke()
                border = NSBezierPath.bezierPathWithRect_(sel)
                border.setLineWidth_(2.0)
                border.stroke()

                hs = 6
                for cx, cy in [(rx, ry), (rx + rw, ry), (rx, ry + rh), (rx + rw, ry + rh)]:
                    hp = NSBezierPath.bezierPathWithRect_(
                        NSMakeRect(cx - hs, cy - hs, hs * 2, hs * 2))
                    HANDLE_C.setFill()
                    hp.fill()
                    NSColor.whiteColor().setStroke()
                    hp.setLineWidth_(1.0)
                    hp.stroke()

                ms = 4
                for cx, cy in [(rx + rw / 2, ry), (rx + rw / 2, ry + rh),
                               (rx, ry + rh / 2), (rx + rw, ry + rh / 2)]:
                    mp = NSBezierPath.bezierPathWithRect_(
                        NSMakeRect(cx - ms, cy - ms, ms * 2, ms * 2))
                    ACCENT_C.setFill()
                    mp.fill()
                    NSColor.whiteColor().setStroke()
                    mp.setLineWidth_(1.0)
                    mp.stroke()

                self._draw_badge(f" {int(rw)} × {int(rh)} px ", rx + rw / 2, ry + rh / 2)

            m = _state["mouse"]
            if m:
                self._draw_crosshair(m[0], m[1], bw, bh)

            self._draw_pill(
                "  Drag to select drawing area   ·   Esc to cancel  ",
                bw / 2, bh - 64)

        def _draw_badge(self, text, cx, cy):
            from AppKit import NSAttributedString, NSForegroundColorAttributeName, NSFontAttributeName
            from Foundation import NSMakePoint
            font = NSFont.monospacedSystemFontOfSize_weight_(13, 0.4)
            attrs = {NSForegroundColorAttributeName: ACCENT_C, NSFontAttributeName: font}
            astr = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
            sz = astr.size()
            pad = 7
            bx, by = cx - sz.width / 2, cy - sz.height / 2
            bg = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                NSMakeRect(bx - pad, by - pad / 2, sz.width + pad * 2, sz.height + pad), 5, 5)
            NSColor.colorWithWhite_alpha_(0.06, 0.90).setFill()
            bg.fill()
            ACCENT_C.setStroke()
            bg.setLineWidth_(1.0)
            bg.stroke()
            astr.drawAtPoint_(NSMakePoint(bx, by))

        def _draw_pill(self, text, cx, cy):
            from AppKit import NSAttributedString, NSForegroundColorAttributeName, NSFontAttributeName
            from Foundation import NSMakePoint
            font = NSFont.systemFontOfSize_weight_(14, 0.3)
            attrs = {NSForegroundColorAttributeName: NSColor.whiteColor(), NSFontAttributeName: font}
            astr = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
            sz = astr.size()
            pad = 12
            bx, by = cx - sz.width / 2, cy - sz.height / 2
            bg = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                NSMakeRect(bx - pad, by - pad / 2, sz.width + pad * 2, sz.height + pad), 8, 8)
            NSColor.colorWithWhite_alpha_(0.08, 0.93).setFill()
            bg.fill()
            ACCENT_C.setStroke()
            bg.setLineWidth_(1.0)
            bg.stroke()
            astr.drawAtPoint_(NSMakePoint(bx, by))

        def _draw_crosshair(self, mx, my, bw, bh):
            from Foundation import NSMakePoint
            ch = NSColor.colorWithWhite_alpha_(1.0, 0.13)
            ch.setStroke()
            for p1, p2 in [((0, my), (bw, my)), ((mx, 0), (mx, bh))]:
                ln = NSBezierPath.bezierPath()
                ln.moveToPoint_(NSMakePoint(*p1))
                ln.lineToPoint_(NSMakePoint(*p2))
                ln.setLineWidth_(1.0)
                ln.stroke()
            r = 6
            ACCENT_C.setStroke()
            ring = NSBezierPath.bezierPathWithOvalInRect_(
                NSMakeRect(mx - r, my - r, r * 2, r * 2))
            ring.setLineWidth_(2.0)
            ring.stroke()
            for p1, p2 in [((mx - 14, my), (mx - r - 2, my)),
                           ((mx + r + 2, my), (mx + 14, my)),
                           ((mx, my - 14), (mx, my - r - 2)),
                           ((mx, my + r + 2), (mx, my + 14))]:
                tick = NSBezierPath.bezierPath()
                tick.moveToPoint_(NSMakePoint(*p1))
                tick.lineToPoint_(NSMakePoint(*p2))
                tick.setLineWidth_(1.5)
                tick.stroke()

    class OverlayWindow(NSWindow):
        def canBecomeKeyWindow(self):
            return True

        def canBecomeMainWindow(self):
            return True

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)
    _app_box.append(app)

    win = OverlayWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        sf, NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False)
    _app_box.append(win)
    win.setBackgroundColor_(NSColor.clearColor())
    win.setOpaque_(False)
    win.setLevel_(NSFloatingWindowLevel + 2)
    win.setIgnoresMouseEvents_(False)
    win.setAcceptsMouseMovedEvents_(True)
    win.makeKeyAndOrderFront_(None)

    view = OverlayView.alloc().initWithFrame_(sf)
    win.setContentView_(view)
    win.makeFirstResponder_(view)

    NSEventMaskKeyDown = 1 << 10

    def _on_key(event):
        if event.keyCode() == 53:
            _stop()

    key_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
        NSEventMaskKeyDown, _on_key)

    NSCursor.crosshairCursor().push()
    app.activateIgnoringOtherApps_(True)
    app.run()
    NSEvent.removeMonitor_(key_monitor)
    win.close()
    app.deactivate()

    if not result:
        return None

    sx, sy, ex, ey = result[0]
    x1 = int(min(sx, ex))
    x2 = int(max(sx, ex))
    y1_ns = int(min(sy, ey))
    y2_ns = int(max(sy, ey))
    return (x1, y1_ns, x2, y2_ns)
