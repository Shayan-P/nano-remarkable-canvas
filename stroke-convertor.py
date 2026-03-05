#!/usr/bin/env python3
"""
Read tablet events from stdin and send normalized stroke events to the receiver
WebSocket server (ws://localhost:8765), same protocol as board.py.
"""

import asyncio
import json
import queue
import struct
import sys
import threading

import websockets

EVENT_FORMAT = "<LLHHI"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

EV_KEY = 0x01
EV_ABS = 0x03
EV_SYN = 0x00
BTN_TOUCH = 0x14a
ABS_X = 0x01
ABS_Y = 0x00
ABS_PRESSURE = 0x18

WS_URL = "ws://localhost:8765"

# Tablet coordinate bounds for normalizing to 0–1 (receiver expects nx, ny in [0, 1])
X_MIN, X_MAX = 0, 15600
Y_MIN, Y_MAX = 0, 20875


def normalize(x: int, y: int) -> tuple[float, float]:
    nx = (x - X_MIN) / max(1, X_MAX - X_MIN)
    ny = (y - Y_MIN) / max(1, Y_MAX - Y_MIN)
    nx = max(0.0, min(1.0, nx))
    ny = max(0.0, min(1.0, ny))
    return nx, ny


def run_reader(out_queue: queue.Queue):
    """Read stdin events and push { type, x, y } (normalized) onto queue."""
    pen_down = False
    x, y, pressure = 0, 0, 0

    while True:
        data = sys.stdin.buffer.read(EVENT_SIZE)
        if len(data) < EVENT_SIZE:
            break
        tv_sec, tv_usec, type_, code, value = struct.unpack(EVENT_FORMAT, data)

        if type_ == EV_SYN or type_ == 0:
            continue

        if type_ == EV_KEY and code == BTN_TOUCH:
            if value == 1:
                pen_down = True
                nx, ny = normalize(x, y)
                out_queue.put({"type": "mousedown", "x": nx, "y": ny})
            else:
                pen_down = False
                nx, ny = normalize(x, y)
                out_queue.put({"type": "mouseup", "x": nx, "y": ny})

        elif type_ == EV_ABS:
            if code == ABS_X:
                x = value
            elif code == ABS_Y:
                y = value
            elif code == ABS_PRESSURE:
                pressure = value
            if pen_down and code in (ABS_X, ABS_Y, ABS_PRESSURE):
                nx, ny = normalize(x, y)
                out_queue.put({"type": "mousemove", "x": nx, "y": ny})

    out_queue.put(None)  # EOF sentinel


async def send_to_server(out_queue: queue.Queue):
    """Connect to receiver and send queued messages (same format as board.py)."""
    try:
        async with websockets.connect(WS_URL) as ws:
            while True:
                try:
                    msg = out_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.001)
                    continue
                if msg is None:
                    return
                await ws.send(json.dumps(msg))
    except (ConnectionRefusedError, OSError) as e:
        print(f"Could not connect to {WS_URL}: {e}", file=sys.stderr)
        print("Start receiver.py first, then run this script.", file=sys.stderr)


def main():
    out_queue: queue.Queue = queue.Queue()
    thread = threading.Thread(target=run_reader, args=(out_queue,), daemon=True)
    thread.start()
    asyncio.run(send_to_server(out_queue))


if __name__ == "__main__":
    main()
