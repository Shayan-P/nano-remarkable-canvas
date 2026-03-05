#!/usr/bin/env python3
"""
Read tablet events from stdin and write normalized stroke events as JSON lines to stdout.
Pipe into receiver.py to replay on screen.
"""

import json
import struct
import sys

EVENT_FORMAT = "<LLHHI"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

EV_KEY = 0x01
EV_ABS = 0x03
EV_SYN = 0x00
BTN_TOUCH = 0x14a
ABS_X = 0x01
ABS_Y = 0x00
ABS_PRESSURE = 0x18

# Tablet coordinate bounds for normalizing to 0–1
X_MIN, X_MAX = 0, 15600
Y_MIN, Y_MAX = 0, 20875


def normalize(x: int, y: int) -> tuple[float, float]:
    nx = (x - X_MIN) / max(1, X_MAX - X_MIN)
    ny = (y - Y_MIN) / max(1, Y_MAX - Y_MIN)
    nx = max(0.0, min(1.0, nx))
    ny = max(0.0, min(1.0, ny))
    return nx, ny


def main():
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
                msg = {"type": "mousedown", "x": nx, "y": ny}
            else:
                pen_down = False
                nx, ny = normalize(x, y)
                msg = {"type": "mouseup", "x": nx, "y": ny}
            print(json.dumps(msg), flush=True)

        elif type_ == EV_ABS:
            if code == ABS_X:
                x = value
            elif code == ABS_Y:
                y = value
            elif code == ABS_PRESSURE:
                pressure = value
            if pen_down and code in (ABS_X, ABS_Y, ABS_PRESSURE):
                nx, ny = normalize(x, y)
                msg = {"type": "mousemove", "x": nx, "y": ny}
                print(json.dumps(msg), flush=True)


if __name__ == "__main__":
    main()
