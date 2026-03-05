#!/usr/bin/env python3
"""
receiver.py — Virtual Board Event Receiver

1. GUI: fullscreen overlay to select a bounding box (receiver_gui).
2. Load input: read JSON stroke events from stdin (one JSON object per line).
3. Process input: stroke_replay turns events into mouse actions (stroke_replay).

Requirements:
    pip install pyautogui

macOS note: grant Accessibility permissions to Terminal/iTerm in
System Settings → Privacy & Security → Accessibility.
"""

import json
import sys
import threading
import time

from receiver_gui import select_bounding_box
from stroke_replay import StrokeReplayer


def _stdin_reader(replayer: StrokeReplayer, stop_event: threading.Event) -> None:
    """Read JSON lines from stdin; enqueue each to replayer. On EOF, set stop_event."""
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            replayer.enqueue(msg)
    finally:
        replayer.release_if_down()
        stop_event.set()


def main():
    print("=" * 55)
    print("  Virtual Board — Receiver")
    print("=" * 55)
    print("\nA fullscreen overlay will appear.")
    print("Drag a box over the target app (e.g. Jamboard), then release.\n")

    bbox = select_bounding_box()
    if not bbox:
        print("No bounding box selected — exiting.")
        sys.exit(1)

    x1, y1, x2, y2 = bbox
    print(f"Bounding box set: ({x1},{y1}) → ({x2},{y2})  "
          f"[{x2 - x1} × {y2 - y1} px]")
    print("Reading stroke events from stdin (JSON lines).\n")

    replayer = StrokeReplayer(bbox)
    stop_event = threading.Event()

    def process_loop():
        while not stop_event.is_set():
            replayer.process_one()
            time.sleep(0.001)

    reader_thread = threading.Thread(target=_stdin_reader, args=(replayer, stop_event), daemon=True)
    processor_thread = threading.Thread(target=process_loop, daemon=True)
    reader_thread.start()
    processor_thread.start()
    stop_event.wait()


if __name__ == "__main__":
    main()
