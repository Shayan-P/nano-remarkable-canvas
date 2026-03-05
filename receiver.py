#!/usr/bin/env python3
"""
receiver.py — Virtual Board Event Receiver

1. GUI: fullscreen overlay to select a bounding box (receiver_gui).
2. Load input: WebSocket server receives JSON stroke events.
3. Process input: stroke_replay turns events into mouse actions (stroke_replay).

Requirements:
    pip install pyautogui websockets

macOS note: grant Accessibility permissions to Terminal/iTerm in
System Settings → Privacy & Security → Accessibility.
"""

import asyncio
import json
import sys
import threading
import time
import tty

import websockets

from receiver_gui import select_bounding_box
from stroke_replay import StrokeReplayer

WS_HOST = "localhost"
WS_PORT = 8765


# ── Load input (WebSocket) + dispatch to replayer ─────────────────────────────

async def handle(websocket, replayer: StrokeReplayer):
    """Load messages from WebSocket; pass each to replayer (no processing here)."""
    addr = websocket.remote_address
    print(f"  [+] client connected: {addr}")
    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            replayer.enqueue(msg)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        replayer.release_if_down()
        print(f"  [-] client disconnected: {addr}")


async def serve(replayer: StrokeReplayer, stop_event: asyncio.Event):
    """Run WebSocket server; each connection uses the same replayer."""
    print(f"\nWebSocket server listening on ws://{WS_HOST}:{WS_PORT}")
    print("Open board.py's page and start drawing!")
    print("Press ESC to stop.\n")

    async def handler(websocket):
        await handle(websocket, replayer)

    async with websockets.serve(handler, WS_HOST, WS_PORT):
        await stop_event.wait()


# ── ESC listener (stdlib) ────────────────────────────────────────────────────

def _listen_esc(stop_event: asyncio.Event) -> None:
    try:
        fd = sys.stdin.fileno()
        if not sys.stdin.isatty():
            return
        old = None
        try:
            import termios
            old = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        except Exception:
            return
        try:
            while True:
                c = sys.stdin.buffer.read(1)
                if c == b"\x1b":
                    stop_event.set()
                    break
        finally:
            if old is not None:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        pass


# ── entry point ───────────────────────────────────────────────────────────────

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

    replayer = StrokeReplayer(bbox)
    stop_event = asyncio.Event()

    def process_loop():
        """Pop events from queue and process (last-in-queue each time)."""
        while not stop_event.is_set():
            replayer.process_one()
            time.sleep(0.001)

    esc_thread = threading.Thread(target=_listen_esc, args=(stop_event,), daemon=True)
    esc_thread.start()
    processor_thread = threading.Thread(target=process_loop, daemon=True)
    processor_thread.start()

    def run_server():
        asyncio.run(serve(replayer, stop_event))

    server_thread = threading.Thread(target=run_server, daemon=False)
    server_thread.start()
    server_thread.join()


if __name__ == "__main__":
    main()
