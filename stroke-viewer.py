#!/usr/bin/env python3
"""Read stroke data from stdin and show the last point (x, y) and pressure (p) on screen."""

import json
import ast
import sys
import tkinter as tk
import threading


def parse_line(line: str):
    """Parse a line: either a JSON array (full stroke) or a dict (single point)."""
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(line)  # Python dict repr from print(stroke[-1])
        except (ValueError, SyntaxError):
            return None


# UI refresh rate (Hz)
REFRESH_HZ = 100

# Tablet coordinate bounds (for mapping to canvas)
X_MIN, X_MAX = 0, 15600
Y_MIN, Y_MAX = 0, 20875

def run_viewer():
    root = tk.Tk()
    root.title("Stroke viewer")
    root.geometry("300x400")
    root.resizable(True, True)

    # Shared state: [x, y, p] or None. Updated by reader thread, read by UI timer.
    last_point: list[int | None] = [None, None, None]
    point_lock = threading.Lock()

    label = tk.Label(
        root,
        text="x: —  y: —  p: —",
        font=("Menlo", 24),
        fg="black",
    )
    label.pack(padx=16, pady=(16, 8))

    canvas = tk.Canvas(root, bg="white", highlightthickness=1, highlightbackground="#ccc")
    canvas.pack(padx=16, pady=(0, 16), fill=tk.BOTH, expand=True)

    dot_id = None  # canvas item id for the point, so we can move/delete it

    def scale_x(x: int) -> float:
        cw = max(1, canvas.winfo_width())
        return (x - X_MIN) / max(1, X_MAX - X_MIN) * cw

    def scale_y(y: int) -> float:
        ch = max(1, canvas.winfo_height())
        return (Y_MAX - y) / max(1, Y_MAX - Y_MIN) * ch

    def refresh_ui():
        nonlocal dot_id
        with point_lock:
            x, y, p = last_point[0], last_point[1], last_point[2]
        if x is not None and y is not None and p is not None:
            cx, cy = scale_x(x), scale_y(y)
            label.config(text=f"x: {x}  y: {y}  p: {p} cx: {cx} cy: {cy}")
            r = max(3, min(20, 2 + p / 1500))  # radius from pressure
            if dot_id is not None:
                canvas.delete(dot_id)
            dot_id = canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill="black", outline="black")
        ms = int(1000 / REFRESH_HZ)
        root.after(ms, refresh_ui)

    def read_stdin():
        for line in sys.stdin:
            parsed = parse_line(line)
            if parsed is None:
                continue
            x, y, p = None, None, None
            if isinstance(parsed, list) and parsed:
                last = parsed[-1]
                if "x" in last and "y" in last:
                    x, y = last["x"], last["y"]
                    p = last.get("p", 0)
            elif isinstance(parsed, dict) and "x" in parsed and "y" in parsed:
                x = parsed["x"]
                y = parsed["y"]
                p = parsed.get("p", 0)
            if x is not None and y is not None:
                with point_lock:
                    last_point[0], last_point[1], last_point[2] = x, y, p
        root.after(0, root.quit)

    thread = threading.Thread(target=read_stdin, daemon=True)
    thread.start()
    root.after(0, refresh_ui)
    root.mainloop()


if __name__ == "__main__":
    run_viewer()
