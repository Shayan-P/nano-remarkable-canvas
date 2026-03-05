"""
stroke_replay.py — Process normalized stroke events into real mouse actions.

Takes a bounding box and applies mousedown/mousemove/mouseup/clear events.
Uses mouse_control for move/down/up (Quartz on macOS, pyautogui elsewhere).
Thread-safe queue (max 10); if over 10, drops oldest (FIFO).
"""

import queue
import threading

from mouse_control import mouse_down, mouse_move, mouse_up

MAX_QUEUE = 10


class StrokeReplayer:
    """Replays normalized (0–1) stroke events into screen coordinates inside bbox."""

    def __init__(self, bbox: tuple[int, int, int, int]):
        self.bbox = bbox
        self._mouse_down = False
        self._queue: queue.Queue[dict] = queue.Queue(maxsize=MAX_QUEUE)
        self._lock = threading.Lock()

    def _map_to_screen(self, nx: float, ny: float) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bbox
        return int(x1 + nx * (x2 - x1)), int(y1 + ny * (y2 - y1))

    def enqueue(self, msg: dict) -> None:
        """Add event to queue; if over 10, drop oldest of same type or oldest (FIFO). Does not process."""
        with self._lock:
            if self._queue.full():
                remaining: list[dict] = []
                dropped = None
                while True:
                    try:
                        item = self._queue.get_nowait()
                    except queue.Empty:
                        break
                    if dropped is None and item.get("type") == msg.get("type"):
                        dropped = item
                    else:
                        remaining.append(item)
                if dropped is None and remaining:
                    dropped = remaining.pop(0)
                for r in remaining:
                    self._queue.put(r)
            self._queue.put(msg)

    def process_one(self) -> None:
        """Pop the next event from the queue and apply it. No-op if queue empty."""
        try:
            last = self._queue.get_nowait()
        except queue.Empty:
            return
        self._apply(last)

    def _apply(self, msg: dict) -> None:
        """Apply one stroke event to the mouse."""
        kind = msg.get("type")
        nx = float(msg.get("x", 0.0))
        ny = float(msg.get("y", 0.0))
        ny = 1 - ny  # invert y axis
        sx, sy = self._map_to_screen(nx, ny)

        if kind == "mousedown":
            mouse_move(sx, sy)
            mouse_down(sx, sy)
            self._mouse_down = True
        elif kind == "mousemove" and self._mouse_down:
            mouse_move(sx, sy)
        elif kind == "mouseup":
            mouse_move(sx, sy)
            mouse_up(sx, sy)
            self._mouse_down = False
        elif kind == "clear":
            if self._mouse_down:
                mouse_up(sx, sy)
                self._mouse_down = False

    def release_if_down(self) -> None:
        """Release mouse button if currently down (e.g. on disconnect)."""
        if self._mouse_down:
            x, y = self._map_to_screen(0.5, 0.5)
            mouse_up(x, y)
            self._mouse_down = False
