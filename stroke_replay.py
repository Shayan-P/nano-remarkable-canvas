"""
stroke_replay.py — Process normalized stroke events into real mouse actions.

Takes a bounding box and applies mousedown/mousemove/mouseup/clear events
via pyautogui. Uses a queue (max 10); if over 10, drops oldest (FIFO).
Each process step applies only the last (most recent) event in the queue.
"""

import collections

import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

MAX_QUEUE = 10


class StrokeReplayer:
    """Replays normalized (0–1) stroke events into screen coordinates inside bbox."""

    def __init__(self, bbox: tuple[int, int, int, int]):
        self.bbox = bbox
        self._mouse_down = False
        self._queue: collections.deque[dict] = collections.deque(maxlen=MAX_QUEUE)

    def _map_to_screen(self, nx: float, ny: float) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bbox
        return int(x1 + nx * (x2 - x1)), int(y1 + ny * (y2 - y1))

    def enqueue(self, msg: dict) -> None:
        """Add event to queue; if over 10, drop oldest (FIFO). Does not process."""
        self._queue.append(msg)

    def process_one(self) -> None:
        """Pop the last (most recent) event from the queue and apply it. No-op if queue empty."""
        if not self._queue:
            return
        last = self._queue.pop()
        self._apply(last)

    def _apply(self, msg: dict) -> None:
        """Apply one stroke event to the mouse."""
        kind = msg.get("type")
        nx = float(msg.get("x", 0.0))
        ny = float(msg.get("y", 0.0))
        ny = 1 - ny # invert y axis
        sx, sy = self._map_to_screen(nx, ny)

        if kind == "mousedown":
            pyautogui.moveTo(sx, sy)
            pyautogui.mouseDown()
            self._mouse_down = True
        elif kind == "mousemove" and self._mouse_down:
            pyautogui.moveTo(sx, sy)
        elif kind == "mouseup":
            pyautogui.moveTo(sx, sy)
            pyautogui.mouseUp()
            self._mouse_down = False
        elif kind == "clear":
            if self._mouse_down:
                pyautogui.mouseUp()
                self._mouse_down = False

    def release_if_down(self) -> None:
        """Release mouse button if currently down (e.g. on disconnect)."""
        if self._mouse_down:
            pyautogui.mouseUp()
            self._mouse_down = False
